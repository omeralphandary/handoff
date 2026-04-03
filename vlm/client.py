"""VLM client — factory that returns local (Ollama), Anthropic, or hybrid backend."""
from __future__ import annotations
import re
import base64
import json
import asyncio
import logging
from functools import partial
from abc import ABC, abstractmethod

import cv2
import httpx
import numpy as np

import config

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _encode_frame(frame: np.ndarray) -> bytes:
    blurred = cv2.GaussianBlur(frame, (0, 0), 3)
    sharpened = cv2.addWeighted(frame, 1.5, blurred, -0.5, 0)
    _, buf = cv2.imencode(".jpg", sharpened, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return buf.tobytes()


async def _waiting_ticker(model: str) -> None:
    """Log every 5 s while inference is in progress."""
    elapsed = 0
    while True:
        await asyncio.sleep(5)
        elapsed += 5
        log.info("[vlm] still waiting for %s (%ds elapsed)", model, elapsed)


def _parse_json(text: str) -> dict:
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return {"raw": text, "parse_error": True}
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return {"raw": text, "parse_error": True}


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class BaseVLMClient(ABC):
    @abstractmethod
    async def analyze(self, frame: np.ndarray, prompt: str) -> dict: ...


# ---------------------------------------------------------------------------
# Local backend — Ollama (Qwen2-VL or LLaVA)
# ---------------------------------------------------------------------------

class LocalVLMClient(BaseVLMClient):
    """Sends frames to a local Ollama instance. Zero API cost, runs on GPU."""

    def __init__(self) -> None:
        self._url = f"{config.OLLAMA_URL}/api/chat"
        self._model = config.LOCAL_MODEL

    async def analyze(self, frame: np.ndarray, prompt: str) -> dict:
        image_bytes = _encode_frame(frame)
        b64 = base64.b64encode(image_bytes).decode()
        payload = {
            "model": self._model,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [b64],
                }
            ],
        }
        log.info("[vlm] local inference started — waiting for %s", self._model)
        ticker = asyncio.create_task(_waiting_ticker(self._model))
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(self._url, json=payload)
                response.raise_for_status()
        finally:
            ticker.cancel()
        log.info("[vlm] local inference complete")
        text = response.json()["message"]["content"]
        result = _parse_json(text)
        result["_model"] = self._model
        return result


# ---------------------------------------------------------------------------
# Anthropic backend — Claude Vision
# ---------------------------------------------------------------------------

class AnthropicVLMClient(BaseVLMClient):
    """Calls Anthropic Claude Vision API. Swap in before MVP."""

    def __init__(self) -> None:
        import anthropic
        self._client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    async def analyze(self, frame: np.ndarray, prompt: str) -> dict:
        image_bytes = _encode_frame(frame)
        log.info("[vlm] anthropic inference started — waiting for %s", config.VLM_MODEL)
        ticker = asyncio.create_task(_waiting_ticker(config.VLM_MODEL))
        try:
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(
                None, partial(self._call, image_bytes, prompt)
            )
        finally:
            ticker.cancel()
        log.info("[vlm] anthropic inference complete")
        result = _parse_json(text)
        result["_model"] = config.VLM_MODEL
        return result

    def _call(self, image_bytes: bytes, prompt: str) -> str:
        b64 = base64.b64encode(image_bytes).decode()
        msg = self._client.messages.create(
            model=config.VLM_MODEL,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        return msg.content[0].text


# ---------------------------------------------------------------------------
# Hybrid backend — local first, Anthropic fallback on low confidence
# ---------------------------------------------------------------------------

def _is_low_confidence(result: dict) -> bool:
    """Return True if the local result looks unreliable."""
    if result.get("parse_error"):
        return True
    if result.get("confidence") == "low":
        return True
    return False


class HybridVLMClient(BaseVLMClient):
    """Run Qwen2-VL locally; fall back to Anthropic when confidence is low or JSON parse fails."""

    def __init__(self) -> None:
        self._local = LocalVLMClient()
        self._remote = AnthropicVLMClient()

    async def analyze(self, frame: np.ndarray, prompt: str) -> dict:
        try:
            result = await self._local.analyze(frame, prompt)
        except Exception as e:
            log.warning("[vlm] local backend failed (%s) — falling back to %s", type(e).__name__, config.VLM_MODEL)
            result = await self._remote.analyze(frame, prompt)
            result["_backend"] = "anthropic_fallback"
            return result
        if _is_low_confidence(result):
            log.info("[vlm] local low-confidence — falling back to %s", config.VLM_MODEL)
            result = await self._remote.analyze(frame, prompt)
            result["_backend"] = "anthropic"
        else:
            result["_backend"] = "local"
        return result


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_vlm_client() -> BaseVLMClient:
    if config.VLM_BACKEND == "anthropic":
        return AnthropicVLMClient()
    if config.VLM_BACKEND == "hybrid":
        return HybridVLMClient()
    return LocalVLMClient()


# Default instance — import this everywhere
VLMClient = get_vlm_client
