"""RTSP stream reader — yields frames on demand."""
from __future__ import annotations
import subprocess
import time
import threading
import logging
import numpy as np

log = logging.getLogger(__name__)


class CameraStream:
    """
    Connects to an RTSP stream via FFmpeg subprocess and keeps the latest frame in memory.
    Uses FFmpeg directly to handle H.265/HEVC streams that OpenCV struggles with.
    """

    def __init__(self, url: str, fps_limit: float = 10.0) -> None:
        self.url = url
        self.fps_limit = fps_limit
        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._proc: subprocess.Popen | None = None
        self._proc_lock = threading.Lock()
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._width: int = 0
        self._height: int = 0
        self._connected_at: float | None = None
        self._disconnect_count: int = 0

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._kill_proc()
        self._thread.join(timeout=5)

    def reconnect(self) -> None:
        """Terminate the current FFmpeg process — _read_loop restarts it automatically."""
        log.info("[camera] manual reconnect requested")
        self._kill_proc()

    def _kill_proc(self) -> None:
        with self._proc_lock:
            if self._proc is not None:
                self._proc.terminate()

    def latest_frame(self) -> np.ndarray | None:
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    def _get_dimensions(self) -> tuple[int, int]:
        """Probe stream dimensions via ffprobe."""
        cmd = [
            "ffprobe", "-v", "error",
            "-rtsp_transport", "tcp",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
            self.url,
        ]
        try:
            out = subprocess.check_output(cmd, timeout=10, stderr=subprocess.DEVNULL)
            w, h = out.decode().strip().split(",")
            return int(w), int(h)
        except Exception:
            log.warning("[camera] ffprobe failed — using fallback 1920x1080")
            return 1920, 1080

    def _read_loop(self) -> None:
        interval = 1.0 / self.fps_limit
        while not self._stop.is_set():
            log.info("[camera] probing stream dimensions...")
            w, h = self._get_dimensions()
            frame_size = w * h * 3
            cmd = [
                "ffmpeg", "-loglevel", "error",
                "-rtsp_transport", "tcp",
                "-fflags", "+discardcorrupt+nobuffer",
                "-flags", "low_delay",
                "-err_detect", "ignore_err",
                "-i", self.url,
                "-vf", f"fps={self.fps_limit}",
                "-f", "rawvideo",
                "-pix_fmt", "bgr24",
                "pipe:1",
            ]
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except FileNotFoundError:
                log.error("[camera] ffmpeg not found — install with: sudo apt install ffmpeg")
                time.sleep(10)
                continue

            with self._proc_lock:
                self._proc = proc

            self._connected_at = time.time()
            log.info("[camera] connected — %s (%dx%d) [disconnects so far: %d]",
                     self.url, w, h, self._disconnect_count)

            frames_read = 0
            try:
                while not self._stop.is_set():
                    raw = proc.stdout.read(frame_size)
                    if len(raw) < frame_size:
                        duration = time.time() - self._connected_at if self._connected_at else 0
                        self._disconnect_count += 1
                        stderr_out = proc.stderr.read(2048).decode(errors="replace").strip()
                        log.warning(
                            "[camera] stream lost after %.1fs (%d frames) — disconnect #%d%s",
                            duration, frames_read, self._disconnect_count,
                            f" | ffmpeg: {stderr_out}" if stderr_out else "",
                        )
                        break
                    frame = np.frombuffer(raw, dtype=np.uint8).reshape((h, w, 3))
                    with self._lock:
                        self._frame = frame.copy()
                    frames_read += 1
                    time.sleep(interval)
            finally:
                proc.terminate()
                proc.wait()
                with self._proc_lock:
                    self._proc = None

            if not self._stop.is_set():
                log.info("[camera] reconnecting in 2s...")
                time.sleep(2)
