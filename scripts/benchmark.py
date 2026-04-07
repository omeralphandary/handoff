"""
Oversight -- mixed dataset benchmark.

Samples images from all three datasets, runs the full pipeline on each,
then writes a CSV + PDF summary with miss/FP examples.

Usage:
    python scripts/benchmark.py                        # 300 images, local VLM
    python scripts/benchmark.py --n 100 --no-vlm      # fast local-only run
    python scripts/benchmark.py --backend anthropic    # use Claude

Datasets:
  boxes/             -- damaged vs undamaged packages (ground truth: folder name)
  orc_codes/codes/   -- barcode/QR images  (ground truth: image contains a code)
  orc_codes/ocr_text/-- business-card text (ground truth: image contains text)

Output (written to data/results/):
  benchmark_<timestamp>.csv
  benchmark_<timestamp>.pdf
"""
from __future__ import annotations
import sys
import json
import random
import asyncio
import argparse
import csv
import zipfile
import tempfile
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import numpy as np
import config
from vlm.client import get_vlm_client
from vlm.prompts import DOCUMENTATION_PROMPT
from tasks._ocr_readers import read_barcodes, read_text

# ── constants ─────────────────────────────────────────────────────────────────

DATASETS_DIR = config.DATA_DIR / "test_datasets"
RESULTS_DIR  = config.DATA_DIR / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

OCR_CLEANUP_PROMPT = """You are reading shipping/logistics labels. Below are raw OCR and barcode reads.
Structure them into typed identifiers.

Raw text lines: {texts}
Barcodes/QR codes: {barcodes}

Return valid JSON only:
{{
  "texts": [str],
  "barcodes": [str],
  "identifiers": [{{"label": str, "value": str}}],
  "summary": str,
  "flagged": false
}}
If nothing meaningful was found set flagged to true."""

BARCODE_DETECT_PROMPT = """Is there a barcode, QR code, or other machine-readable symbol in this image?
Even if the image is blurry or partially obscured, try to detect it.

Return valid JSON only:
{{
  "barcode_detected": true or false,
  "barcode_type": "qr_code" or "barcode" or "none",
  "content": "decoded content if readable, or null",
  "summary": "one sentence description"
}}"""

# ── data structures ───────────────────────────────────────────────────────────

DatasetType = Literal["damage", "barcode", "ocr_text"]

@dataclass
class Sample:
    image_path: Path
    dataset: DatasetType
    ground_truth: str             # "damaged"|"undamaged" | "has_barcode" | "has_text"
    local_decode: list[str] = field(default_factory=list)  # pyzbar/cv2 result for barcodes

@dataclass
class Result:
    sample: Sample
    # damage
    condition_score: int | None = None
    passed: bool | None = None
    damage_summary: str = ""
    # ocr / barcode
    barcodes_found: list[str] = field(default_factory=list)
    texts_found: list[str] = field(default_factory=list)
    identifiers: list[dict] = field(default_factory=list)
    ocr_summary: str = ""
    # shared
    flagged: bool = False
    parse_error: bool = False
    correct: bool | None = None   # None = not evaluable
    skipped: bool = False         # VLM disabled for this task type
    elapsed_s: float = 0.0
    error: str = ""

# ── PDF helper ────────────────────────────────────────────────────────────────

def _safe(text: str) -> str:
    """Strip characters outside latin-1 range (fpdf2 core fonts limitation)."""
    return text.encode("latin-1", errors="replace").decode("latin-1")

# ── dataset loaders ───────────────────────────────────────────────────────────

def _load_box_samples(n_damaged: int, n_undamaged: int) -> list[Sample]:
    boxes = DATASETS_DIR / "boxes"
    damaged, undamaged = [], []
    for split in ("test", "valid", "train"):
        damaged   += list((boxes / split / "damagedpackages").glob("*.jpg"))
        undamaged += list((boxes / split / "undamagedpackages").glob("*.jpg"))
    random.shuffle(damaged)
    random.shuffle(undamaged)
    samples = []
    for p in damaged[:n_damaged]:
        samples.append(Sample(p, "damage", "damaged"))
    for p in undamaged[:n_undamaged]:
        samples.append(Sample(p, "damage", "undamaged"))
    return samples


