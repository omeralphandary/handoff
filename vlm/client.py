"""VLM client — factory that returns local (Ollama) or Anthropic backend."""
from __future__ import annotations
import re
import base64
import json
import asyncio
from functools import partial
from abc import ABC, abstractmethod

import cv2
import httpx
import numpy as np

import config


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _encode_frame(frame: np.ndarray) -> bytes:
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return buf.tobytes()


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
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self._url, json=payload)
            response.raise_for_status()
        text = response.json()["message"]["content"]
        return _parse_json(text)


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
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(
            None, partial(self._call, image_bytes, prompt)
        )
        return _parse_json(text)

    def _call(self, image_bytes: bytes, prompt: str) -> str:
        b64 = base64.b64encode(image_bytes).decode()
        msg = self._client.messages.create(
            model=config.VLM_MODEL,
            max_tokens=512,
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
# Factory
# ---------------------------------------------------------------------------

def get_vlm_client() -> BaseVLMClient:
    if config.VLM_BACKEND == "anthropic":
        return AnthropicVLMClient()
    return LocalVLMClient()


# Default instance — import this everywhere
VLMClient = get_vlm_client
