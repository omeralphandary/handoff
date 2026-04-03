"""Task-specific VLM prompts."""

_IGNORE = "Ignore camera OSD, timestamps, watermarks, and brand text. Describe only physical objects and conditions."

DOCUMENTATION_PROMPT = """Freight condition and safety inspector.

Score condition 1-5: 5=no damage, 4=cosmetic only, 3=moderate (dents/tears/wet), 2=significant (seams broken/contents at risk), 1=severe (contents exposed). Normal creases and scuffs are NOT damage.

Also assess: is each object stable or at risk of tipping/falling? Any hazards (fire, smoke, spill, unsafe stacking)?

JSON only:
{"condition_score":int,"passed":bool,"damage_items":[{"location":str,"type":str,"severity":"minor|moderate|severe"}],"safety_status":"stable|at_risk|unsafe","safety_notes":[{"object":str,"issue":str,"severity":"low|medium|high"}],"hazards":[{"type":str,"severity":"low|medium|high"}],"summary":str}

passed=true when score>=4, safety_status=stable, no hazards. If passed, damage_items/safety_notes/hazards=[], omit summary."""

OCR_PROMPT = f"""Read all text, labels, and codes on physical objects. {_IGNORE}

JSON only:
{{"texts":[str],"barcodes":[str],"identifiers":[{{"label":str,"value":str}}],"summary":str}}"""

INSPECTION_PROMPT = """Inspect for anomalies and safety issues.

Check: object stability (tipping/falling?), structural integrity, hazards (fire/smoke/spill/unsafe stacking), displaced or missing items. Ignore minor lighting changes.

JSON only:
{"anomaly_detected":bool,"safety_status":"stable|at_risk|unsafe","anomalies":[{"description":str,"severity":"low|medium|high","location":str}],"summary":str}

Omit summary if anomaly_detected=false and safety_status=stable."""

CLASSIFICATION_PROMPT = """Identify primary cargo type.

Types: pallet_wrapped, pallet_open, single_box, container, bag, drum, mixed, empty, unknown.

JSON only:
{"cargo_type":str,"confidence":"high|medium|low","count":int|null,"notes":str}"""
