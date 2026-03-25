"""Per-zone loop: reads frames, checks motion, dispatches to task."""
from __future__ import annotations
import asyncio
import cv2
import numpy as np
from core.camera import CameraStream
from core.motion import MotionTrigger
from core.zone import Zone
from tasks.base import BaseTask


class ZoneDispatcher:
    def __init__(self, zone: Zone, task: BaseTask) -> None:
        self.zone = zone
        self.task = task
        self._stream = CameraStream(zone.camera_url)
        self._trigger = MotionTrigger(cooldown_seconds=zone.cooldown_seconds)

    async def run(self) -> None:
        self._stream.start()
        try:
            while True:
                frame = self._stream.latest_frame()
                if frame is not None:
                    cropped = self.zone.crop(frame)
                    if self._trigger.check(cropped):
                        await self.task.run(cropped, self.zone)
                await asyncio.sleep(0.5)
        finally:
            self._stream.stop()
