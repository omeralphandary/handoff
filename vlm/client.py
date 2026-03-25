"""VLM abstraction — Claude Vision backend."""
from __future__ import annotations
import re
import base64
import json
import asyncio
from functools import partial
import cv2
import numpy as np
import anthropic
import config


class VLMClient:
    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    async def analyze(self, frame: np.ndarray, prompt: str) -> dict:
        """Encode frame and send to VLM. Returns parsed JSON dict."""
        image_bytes = self._encode(frame)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None, partial(self._call, image_bytes, prompt)
        )
        return self._parse(response)

    def _encode(self, frame: np.ndarray) -> bytes:
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        return buf.tobytes()

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

    def _parse(self, text: str) -> dict:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return {"raw": text, "parse_error": True}
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return {"raw": text, "parse_error": True}
