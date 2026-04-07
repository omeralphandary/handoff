"""
Test the full pipeline on a static image — no camera needed.

Usage:
    python scripts/test_image.py path/to/image.jpg
    python scripts/test_image.py path/to/image.jpg --task ocr
    python scripts/test_image.py path/to/image.jpg --task inspection
"""
from __future__ import annotations
import sys
import json
import asyncio
import argparse
from pathlib import Path

# Make sure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import config
from vlm.client import get_vlm_client
from vlm.prompts import DOCUMENTATION_PROMPT, OCR_PROMPT, INSPECTION_PROMPT
from reports.pdf import generate_pdf

PROMPTS = {
    "documentation": DOCUMENTATION_PROMPT,
    "ocr": OCR_PROMPT,
    "inspection": INSPECTION_PROMPT,
}


async def run(image_path: Path, task: str) -> None:
    print(f"\n{'='*50}")
    print(f"Image : {image_path}")
    print(f"Task  : {task}")
    print(f"Backend: {config.VLM_BACKEND}")
    if config.VLM_BACKEND == "local":
        print(f"Model : {config.LOCAL_MODEL}")
    else:
        print(f"Model : {config.VLM_MODEL}")
    print(f"{'='*50}\n")

    # Load image
    frame = cv2.imread(str(image_path))
    if frame is None:
        print(f"ERROR: could not load image at {image_path}")
        sys.exit(1)
    print(f"Loaded image: {frame.shape[1]}x{frame.shape[0]}px")

    # Run VLM
    print("Sending to VLM... ", end="", flush=True)
    client = get_vlm_client()
    result = await client.analyze(frame, PROMPTS[task])
    print("done\n")

    # Print result
    print("--- VLM Result ---")
    print(json.dumps(result, indent=2))

    if result.get("parse_error"):
        print("\nWARNING: JSON parse failed — check prompt or model output above")
        return

    # Generate PDF if documentation task
    if task == "documentation":
        # Build a minimal record dict for the PDF generator
        import uuid
        from datetime import datetime
        config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        config.IMAGES_DIR.mkdir(parents=True, exist_ok=True)

        record_id = str(uuid.uuid4())
        image_dest = config.IMAGES_DIR / f"{record_id}.jpg"
        cv2.imwrite(str(image_dest), frame)

        score = result.get("condition_score")
        flagged = (score is not None and score < 5) or result.get("damage_detected", False)
        record = {
            "id": record_id,
            "zone_name": "test-zone",
            "task_type": task,
            "timestamp": datetime.utcnow().isoformat(),
            "flagged": flagged,
            "image_path": str(image_dest),
            "result": result,
        }
        pdf_path = generate_pdf(record)
        print(f"\n--- PDF generated ---")
        print(f"{pdf_path}")

    print(f"\n{'='*50}")
    print("Pipeline test complete.")
    print(f"{'='*50}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Test Oversight pipeline on a static image")
    parser.add_argument("image", type=Path, help="Path to image file")
    parser.add_argument(
        "--task",
        choices=["documentation", "ocr", "inspection"],
        default="documentation",
        help="Task type to run (default: documentation)",
    )
    args = parser.parse_args()

    if not args.image.exists():
        print(f"ERROR: file not found: {args.image}")
        sys.exit(1)

    asyncio.run(run(args.image, args.task))


if __name__ == "__main__":
    main()
