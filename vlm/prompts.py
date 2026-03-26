"""Task-specific VLM prompts."""

DOCUMENTATION_PROMPT = """You are a freight condition inspector. Score the package condition on a 1-5 scale.

Scoring rubric — be strict about what counts as damage:
  5 = PASS. No damage. Normal cardboard appearance, minor manufacturing creases, slight
      discoloration, small scuffs from normal handling. These are NOT damage.
  4 = Minor cosmetic marks that do not affect structural integrity or contents.
      Small surface scratches, light dirt, very shallow dents on non-load-bearing areas.
  3 = Moderate damage. Visible dents, tears, or deformation that may affect contents.
      Crushed corners with structural compromise, punctures, wet spots.
  2 = Significant damage. Large tears, heavy crushing, broken seams, contents visible or at risk.
  1 = Severe. Contents exposed, package structurally failed.

Important: do NOT penalise normal cardboard texture, print wear, minor fold lines from
manufacturing, or light surface marks. Only flag genuine damage that would concern a
freight receiver or create a liability dispute.

Return valid JSON only, no other text:
{
  "condition_score": <integer 1-5>,
  "passed": <true if score is 5, false otherwise>,
  "damage_items": [
    {"location": <str>, "type": <str>, "severity": "minor" | "moderate" | "severe"}
  ],
  "summary": <str describing defects — omit this field entirely if passed is true>
}

If passed is true, damage_items must be an empty array."""

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
