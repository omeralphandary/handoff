"""GeminiInferenceNode — Google Gemini Vision backend."""
from __future__ import annotations
import asyncio
import base64
import logging
import re
import json
from functools import partial
from core.nodes.base import BaseNode, NodeMeta
from core.nodes.registry import NodeRegistry
from core.frame import Frame
from vlm.prompts import DOCUMENTATION_PROMPT, OCR_PROMPT, CLASSIFICATION_PROMPT

log = logging.getLogger(__name__)

_PROMPT_MAP = {
    "documentation": DOCUMENTATION_PROMPT,
    "ocr":           OCR_PROMPT,
    "classification": CLASSIFICATION_PROMPT,
}


@NodeRegistry.register
class GeminiInferenceNode(BaseNode):
    META = NodeMeta(
        node_type="gemini_inference",
        label="Gemini Vision",
        category="inference",
        icon="gemini",
        vram_mb=0,
        config_schema={
            "type": "object",
            "properties": {
                "task_types": {
                    "type": "array",
                    "title": "Task Types",
                    "items": {"type": "string", "enum": ["documentation", "ocr", "classification"]},
                    "default": ["documentation"],
                },
                "model": {
                    "type": "string",
                    "title": "Model",
                    "default": "gemini-2.0-flash",
                    "description": "Gemini model ID",
                },
                "custom_prompt": {"type": "string", "title": "Custom Prompt"},
            },
        },
    )

    def __init__(self, config: dict, ctx: "ExecutionContext") -> None:
        super().__init__(config, ctx)
        if "task_types" in config and isinstance(config["task_types"], list):
            self._task_types = config["task_types"] or ["documentation"]
        else:
            self._task_types = [config.get("task_type", "documentation")]
        self._model: str = config.get("model", "gemini-2.0-flash")
        override: str | None = config.get("custom_prompt")
        self._prompts = {t: override or _PROMPT_MAP.get(t, DOCUMENTATION_PROMPT) for t in self._task_types}
        self._client = None

    async def setup(self) -> None:
        try:
            import google.generativeai as genai
            import config as cfg
            api_key = getattr(cfg, "GEMINI_API_KEY", "")
            if not api_key:
                raise RuntimeError("GEMINI_API_KEY not set in config/.env")
            genai.configure(api_key=api_key)
            self._genai = genai
            log.info("[gemini] configured with model %s", self._model)
        except ImportError:
            raise RuntimeError("google-generativeai not installed — run: pip install google-generativeai")

    async def process(self, frame: Frame) -> Frame | None:
        import cv2
        _, buf = cv2.imencode(".jpg", frame.image, [cv2.IMWRITE_JPEG_QUALITY, 90])
        image_bytes = buf.tobytes()
        loop = asyncio.get_event_loop()

        results: dict = {}
        for task_type in self._task_types:
            log.info("[gemini] %s on capture %s", task_type, frame.capture_id[:8])
            text = await loop.run_in_executor(None, partial(self._call, image_bytes, self._prompts[task_type]))
            r = self._parse(text)
            r["_model"] = self._model
            r["_backend"] = "gemini"
            results[task_type] = r

        combined = results[self._task_types[0]] if len(results) == 1 else results
        return frame.with_meta(
            inference_result=combined,
            inference_results=results,
            task_type=self._task_types[0],
            task_types=self._task_types,
        )

    def _call(self, image_bytes: bytes, prompt: str) -> str:
        import PIL.Image, io
        img = PIL.Image.open(io.BytesIO(image_bytes))
        model = self._genai.GenerativeModel(self._model)
        response = model.generate_content([prompt, img])
        return response.text

    @staticmethod
    def _parse(text: str) -> dict:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return {"raw": text, "parse_error": True}
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return {"raw": text, "parse_error": True}


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.graph import ExecutionContext
