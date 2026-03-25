"""PDF evidence report generator."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime
from fpdf import FPDF
import config


def generate_pdf(record: dict) -> Path:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Handoff — Evidence Report", ln=True)

    pdf.set_font("Helvetica", "", 10)
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

    # Result summary
    result = record.get("result", {})
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Analysis", ln=True)
    pdf.set_font("Helvetica", "", 10)

    summary = result.get("summary", "—")
    pdf.multi_cell(0, 6, summary)
    pdf.ln(2)

    # Damage items if present
    items = result.get("damage_items", []) or result.get("anomalies", [])
    if items:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, "Items", ln=True)
        pdf.set_font("Helvetica", "", 9)
        for item in items:
            line = " | ".join(f"{k}: {v}" for k, v in item.items())
            pdf.cell(0, 5, f"  • {line}", ln=True)

    out_path = config.REPORTS_DIR / f"{record['id']}.pdf"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out_path))
    return out_path
