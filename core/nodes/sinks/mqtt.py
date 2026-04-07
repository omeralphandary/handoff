"""MQTTSinkNode — publishes inference result to an MQTT broker (IoT/PLC integration)."""
from __future__ import annotations
import json
import logging
from core.nodes.base import BaseNode, NodeMeta
from core.nodes.registry import NodeRegistry
from core.frame import Frame

log = logging.getLogger(__name__)


@NodeRegistry.register
class MQTTSinkNode(BaseNode):
    META = NodeMeta(
        node_type="mqtt_sink",
        label="MQTT Publish",
        category="sink",
        icon="📡",
        vram_mb=0,
        config_schema={
            "type": "object",
            "required": ["host", "topic"],
            "properties": {
                "host":     {"type": "string", "title": "Broker Host"},
                "port":     {"type": "integer", "title": "Port", "default": 1883},
                "topic":    {"type": "string", "title": "Topic", "default": "oversight/events"},
                "username": {"type": "string", "title": "Username"},
                "password": {"type": "string", "title": "Password"},
                "qos":      {"type": "integer", "title": "QoS", "default": 1, "enum": [0, 1, 2]},
            },
        },
    )

    def __init__(self, config: dict, ctx: "ExecutionContext") -> None:
        super().__init__(config, ctx)
        self._host: str = config["host"]
        self._port: int = int(config.get("port", 1883))
        self._topic: str = config.get("topic", "oversight/events")
        self._username: str = config.get("username", "")
        self._password: str = config.get("password", "")
        self._qos: int = int(config.get("qos", 1))
        self._client = None

    async def setup(self) -> None:
        try:
            import paho.mqtt.client as mqtt
            client = mqtt.Client()
            if self._username:
                client.username_pw_set(self._username, self._password)
            client.connect(self._host, self._port, keepalive=60)
            client.loop_start()
            self._client = client
            log.info("[mqtt] connected to %s:%d", self._host, self._port)
        except ImportError:
            raise RuntimeError("paho-mqtt not installed — run: pip install paho-mqtt")

    async def teardown(self) -> None:
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()

    async def process(self, frame: Frame) -> Frame | None:
        if self._client is None:
            return frame
        payload = {
            "capture_id": frame.capture_id,
            "zone_id":    self.ctx.zone.id,
            "zone_name":  self.ctx.zone.name,
            "timestamp":  frame.timestamp,
            "result":     frame.metadata.get("inference_result"),
            "task_type":  frame.metadata.get("task_type"),
        }
        self._client.publish(self._topic, json.dumps(payload), qos=self._qos)
        log.debug("[mqtt] published capture %s to %s", frame.capture_id[:8], self._topic)
        return frame


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.graph import ExecutionContext
