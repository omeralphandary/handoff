"""
Batch test the VLM pipeline against a labeled image dataset.
Outputs a CSV — no PDFs generated.

Usage:
    python scripts/batch_test.py
    python scripts/batch_test.py --split test          # default
    python scripts/batch_test.py --split all
    python scripts/batch_test.py --concurrency 4       # parallel VLM calls
    python scripts/batch_test.py --limit 20            # cap number of images
"""
from __future__ import annotations
import sys
import asyncio
import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from vlm.client import get_vlm_client
from vlm.prompts import DOCUMENTATION_PROMPT
import config

DATASET_DIR = config.BASE_DIR / "data" / "test_datasets"
RESULTS_DIR = config.BASE_DIR / "data" / "results"

# folder name → ground truth label
LABEL_MAP = {
    "damagedpackages": "damaged",
    "undamagedpackages": "undamaged",
}


def collect_images(split: str) -> list[tuple[Path, str]]:
    """Return list of (image_path, ground_truth_label)."""
    splits = ["train", "test", "valid"] if split == "all" else [split]
    items: list[tuple[Path, str]] = []
    for s in splits:
        for folder, label in LABEL_MAP.items():
            folder_path = DATASET_DIR / s / folder
            if folder_path.exists():
                for img in sorted(folder_path.glob("*.jpg")):
                    items.append((img, label))
    return items


async def analyze_one(
    client,
    image_path: Path,
    label: str,
    semaphore: asyncio.Semaphore,
    idx: int,
    total: int,
) -> dict:
    import cv2
    async with semaphore:
        frame = cv2.imread(str(image_path))
        if frame is None:
            print(f"  [{idx}/{total}] SKIP (unreadable): {image_path.name}")
            return {
                "filename": image_path.name,
                "split": image_path.parts[-3],
                "actual_label": label,
                "condition_score": None,
                "passed": None,
                "correct": None,
                "damage_items": "",
                "summary": "unreadable image",
                "parse_error": True,
            }

        result = await client.analyze(frame, DOCUMENTATION_PROMPT)
        score = result.get("condition_score")
        passed = result.get("passed")

        # infer passed from score if model didn't return it explicitly
        if passed is None and score is not None:
            passed = score == 5

        predicted = "undamaged" if passed else "damaged"
        correct = predicted == label

        status = "OK" if correct else "WRONG"
        print(
            f"  [{idx}/{total}] {status}  score={score}  actual={label}  "
            f"predicted={predicted}  {image_path.name}"
        )

        return {
            "filename": image_path.name,
            "split": image_path.parts[-3],
            "actual_label": label,
            "condition_score": score,
            "passed": passed,
            "correct": correct,
            "damage_items": json.dumps(result.get("damage_items", [])),
            "summary": result.get("summary", ""),
            "parse_error": result.get("parse_error", False),
        }


async def run(split: str, concurrency: int, limit: int | None) -> None:
    images = collect_images(split)
    if limit:
        images = images[:limit]

    total = len(images)
    print(f"\nDataset : {DATASET_DIR}")
    print(f"Split   : {split}")
    print(f"Images  : {total}")
    print(f"Backend : {config.VLM_BACKEND}  ({config.LOCAL_MODEL if config.VLM_BACKEND == 'local' else config.VLM_MODEL})")
    print(f"Workers : {concurrency}\n")

    client = get_vlm_client()
    semaphore = asyncio.Semaphore(concurrency)

    tasks = [
        analyze_one(client, path, label, semaphore, idx + 1, total)
        for idx, (path, label) in enumerate(images)
    ]
    rows = await asyncio.gather(*tasks)

    # Summary stats
    completed = [r for r in rows if not r["parse_error"]]
    correct = sum(1 for r in completed if r["correct"])
    damaged_rows = [r for r in completed if r["actual_label"] == "damaged"]
    undamaged_rows = [r for r in completed if r["actual_label"] == "undamaged"]
    tp = sum(1 for r in damaged_rows if not r["passed"])    # correctly caught
    fp = sum(1 for r in undamaged_rows if not r["passed"])  # false alarms
    fn = sum(1 for r in damaged_rows if r["passed"])        # missed damage
    tn = sum(1 for r in undamaged_rows if r["passed"])      # correctly passed

    print(f"\n{'='*50}")
    print(f"Accuracy        : {correct}/{len(completed)} ({100*correct/max(len(completed),1):.1f}%)")
    print(f"True positives  : {tp}/{len(damaged_rows)}  (damaged correctly flagged)")
    print(f"False positives : {fp}/{len(undamaged_rows)}  (good packages flagged)")
    print(f"False negatives : {fn}/{len(damaged_rows)}  (damage missed)")
    print(f"True negatives  : {tn}/{len(undamaged_rows)}  (good packages passed)")
    print(f"{'='*50}\n")

    # Write CSV
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    accuracy_pct = int(100 * correct / max(len(completed), 1))
    csv_path = RESULTS_DIR / f"batch_{ts}_acc{accuracy_pct}.csv"

    fieldnames = [
        "filename", "split", "actual_label", "condition_score",
        "passed", "correct", "damage_items", "summary", "parse_error",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Results saved: {csv_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch test VLM pipeline")
    parser.add_argument("--split", choices=["test", "train", "valid", "all"], default="test")
    parser.add_argument("--concurrency", type=int, default=3, help="Parallel VLM calls")
    parser.add_argument("--limit", type=int, default=None, help="Cap number of images")
    args = parser.parse_args()
    asyncio.run(run(args.split, args.concurrency, args.limit))


if __name__ == "__main__":
    main()
