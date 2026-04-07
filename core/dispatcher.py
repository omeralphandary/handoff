"""Per-zone loop: reads frames, checks motion, dispatches to tasks."""
from __future__ import annotations
import asyncio
import logging
import time
from core.camera import CameraStream
from core.motion import MotionTrigger
from core.yolo_gate import YOLOGate
from core.zone import Zone
from tasks.base import BaseTask

log = logging.getLogger(__name__)


class ZoneDispatcher:
    def __init__(self, zone: Zone, tasks: list[BaseTask]) -> None:
        self.zone = zone
        self.tasks = tasks
        self._stream = CameraStream(zone.camera_url)
        self._trigger = MotionTrigger(
            threshold_pct=zone.motion_threshold,
            cooldown_seconds=zone.cooldown_seconds,
        )
        self._last_sequence: float = 0.0
        self.is_inferring: bool = False
        self.last_capture_id: str | None = None
        self._yolo: YOLOGate | None = (
            YOLOGate(zone.trigger_classes) if zone.trigger_classes else None
        )

    async def trigger_now(self) -> bool:
        """Grab the current frame and run all tasks immediately. Returns False if no frame."""
        frame = self._stream.latest_frame()
        if frame is None:
            return False
        cropped = self.zone.crop(frame)
        await self._run_tasks(cropped, "manual")
        return True

    async def _run_tasks(self, cropped, label: str) -> None:
        import uuid as _uuid
        capture_id = str(_uuid.uuid4())
        self.is_inferring = True
        self.last_capture_id = capture_id
        log.info("[dispatcher] %s — running tasks (capture %s)", label, capture_id[:8])
        try:
            for task in self.tasks:
                try:
                    await task.run(cropped, self.zone, capture_id=capture_id)
                    log.info("[dispatcher] task %s done", task.__class__.__name__)
                except Exception:
                    log.exception("Task %s failed for zone %s", task.__class__.__name__, self.zone.name)
        finally:
            self.is_inferring = False

    async def run(self) -> None:
        self._stream.start()
        log.info("Dispatcher started: zone=%s tasks=%s", self.zone.name, [t.__class__.__name__ for t in self.tasks])
        try:
            while True:
                frame = self._stream.latest_frame()
                if frame is not None:
                    cropped = self.zone.crop(frame)
                    now = time.time()

                    if self.zone.trigger_mode == "sequence":
                        if (now - self._last_sequence) >= self.zone.sequence_interval:
                            self._last_sequence = now
                            await self._run_tasks(cropped, "sequence")

                    elif self.zone.trigger_mode == "motion":
                        if self._trigger.check(cropped):
                            await self._run_tasks(cropped, "motion")

                    elif self.zone.trigger_mode == "by_class":
                        # Motion is a cheap pre-filter; cooldown only stamps after class confirmed
                        if self._trigger.in_cooldown():
                            pass  # silent — would be too noisy at 0.5s interval
                        elif self._trigger.has_motion(cropped):
                            log.info("[yolo] motion detected in zone '%s' — running YOLO gate", self.zone.name)
                            loop = asyncio.get_event_loop()
                            matched = await loop.run_in_executor(None, self._yolo.check, cropped)
                            if matched:
                                self._trigger.stamp_cooldown()
                                log.info("[yolo] classes confirmed: %s — triggering inference (zone '%s')", matched, self.zone.name)
                                self.zone._triggered_by = matched
                                await self._run_tasks(cropped, "by_class")
                                self.zone._triggered_by = []
                            else:
                                log.info("[yolo] no target class detected (watching: %s)", sorted(self._yolo.classes))

                    # "manual" — stream stays alive, only trigger_now() fires tasks

                else:
                    log.debug("[dispatcher] no frame yet")
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            log.info("Dispatcher stopping: zone=%s", self.zone.name)
        finally:
            self._stream.stop()
