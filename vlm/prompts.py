"""Task-specific VLM prompts."""

DOCUMENTATION_PROMPT = """Inspect this image for freight/cargo/package damage or condition issues.

Return valid JSON only, no other text:
{
  "damage_detected": bool,
  "overall_condition": "good" | "fair" | "poor",
  "damage_items": [
    {"location": str, "type": str, "severity": "minor" | "moderate" | "severe"}
  ],
  "summary": str
}"""

OCR_PROMPT = """Read all visible text, labels, barcodes, and identifiers in this image.

Return valid JSON only, no other text:
{
  "texts": [str],
  "barcodes": [str],
  "identifiers": [{"label": str, "value": str}],
  "summary": str
}"""

INSPECTION_PROMPT = """Inspect this image for anomalies, safety issues, or changes from expected state.

Return valid JSON only, no other text:
{
  "anomaly_detected": bool,
  "anomalies": [
    {"description": str, "severity": "low" | "medium" | "high", "location": str}
  ],
  "summary": str
}"""
