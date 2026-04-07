# Oversight — Future Roadmap & Ideas

Ideas captured from product sessions. Not prioritized — use this as a thinking board.

---

## GenAI Features

### Agentic Dispute Resolution
When a claim is filed, an agent automatically builds the evidence case:
- Search all records by carrier / tracking number / timeframe
- Pull relevant images, condition scores, timestamps
- Generate a formal dispute brief as PDF: timeline, evidence photos, liability assessment
- Example output: "Package arrived condition 4/5 at 14:22. Departed 2/5 at 16:45. Damage occurred in carrier custody."

**Why it matters:** Disputes currently take hours of manual searching. This makes it a 10-second button.
**How to build:** Claude agent with `tool_use` calling SQLite records. Straightforward.
**Build when:** Phase 2 — highest emotional value, easiest to demo.

---

### Natural Language Evidence Search
Let any user query the evidence database in plain English:
- "Show me all corner crush damage from Carrier X in the last 30 days"
- "Which zone has the highest damage rate on Friday afternoons?"

**How to build:** NL → SQL via Claude, execute against SQLite, return records with image thumbnails.
**Build when:** Phase 2, after dispute brief.

---

### Anomaly Narrative Generation
Instead of `anomaly_detected: true`, produce a human-readable explanation with context:
> "Zone B shows an untagged pallet not present in the 09:00 baseline. The previous 4 captures (08:00–09:00) show normal state. Item appears to be a brown cardboard box, approximately 60x40cm."

**How to build:** Pass recent record history + current frame to VLM in a single prompt. Already have all the data.
**Build when:** Phase 2, small lift on top of existing inspection task.

---

### Smart Manifest Linking
OCR task reads tracking numbers from labels. Connect to BOL/manifest upload or TMS webhook to auto-link visual evidence to shipment records. Carriers can't dispute damage photographed and linked to their signed manifest.

**Build when:** Phase 2, requires integration work with customer TMS.

---

## Predictive Maintenance (PdM)

### Carrier / Route Risk Scoring
After 6+ months of data: carrier × route × day/time × cargo type → damage outcome.
Train a gradient boosted model (doesn't need to be GenAI) on historical records.
Output: pre-arrival risk score per incoming shipment.

> "Incoming load from Carrier X, Friday 17:00 route: 38% historical damage probability. Recommend increased scrutiny at receiving."

**Data needed:** Carrier ID on zone/record entries — start collecting this now.
**Build when:** Phase 2 data collection → Phase 3 model training. Need 6+ months of records.

---

### Zone / Environment Drift Detection
Inspection baselines already track visual state. Extend: if a baseline updates frequently with small changes, something is gradually changing — equipment wear, lighting, accumulation.

> "Zone C baseline has drifted 12% over the past 3 weeks — progressive change, not a single event. Review recommended."

**How to build:** Track baseline diff history per zone over time. Flag sustained drift vs sudden events.
**Build when:** Phase 2, low effort extension of existing inspection task.

---

### Camera Health Monitoring
Reuse inspection diff logic to detect camera degradation: increasing blur, color shift, lens occlusion.

> "Zone A image quality degraded 30% over 5 days — possible lens contamination or repositioning needed."

**Build when:** Phase 2. Piggybacks on existing baseline infrastructure.

---

## Phase 3 / Moat Ideas

### Fine-tuned VLM per customer
General VLMs generalize across everything. A model trained on "this customer ships refrigeration units" will hit 95%+ accuracy vs 82% for a general model.

Pipeline:
1. Accumulate labeled records (human review of VLM outputs)
2. QLoRA fine-tune on Qwen2-VL-7B or InternVL2-8B
3. Convert to GGUF → push to Ollama → update LOCAL_MODEL
4. Retrain every 3-6 months on accumulated data

**Build when:** Phase 3, after 500-1000 labeled records per task type per customer.

---

### Predictive + Prescriptive Full Loop
The complete differentiated product:
- **Before** truck arrives: risk score based on carrier history
- **During** handoff: real-time capture + structured extraction + anomaly detection
- **After** a problem: auto-generated dispute brief with full evidence chain
- **Over time**: trend reports showing which carriers/routes/times are systematically problematic

No competitor connects all four. Individual pieces exist (dashcams, WMS notes, carrier scorecards) — none are tied to visual AI evidence.

---

### Compliance Packages
Vertical-specific alert rules and report templates:
- **Cold chain**: temperature sensor + visual check + deviation alert
- **Pharma GDP**: tamper evidence, seal integrity, humidity exposure
- **Hazmat**: placard verification, containment inspection
- **Food safety**: packaging integrity, contamination detection

---

### Mobile Companion
Driver-side capture on mobile that merges with fixed camera records. Full chain of custody without requiring cameras at every point. Useful for last-mile and pickup points where fixed cameras aren't viable.

---

## Notes

- The data flywheel is the moat. After 12 months multi-tenant, Oversight will have the largest labeled dataset of logistics handoff footage in existence.
- Start collecting carrier ID on records immediately — it unlocks risk scoring later.
- Build dispute brief first. Highest emotional value, easiest sales story: "When a carrier disputes damage, we generate the evidence brief automatically."
