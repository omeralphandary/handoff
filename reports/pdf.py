"""PDF evidence report generator."""
from __future__ import annotations
from pathlib import Path
from fpdf import FPDF
import config

FONT_PATH = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
FONT_BOLD_PATH = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")


def _make_pdf() -> FPDF:
    pdf = FPDF()
    pdf.add_font("DejaVu", style="", fname=str(FONT_PATH))
    pdf.add_font("DejaVu", style="B", fname=str(FONT_BOLD_PATH))
    return pdf


def generate_pdf(record: dict) -> Path:
    pdf = _make_pdf()
    pdf.add_page()

    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, "Handoff — Evidence Report", ln=True)

    pdf.set_font("DejaVu", "", 10)
    pdf.cell(0, 6, f"Record ID : {record['id']}", ln=True)
    pdf.cell(0, 6, f"Zone      : {record['zone_name']}", ln=True)
    pdf.cell(0, 6, f"Task      : {record['task_type']}", ln=True)
    pdf.cell(0, 6, f"Timestamp : {record['timestamp']}", ln=True)
    pdf.cell(0, 6, f"Flagged   : {'YES' if record['flagged'] else 'no'}", ln=True)
    pdf.ln(4)

    # Image
    image_path = record.get("image_path")
    if image_path and Path(image_path).exists():
        pdf.image(image_path, w=180)
        pdf.ln(4)

    # Result
    result = record.get("result", {})
    score = result.get("condition_score")
    passed = result.get("passed", not record.get("flagged"))

    pdf.set_font("DejaVu", "B", 12)
    pdf.cell(0, 8, "Condition Assessment", ln=True)
    pdf.set_font("DejaVu", "", 11)

    verdict = "PASS" if passed else f"FAIL  (score {score}/5)"
    pdf.cell(0, 8, f"Result  : {verdict}", ln=True)
    if score is not None:
        pdf.cell(0, 6, f"Score   : {score} / 5", ln=True)
    pdf.ln(2)

    if not passed:
        summary = result.get("summary", "")
        if summary:
            pdf.set_font("DejaVu", "B", 10)
            pdf.cell(0, 6, "Description", ln=True)
            pdf.set_font("DejaVu", "", 10)
            pdf.multi_cell(0, 6, summary)
            pdf.ln(2)

        items = result.get("damage_items", []) or result.get("anomalies", [])
        if items:
            pdf.set_font("DejaVu", "B", 10)
            pdf.cell(0, 6, "Defects", ln=True)
            pdf.set_font("DejaVu", "", 9)
            for item in items:
                line = " | ".join(f"{k}: {v}" for k, v in item.items())
                pdf.cell(0, 5, f"  * {line}", ln=True)

    out_path = config.REPORTS_DIR / f"{record['id']}.pdf"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out_path))
    return out_path