def _extract_zip_images(zip_path: Path, extract_dir: Path) -> list[Path]:
    extract_dir.mkdir(parents=True, exist_ok=True)
    images = []
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if name.lower().endswith((".jpg", ".jpeg", ".png")) and "/" in name:
                dest = extract_dir / Path(name).name
                if not dest.exists():
                    with z.open(name) as src, open(dest, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                images.append(dest)
    return images


def _load_barcode_samples(n: int, extract_dir: Path) -> list[Sample]:
    zip_path = DATASETS_DIR / "orc_codes" / "codes" / "Barcode-Detection.v1i.coco.zip"
    images = _extract_zip_images(zip_path, extract_dir / "barcodes")
    random.shuffle(images)
    samples = []
    for p in images[:n]:
        frame = cv2.imread(str(p))
        local = read_barcodes(frame) if frame is not None else []
        s = Sample(p, "barcode", "has_barcode")
        s.local_decode = local
        samples.append(s)
    return samples


def _load_ocr_text_samples(n: int, extract_dir: Path) -> list[Sample]:
    zip_path = DATASETS_DIR / "orc_codes" / "ocr_text" / "OCR.v8i.coco.zip"
    images = _extract_zip_images(zip_path, extract_dir / "ocr_text")
    random.shuffle(images)
    return [Sample(p, "ocr_text", "has_text") for p in images[:n]]


# ── pipeline runners ──────────────────────────────────────────────────────────

async def _run_damage(sample: Sample, vlm, no_vlm: bool) -> Result:
    r = Result(sample=sample)
    if no_vlm:
        r.skipped = True
        return r
    frame = cv2.imread(str(sample.image_path))
    if frame is None:
        r.error = "could not load image"
        return r
    t0 = asyncio.get_event_loop().time()
    try:
        result = await vlm.analyze(frame, DOCUMENTATION_PROMPT)
        r.elapsed_s   = round(asyncio.get_event_loop().time() - t0, 2)
        r.condition_score = result.get("condition_score")
        r.passed      = result.get("passed", True)
        r.damage_summary = result.get("summary", "")
        r.parse_error = bool(result.get("parse_error"))
        r.flagged     = not r.passed
        if not r.parse_error:
            gt_damaged  = sample.ground_truth == "damaged"
            r.correct   = gt_damaged == (not r.passed)
    except Exception as exc:
        r.error = str(exc)
    return r


async def _run_barcode(sample: Sample, vlm, no_vlm: bool) -> Result:
    r = Result(sample=sample)
    frame = cv2.imread(str(sample.image_path))
    if frame is None:
        r.error = "could not load image"
        return r
    t0 = asyncio.get_event_loop().time()
    try:
        # Local decode result already captured in sample.local_decode
        local_codes = sample.local_decode

        if no_vlm:
            r.elapsed_s    = round(asyncio.get_event_loop().time() - t0, 2)
            r.barcodes_found = local_codes
            r.correct      = len(local_codes) > 0
        else:
            # Ask VLM to detect barcode (handles augmented/distorted images)
            result = await vlm.analyze(frame, BARCODE_DETECT_PROMPT)
            r.elapsed_s   = round(asyncio.get_event_loop().time() - t0, 2)
            r.parse_error = bool(result.get("parse_error"))
            detected      = bool(result.get("barcode_detected"))
            content       = result.get("content") or ""
            r.ocr_summary = result.get("summary", "")
            vlm_codes = [str(content)] if content else []
            r.barcodes_found = vlm_codes or local_codes
            r.correct     = detected or len(local_codes) > 0
            r.flagged     = not r.correct
    except Exception as exc:
        r.error = str(exc)
    return r


async def _run_ocr_text(sample: Sample, vlm, no_vlm: bool) -> Result:
    r = Result(sample=sample)
    frame = cv2.imread(str(sample.image_path))
    if frame is None:
        r.error = "could not load image"
        return r
    t0 = asyncio.get_event_loop().time()
    try:
        texts    = read_text(frame)
        barcodes = read_barcodes(frame)

        if not no_vlm and (texts or barcodes):
            prompt = OCR_CLEANUP_PROMPT.format(
                texts=texts or ["(none)"],
                barcodes=barcodes or ["(none)"],
            )
            result = await vlm.analyze(frame, prompt)
            r.elapsed_s     = round(asyncio.get_event_loop().time() - t0, 2)
            r.parse_error   = bool(result.get("parse_error"))
            r.texts_found   = result.get("texts", texts)
            r.barcodes_found = result.get("barcodes", barcodes)
            r.identifiers   = result.get("identifiers", [])
            r.ocr_summary   = result.get("summary", "")
        else:
            r.elapsed_s     = round(asyncio.get_event_loop().time() - t0, 2)
            r.texts_found   = texts
            r.barcodes_found = barcodes

        r.correct = len(r.texts_found) > 0 or len(r.barcodes_found) > 0
        r.flagged = not r.correct
    except Exception as exc:
        r.error = str(exc)
    return r


async def run_sample(sample: Sample, vlm, no_vlm: bool, sem: asyncio.Semaphore) -> Result:
    async with sem:
        if sample.dataset == "damage":
            return await _run_damage(sample, vlm, no_vlm)
        elif sample.dataset == "barcode":
            return await _run_barcode(sample, vlm, no_vlm)
        else:
            return await _run_ocr_text(sample, vlm, no_vlm)


# ── CSV writer ────────────────────────────────────────────────────────────────

def write_csv(results: list[Result], path: Path) -> None:
    fieldnames = [
        "image", "dataset", "ground_truth", "local_decode",
        "condition_score", "passed", "damage_summary",
        "barcodes_found", "texts_found", "identifiers", "ocr_summary",
        "flagged", "correct", "parse_error", "skipped", "elapsed_s", "error",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in results:
            w.writerow({
                "image":           r.sample.image_path.name,
                "dataset":         r.sample.dataset,
                "ground_truth":    r.sample.ground_truth,
                "local_decode":    "|".join(r.sample.local_decode),
                "condition_score": r.condition_score if r.condition_score is not None else "",
                "passed":          "" if r.passed is None else str(r.passed),
                "damage_summary":  r.damage_summary,
                "barcodes_found":  "|".join(x for x in r.barcodes_found if x),
                "texts_found":     "|".join(x for x in r.texts_found[:8] if x),
                "identifiers":     json.dumps(r.identifiers[:5]),
                "ocr_summary":     r.ocr_summary,
                "flagged":         str(r.flagged),
                "correct":         "" if r.correct is None else str(r.correct),
                "parse_error":     str(r.parse_error),
                "skipped":         str(r.skipped),
                "elapsed_s":       r.elapsed_s,
                "error":           r.error,
            })


# ── PDF writer ────────────────────────────────────────────────────────────────

def write_pdf(results: list[Result], csv_path: Path, pdf_path: Path, cfg: dict) -> None:
    from fpdf import FPDF

    damage_results  = [r for r in results if r.sample.dataset == "damage"   and not r.error and not r.skipped]
    barcode_results = [r for r in results if r.sample.dataset == "barcode"  and not r.error]
    ocr_results     = [r for r in results if r.sample.dataset == "ocr_text" and not r.error]

    def _acc(rs: list[Result]):
        valid = [r for r in rs if r.correct is not None]
        if not valid:
            return 0, 0, 0.0
        correct = sum(1 for r in valid if r.correct)
        return correct, len(valid), correct / len(valid) * 100

    dmg_correct, dmg_total, dmg_acc = _acc(damage_results)
    bc_correct,  bc_total,  bc_acc  = _acc(barcode_results)
    ocr_correct, ocr_total, ocr_acc = _acc(ocr_results)

    dmg_misses = [r for r in damage_results if r.correct is False and r.sample.ground_truth == "damaged"]
    dmg_fps    = [r for r in damage_results if r.correct is False and r.sample.ground_truth == "undamaged"]
    bc_misses  = [r for r in barcode_results if r.correct is False]
    ocr_misses = [r for r in ocr_results    if r.correct is False]

    parse_errors = sum(1 for r in results if r.parse_error)
    vlm_results  = [r for r in results if r.elapsed_s > 0]
    avg_elapsed  = sum(r.elapsed_s for r in vlm_results) / max(1, len(vlm_results))

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_margins(16, 16, 16)
    W = 178

    def cell(text, w=None, h=6, style="", size=10, ln=True, align="L"):
        pdf.set_font("Helvetica", style, size)
        kw = dict(w=w or W, h=h, text=_safe(str(text)), align=align,
                  new_x="LMARGIN" if ln else "RIGHT",
                  new_y="NEXT"    if ln else "TOP")
        pdf.cell(**kw)

    def heading(text: str, size: int = 12):
        pdf.set_fill_color(28, 28, 28)
        pdf.set_text_color(230, 230, 230)
        cell(text, style="B", size=size, h=8)
        pdf.set_fill_color(255, 255, 255)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)

    def section(text: str):
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(40, 40, 40)
        cell(text, h=7)
        pdf.set_draw_color(200, 200, 200)
        pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + W, pdf.get_y())
        pdf.ln(3)
        pdf.set_text_color(0, 0, 0)

    def stat_row(label: str, value: str, good: bool | None = None):
        color = (34, 197, 94) if good is True else (239, 68, 68) if good is False else (100, 100, 100)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(85, 6, _safe(label), new_x="RIGHT", new_y="TOP")
        pdf.set_text_color(*color)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(W - 85, 6, _safe(value), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)

    def thumb_row(row_results: list[Result], caption_fn, max_n: int = 6):
        items = row_results[:max_n]
        if not items:
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(150, 150, 150)
            pdf.cell(W, 6, "  None.", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
            return

        THUMB_W, THUMB_H, GAP, COLS = 54, 40, 4, 3
        row_start_y = pdf.get_y()

        for i, r in enumerate(items):
            col = i % COLS
            x = pdf.l_margin + col * (THUMB_W + GAP)
            y = row_start_y + (i // COLS) * (THUMB_H + 16)

            frame = cv2.imread(str(r.sample.image_path))
            if frame is not None:
                h, w = frame.shape[:2]
                scale = min(THUMB_W * 3.78 / w, THUMB_H * 3.78 / h)
                nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
                thumb = cv2.resize(frame, (nw, nh))
                tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
                cv2.imwrite(tmp.name, thumb, [cv2.IMWRITE_JPEG_QUALITY, 75])
                tmp.close()
                try:
                    pdf.image(tmp.name, x=x, y=y, w=THUMB_W, h=THUMB_H)
                except Exception:
                    pass
                Path(tmp.name).unlink(missing_ok=True)

            pdf.set_xy(x, y + THUMB_H + 1)
            pdf.set_font("Helvetica", "", 7)
            pdf.set_text_color(80, 80, 80)
            cap = _safe(caption_fn(r))[:120]
            pdf.multi_cell(THUMB_W, 3.5, cap, align="L",
                           new_x="RIGHT", new_y="TOP")
            pdf.set_text_color(0, 0, 0)

        rows = (len(items) + COLS - 1) // COLS
        pdf.set_y(row_start_y + rows * (THUMB_H + 16) + 4)

    # ── Page 1: title + summary ───────────────────────────────────────────────
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(W, 13, "Oversight -- Benchmark Report",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(130, 130, 130)
    ts_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    cell(f"Generated: {ts_str}   Backend: {cfg['backend']}   Model: {cfg['model']}   "
         f"Samples: {len(results)}", size=9)
    cell(f"CSV: {csv_path.name}", size=9)
    pdf.ln(6)

    section("Overall Results")
    n_dmg_skipped = sum(1 for r in results if r.sample.dataset == "damage" and r.skipped)
    if n_dmg_skipped:
        stat_row("Damage detection", "N/A (VLM disabled)")
    else:
        stat_row("Damage detection accuracy",
                 f"{dmg_acc:.1f}%  ({dmg_correct}/{dmg_total})",
                 good=dmg_acc >= 80)
        stat_row("  Misses (damaged, called safe)",       str(len(dmg_misses)), good=len(dmg_misses) == 0)
        stat_row("  False positives (safe, called dmg)",  str(len(dmg_fps)),    good=len(dmg_fps) == 0)
    stat_row("Barcode detection rate",
             f"{bc_acc:.1f}%  ({bc_correct}/{bc_total})",
             good=bc_acc >= 70)
    stat_row("  Misses (no barcode found)",              str(len(bc_misses)),  good=len(bc_misses) == 0)
    stat_row("OCR text detection rate",
             f"{ocr_acc:.1f}%  ({ocr_correct}/{ocr_total})",
             good=ocr_acc >= 80)
    stat_row("  Misses (no text detected)",              str(len(ocr_misses)), good=len(ocr_misses) == 0)
    stat_row("VLM parse errors",                         str(parse_errors),    good=parse_errors == 0)
    stat_row("Avg VLM latency",                          f"{avg_elapsed:.1f}s")
    pdf.ln(4)

    # Condition score distribution
    scores = [r.condition_score for r in damage_results if r.condition_score is not None]
    if scores:
        section("Condition Score Distribution (1=severe, 5=pass)")
        max_count = max((scores.count(s) for s in range(1, 6)), default=1)
        for score in range(1, 6):
            count = scores.count(score)
            bar_len = int(count / max_count * 50) if max_count else 0
            pdf.set_font("Courier", "", 9)
            pdf.set_text_color(60, 60, 60)
            pdf.cell(8, 5, str(score), new_x="RIGHT", new_y="TOP")
            pdf.set_text_color(60, 120, 200)
            pdf.cell(100, 5, "|" * bar_len, new_x="RIGHT", new_y="TOP")
            pdf.set_text_color(80, 80, 80)
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(20, 5, f" {count}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(4)

    # ── Page 2: damage examples ───────────────────────────────────────────────
    if damage_results:
        pdf.add_page()
        heading("Damage Detection -- Misses (damaged image, model said PASS)")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(120, 120, 120)
        cell(f"{len(dmg_misses)} misses out of {dmg_total} damage samples", size=9)
        pdf.ln(3)
        thumb_row(dmg_misses,
                  lambda r: f"GT: damaged  Score:{r.condition_score}  {r.damage_summary[:70]}")

        heading("Damage Detection -- False Positives (undamaged, model flagged)")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(120, 120, 120)
        cell(f"{len(dmg_fps)} false positives", size=9)
        pdf.ln(3)
        thumb_row(dmg_fps,
                  lambda r: f"GT: undamaged  Score:{r.condition_score}  {r.damage_summary[:70]}")

    # ── Page 3: barcode examples ──────────────────────────────────────────────
    pdf.add_page()
    heading("Barcode Detection -- Misses")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(120, 120, 120)
    cell(f"{len(bc_misses)} misses out of {bc_total} barcode samples "
         f"(note: images are augmented/distorted -- lower decode rate expected)", size=9)
    pdf.ln(3)
    thumb_row(bc_misses,
              lambda r: f"local_decode:{r.sample.local_decode or 'none'}  pipeline:{r.barcodes_found or 'none'}")

    heading("Barcode Detection -- Correct Examples")
    correct_bc = [r for r in barcode_results if r.correct][:6]
    thumb_row(correct_bc,
              lambda r: f"Decoded: {', '.join(r.barcodes_found[:2])[:80]}")

    # ── Page 4: OCR text examples ─────────────────────────────────────────────
    pdf.add_page()
    heading("OCR Text Detection -- Misses")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(120, 120, 120)
    cell(f"{len(ocr_misses)} misses out of {ocr_total} text samples", size=9)
    pdf.ln(3)
    thumb_row(ocr_misses,
              lambda r: "No text detected.")

    heading("OCR Text Detection -- Correct Examples")
    correct_ocr = [r for r in ocr_results if r.correct and r.texts_found][:6]
    thumb_row(correct_ocr,
              lambda r: f"Found: {', '.join(r.texts_found[:4])[:80]}")

    pdf.output(str(pdf_path))


# ── main ──────────────────────────────────────────────────────────────────────

async def main(n: int, backend: str, no_vlm: bool, concurrency: int, seed: int) -> None:
    random.seed(seed)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    print(f"\nOversight Benchmark  |  n={n}  backend={backend}  no-vlm={no_vlm}")
    print("=" * 60)

    extract_dir = config.DATA_DIR / "test_datasets" / "_extracted"
    extract_dir.mkdir(exist_ok=True)

    # Sample mix: 50% damage, ~33% barcode, rest OCR text
    n_half      = n // 2
    n_damaged   = n_half // 2
    n_undamaged = n_half // 2
    n_barcode   = int(n * 0.33)
    n_ocr       = n - (n_damaged + n_undamaged) - n_barcode

    print(f"Sample mix: {n_damaged+n_undamaged} damage ({n_damaged}dmg/{n_undamaged}ok), "
          f"{n_barcode} barcode, {n_ocr} ocr-text")

    print("Loading datasets... ", end="", flush=True)
    samples: list[Sample] = []
    samples += _load_box_samples(n_damaged, n_undamaged)
    samples += _load_barcode_samples(n_barcode, extract_dir)
    samples += _load_ocr_text_samples(n_ocr, extract_dir)
    random.shuffle(samples)
    print(f"done  ({len(samples)} samples)")

    if not no_vlm:
        config.VLM_BACKEND = backend
        vlm = get_vlm_client()
        model_name = config.VLM_MODEL if backend == "anthropic" else config.LOCAL_MODEL
        print(f"VLM: {backend}  model: {model_name}")
    else:
        vlm = None
        model_name = "none"
        print("VLM: disabled (local readers only)")

    sem = asyncio.Semaphore(concurrency)
    tasks = [run_sample(s, vlm, no_vlm, sem) for s in samples]

    results: list[Result] = []
    done = 0
    total = len(tasks)
    print(f"\nRunning {total} samples (concurrency={concurrency})...")

    for coro in asyncio.as_completed(tasks):
        r = await coro
        results.append(r)
        done += 1
        icon = ("V" if r.correct else "X" if r.correct is False
                else "-" if r.skipped else "E" if r.error else "?")
        bar = "#" * int(done / total * 30)
        print(f"\r  [{bar:<30}] {done}/{total}  {icon}", end="", flush=True)

    print(f"\r  [{'#'*30}] {total}/{total}  done          ")

    # ── stats preview ──────────────────────────────────────────────────────────
    def _stats_line(rs: list[Result], label: str):
        skipped = sum(1 for r in rs if r.skipped)
        if skipped == len(rs):
            print(f"  {label:<24} N/A (VLM disabled)")
            return
        valid = [r for r in rs if r.correct is not None and not r.error and not r.skipped]
        if not valid:
            return
        n_correct = sum(1 for r in valid if r.correct)
        acc = n_correct / len(valid) * 100
        perr = sum(1 for r in rs if r.parse_error)
        errs = sum(1 for r in rs if r.error)
        print(f"  {label:<24} {acc:5.1f}%  ({n_correct}/{len(valid)})  "
              f"parse_err={perr}  load_err={errs}")

    print("\nResults:")
    _stats_line([r for r in results if r.sample.dataset == "damage"],   "Damage detection")
    _stats_line([r for r in results if r.sample.dataset == "barcode"],  "Barcode detection")
    _stats_line([r for r in results if r.sample.dataset == "ocr_text"], "OCR text detection")

    csv_path = RESULTS_DIR / f"benchmark_{ts}.csv"
    pdf_path = RESULTS_DIR / f"benchmark_{ts}.pdf"

    print(f"\nWriting CSV ... {csv_path.name}")
    write_csv(results, csv_path)

    print(f"Writing PDF ... {pdf_path.name}")
    write_pdf(results, csv_path, pdf_path, {"backend": backend, "model": model_name})

    print(f"\nDone.")
    print(f"  CSV: {csv_path}")
    print(f"  PDF: {pdf_path}\n")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--n",           type=int, default=300)
    p.add_argument("--backend",     default=config.VLM_BACKEND, choices=["local", "anthropic"])
    p.add_argument("--no-vlm",      action="store_true")
    p.add_argument("--concurrency", type=int, default=2)
    p.add_argument("--seed",        type=int, default=42)
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(
        n=args.n,
        backend=args.backend,
        no_vlm=args.no_vlm,
        concurrency=args.concurrency,
        seed=args.seed,
    ))
