"""ImageFolderSourceNode — iterates a folder of images through a pipeline."""
from __future__ import annotations
import threading
import time
import logging
from pathlib import Path
import numpy as np
from core.nodes.base import SourceNode, NodeMeta
from core.nodes.registry import NodeRegistry
from core.frame import Frame

log = logging.getLogger(__name__)

_IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@NodeRegistry.register
class ImageFolderSourceNode(SourceNode):
    META = NodeMeta(
        node_type="image_folder_source",
        label="Image Folder",
        category="source",
        icon="🗂",
        vram_mb=0,
        config_schema={
            "type": "object",
            "required": ["path"],
            "properties": {
                "path":     {"type": "string", "title": "Folder Path"},
                "interval": {"type": "number", "title": "Interval (s)", "default": 1.0,
                             "description": "Seconds between frames"},
                "loop":     {"type": "boolean", "title": "Loop", "default": False},
            },
        },
    )

    def __init__(self, config: dict, ctx: "ExecutionContext") -> None:
        super().__init__(config, ctx)
        self._path = Path(config["path"])
        self._interval: float = float(config.get("interval", 1.0))
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
        while not self._stop.is_set():
            images = sorted(p for p in self._path.iterdir() if p.suffix.lower() in _IMG_EXTS)
            if not images:
                log.warning("[image_folder] no images found in %s", self._path)
                return
            log.info("[image_folder] %d images in %s", len(images), self._path)
            for img_path in images:
                if self._stop.is_set():
                    return
                img = cv2.imread(str(img_path))
                if img is None:
                    log.warning("[image_folder] failed to read %s", img_path)
                    continue
                frame = Frame(image=img, source_id=str(img_path))
                with self._lock:
                    self._frame = frame
                    self._frame_time = time.monotonic()
                time.sleep(self._interval)
            if not self._loop:
                log.info("[image_folder] done: %s", self._path)
                return


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.graph import ExecutionContext
