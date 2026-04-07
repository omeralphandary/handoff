"""S3SinkNode — uploads image + result JSON to S3-compatible object storage."""
from __future__ import annotations
import json
import logging
import cv2
from core.nodes.base import BaseNode, NodeMeta
from core.nodes.registry import NodeRegistry
from core.frame import Frame

log = logging.getLogger(__name__)


@NodeRegistry.register
class S3SinkNode(BaseNode):
    META = NodeMeta(
        node_type="s3_sink",
        label="S3 / Object Storage",
        category="sink",
        icon="☁",
        vram_mb=0,
        config_schema={
            "type": "object",
            "required": ["bucket"],
            "properties": {
                "bucket":       {"type": "string", "title": "Bucket Name"},
                "prefix":       {"type": "string", "title": "Key Prefix", "default": "oversight/},
                "endpoint_url": {
                    "type": "string",
                    "title": "Endpoint URL",
                    "description": "For MinIO / R2 / custom S3. Leave empty for AWS.",
                },
                "region":       {"type": "string", "title": "Region", "default": "us-east-1"},
                "access_key":   {"type": "string", "title": "Access Key ID"},
                "secret_key":   {"type": "string", "title": "Secret Access Key"},
            },
        },
    )

    def __init__(self, config: dict, ctx: "ExecutionContext") -> None:
        super().__init__(config, ctx)
        self._bucket: str = config["bucket"]
        self._prefix: str = config.get("prefix", "oversight/)
        self._endpoint: str | None = config.get("endpoint_url") or None
        self._region: str = config.get("region", "us-east-1")
        self._access_key: str = config.get("access_key", "")
        self._secret_key: str = config.get("secret_key", "")
        self._s3 = None

    async def setup(self) -> None:
        try:
            import boto3
            kwargs: dict = {
                "region_name": self._region,
            }
            if self._access_key and self._secret_key:
                kwargs["aws_access_key_id"] = self._access_key
                kwargs["aws_secret_access_key"] = self._secret_key
            if self._endpoint:
                kwargs["endpoint_url"] = self._endpoint
            self._s3 = boto3.client("s3", **kwargs)
            log.info("[s3] connected to bucket %s", self._bucket)
        except ImportError:
            raise RuntimeError("boto3 not installed — run: pip install boto3")

    async def process(self, frame: Frame) -> Frame | None:
        import asyncio
        if self._s3 is None:
            return frame

        cid = frame.capture_id
        _, buf = cv2.imencode(".jpg", frame.image, [cv2.IMWRITE_JPEG_QUALITY, 90])
        image_bytes = buf.tobytes()
        result = frame.metadata.get("inference_result", {})

        img_key = f"{self._prefix}{cid}.jpg"
        json_key = f"{self._prefix}{cid}.json"

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, lambda: self._s3.put_object(
                Bucket=self._bucket, Key=img_key, Body=image_bytes, ContentType="image/jpeg"
            ))
            await loop.run_in_executor(None, lambda: self._s3.put_object(
                Bucket=self._bucket, Key=json_key,
                Body=json.dumps(result).encode(), ContentType="application/json"
            ))
            log.info("[s3] uploaded %s → s3://%s/%s", cid[:8], self._bucket, img_key)
        except Exception as e:
            log.warning("[s3] upload failed for %s: %s", cid[:8], e)

        return frame


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.graph import ExecutionContext
