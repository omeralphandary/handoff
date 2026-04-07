"""CustomPromptNode — user-defined prompt, any VLM backend, free-text or JSON output."""
from __future__ import annotations
import logging
from core.nodes.base import BaseNode, NodeMeta
from core.nodes.registry import NodeRegistry
from core.frame import Frame

log = logging.getLogger(__name__)


@NodeRegistry.register
class CustomPromptNode(BaseNode):
    META = NodeMeta(
        node_type="custom_prompt",
        label="Custom Prompt",
        category="inference",
        icon="✏️",
        vram_mb=0,
        config_schema={
            "type": "object",
            "required": ["prompt"],
            "properties": {
                "prompt": {
                    "type": "string",
                    "title": "Prompt",
                    "description": "Sent directly to the VLM. Append 'Respond in JSON.' to get structured output.",
                },
                "backend": {
                    "type": "string",
                    "title": "Backend",
                    "enum": ["anthropic", "ollama", "gemini"],
                    "default": "anthropic",
                },
                "task_label": {
                    "type": "string",
                    "title": "Task Label",
                    "default": "custom",
                    "description": "Used as task_type in the evidence record",
                },
            },
        },
    )

    def __init__(self, config: dict, ctx: "ExecutionContext") -> None:
        super().__init__(config, ctx)
        self._prompt: str = config["prompt"]
        self._backend: str = config.get("backend", "anthropic")
        self._task_label: str = config.get("task_label", "custom")

    async def setup(self) -> None:
        if self._backend == "anthropic":
            from vlm.client import AnthropicVLMClient
            self._vlm = AnthropicVLMClient()
        elif self._backend == "ollama":
            from vlm.client import LocalVLMClient
            self._vlm = LocalVLMClient()
        elif self._backend == "gemini":
            # Reuse GeminiInferenceNode's client setup inline
            try:
                import google.generativeai as genai
                import config as cfg
                genai.configure(api_key=cfg.GEMINI_API_KEY)
                self._genai = genai
                self._vlm = None  # uses _genai directly
            except ImportError:
                raise RuntimeError("google-generativeai not installed")
        else:
            raise ValueError(f"Unknown backend: {self._backend!r}")

    async def process(self, frame: Frame) -> Frame | None:
        log.info("[custom_prompt] %s inference on capture %s", self._backend, frame.capture_id[:8])
        if self._vlm is not None:
            result = await self._vlm.analyze(frame.image, self._prompt)
        else:
            result = await self._call_gemini(frame)
        result["_backend"] = self._backend
        return frame.with_meta(inference_result=result, task_type=self._task_label)

    async def _call_gemini(self, frame: Frame) -> dict:
        import asyncio, cv2, re, json, io
        import PIL.Image
        _, buf = cv2.imencode(".jpg", frame.image, [cv2.IMWRITE_JPEG_QUALITY, 90])
        img = PIL.Image.open(io.BytesIO(buf.tobytes()))
        model = self._genai.GenerativeModel("gemini-2.0-flash")
        loop = asyncio.get_event_loop()
        from functools import partial
        text = await loop.run_in_executor(None, partial(model.generate_content, [self._prompt, img]))
        raw = text.text
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        return {"raw": raw}


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.graph import ExecutionContext
