"""VLM inference nodes — Claude (Anthropic) and Ollama backends."""
from __future__ import annotations
import logging
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

_TASK_ENUM = ["documentation", "ocr", "classification"]

_TASK_SCHEMA = {
    "type": "object",
    "properties": {
        "task_types": {
            "type": "array",
            "title": "Task Types",
            "description": "Run inference for each selected type",
            "items": {"type": "string", "enum": _TASK_ENUM},
            "default": ["documentation"],
        },
        "custom_prompt": {
            "type": "string",
            "title": "Custom Prompt",
            "description": "Overrides built-in prompts for all selected task types",
        },
    },
}


def _resolve_task_types(config: dict) -> list[str]:
    """Support both old task_type (str) and new task_types (list)."""
    if "task_types" in config and isinstance(config["task_types"], list):
        return config["task_types"] or ["documentation"]
    if "task_type" in config:
        return [config["task_type"]]
    return ["documentation"]


@NodeRegistry.register
class ClaudeInferenceNode(BaseNode):
    META = NodeMeta(
        node_type="claude_inference",
        label="Claude Vision",
        category="inference",
        icon="claude",
        vram_mb=0,
        config_schema=_TASK_SCHEMA,
    )

    def __init__(self, config: dict, ctx: "ExecutionContext") -> None:
        super().__init__(config, ctx)
        self._task_types = _resolve_task_types(config)
        override: str | None = config.get("custom_prompt")
        self._prompts = {
            t: override or _PROMPT_MAP.get(t, DOCUMENTATION_PROMPT)
            for t in self._task_types
        }

    async def setup(self) -> None:
        from vlm.client import AnthropicVLMClient
        self._vlm = AnthropicVLMClient()

    async def process(self, frame: Frame) -> Frame | None:
        results: dict[str, str] = {}
        for task_type in self._task_types:
            log.info("[claude] %s on capture %s", task_type, frame.capture_id[:8])
            results[task_type] = await self._vlm.analyze(frame.image, self._prompts[task_type])

        combined = "\n\n".join(
            f"[{t.upper()}]\n{r}" for t, r in results.items()
        ) if len(results) > 1 else next(iter(results.values()))

        return frame.with_meta(
            inference_result=combined,
            inference_results=results,
            task_type=self._task_types[0],
            task_types=self._task_types,
        )


@NodeRegistry.register
class OllamaInferenceNode(BaseNode):
    META = NodeMeta(
        node_type="ollama_inference",
        label="Ollama (Local VLM)",
        category="inference",
        icon="ollama",
        vram_mb=4096,
        config_schema=_TASK_SCHEMA,
    )

    def __init__(self, config: dict, ctx: "ExecutionContext") -> None:
        super().__init__(config, ctx)
        self._task_types = _resolve_task_types(config)
        override: str | None = config.get("custom_prompt")
        self._prompts = {
            t: override or _PROMPT_MAP.get(t, DOCUMENTATION_PROMPT)
            for t in self._task_types
        }

    async def setup(self) -> None:
        from vlm.client import LocalVLMClient
        self._vlm = LocalVLMClient()

    async def process(self, frame: Frame) -> Frame | None:
        results: dict[str, str] = {}
        for task_type in self._task_types:
            log.info("[ollama] %s on capture %s", task_type, frame.capture_id[:8])
            results[task_type] = await self._vlm.analyze(frame.image, self._prompts[task_type])

        combined = "\n\n".join(
            f"[{t.upper()}]\n{r}" for t, r in results.items()
        ) if len(results) > 1 else next(iter(results.values()))

        return frame.with_meta(
            inference_result=combined,
            inference_results=results,
            task_type=self._task_types[0],
            task_types=self._task_types,
        )


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.graph import ExecutionContext
