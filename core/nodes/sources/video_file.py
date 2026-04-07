"""VideoFileSourceNode — feeds a local video file through a pipeline."""
from __future__ import annotations
import threading
import time
import logging
import numpy as np
from core.nodes.base import SourceNode, NodeMeta
from core.nodes.registry import NodeRegistry
from core.frame import Frame

log = logging.getLogger(__name__)


@NodeRegistry.register
class VideoFileSourceNode(SourceNode):
    META = NodeMeta(
        node_type="video_file_source",
        label="Video File",
        category="source",
        icon="🎬",
        vram_mb=0,
        config_schema={
            "type": "object",
            "required": ["path"],
            "properties": {
                "path":   {"type": "string", "title": "File Path", "description": "Absolute path to MP4/AVI/MKV"},
                "fps":    {"type": "number", "title": "Playback FPS", "default": 10},
                "loop":   {"type": "boolean", "title": "Loop", "default": False},
            },
        },
    )

    def __init__(self, config: dict, ctx: "ExecutionContext") -> None:
        super().__init__(config, ctx)
        self._path: str = config["path"]
        self._fps: float = float(config.get("fps", 10.0))
        self._loop: bool = bool(config.get("loop", False))
        self._frame: Frame | None = None
        self._frame_time: float = 0.0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._read_loop, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)

    def latest_frame(self) -> Frame | None:
        with self._lock:
            return self._frame

    @property
    def last_frame_time(self) -> float:
        return self._frame_time

    def _read_loop(self) -> None:
        import cv2
        interval = 1.0 / self._fps
        while not self._stop.is_set():
            cap = cv2.VideoCapture(self._path)
            if not cap.isOpened():
                log.error("[video_file] cannot open: %s", self._path)
                return
            log.info("[video_file] opened %s", self._path)
            while not self._stop.is_set():
                ret, img = cap.read()
                if not ret:
                    break
                frame = Frame(image=img, source_id=self._path)
                with self._lock:
                    self._frame = frame
                    self._frame_time = time.monotonic()
                time.sleep(interval)
            cap.release()
            if not self._loop:
                log.info("[video_file] playback complete: %s", self._path)
                return
            log.info("[video_file] looping: %s", self._path)


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.graph import ExecutionContext
