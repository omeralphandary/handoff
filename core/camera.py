"""RTSP stream reader — yields frames on demand."""
from __future__ import annotations
import time
import threading
import cv2
import numpy as np


class CameraStream:
    """
    Connects to an RTSP stream and keeps the latest frame in memory.
    Runs a background thread so the buffer never stales.
    """

    def __init__(self, url: str, fps_limit: float = 2.0) -> None:
        self.url = url
        self.fps_limit = fps_limit
        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._read_loop, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)

    def latest_frame(self) -> np.ndarray | None:
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    def _read_loop(self) -> None:
        interval = 1.0 / self.fps_limit
        while not self._stop.is_set():
            cap = cv2.VideoCapture(self.url)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if not cap.isOpened():
                print(f"[camera] cannot open {self.url} — retrying in 5s")
                time.sleep(5)
                continue
            while not self._stop.is_set():
                ret, frame = cap.read()
                if not ret:
                    print("[camera] stream lost — reconnecting")
                    break
                with self._lock:
                    self._frame = frame
                time.sleep(interval)
            cap.release()
