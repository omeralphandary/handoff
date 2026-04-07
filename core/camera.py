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
        self._frame_time: float = 0.0
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

    @property
    def last_frame_time(self) -> float:
        return self._frame_time

    def _get_dimensions(self) -> tuple[int, int]:
        """Probe stream dimensions via ffprobe, capped at 1920 wide."""
        cmd = [
            "ffprobe", "-v", "error",
            "-rtsp_transport", "tcp",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0",
            self.url,
        ]
        try:
            out = subprocess.check_output(cmd, timeout=5, stderr=subprocess.DEVNULL)
            w, h = (int(x) for x in out.decode().strip().split(","))
            # Mirror the scale filter: cap width at 1920, keep aspect ratio
            if w > 1920:
                h = round(h * 1920 / w / 2) * 2  # ensure even height
                w = 1920
            return w, h
        except Exception:
            log.warning("[camera] ffprobe failed — using fallback 1920x1080")
            return 1920, 1080

    def _read_loop(self) -> None:
        interval = 1.0 / self.fps_limit
        while not self._stop.is_set():
            if not self._width or not self._height:
                log.info("[camera] probing stream dimensions...")
                self._width, self._height = self._get_dimensions()
            w, h = self._width, self._height
            frame_size = w * h * 3
            cmd = [
                "ffmpeg", "-loglevel", "error",
                "-rtsp_transport", "tcp",
                "-timeout", "10000000",          # socket timeout (µs) for RTSP
                "-probesize", "32",             # minimal probe, faster connect
                "-analyzeduration", "0",        # don't wait to analyze stream
                "-fflags", "+discardcorrupt+nobuffer+genpts",
                "-flags", "low_delay",
                "-err_detect", "ignore_err",
                "-max_error_rate", "1.0",       # keep going on decode errors
                "-i", self.url,
                "-vf", f"scale='min(1920,iw)':-2,fps={self.fps_limit}",
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
                    # Skip grey/corrupted frames (near-uniform pixel values)
                    if frame.std() < 4:
                        log.debug("[camera] skipping corrupted frame (std=%.1f)", frame.std())
                        continue
                    with self._lock:
                        self._frame = frame.copy()
                        self._frame_time = time.monotonic()
                    frames_read += 1
            finally:
                proc.terminate()
                proc.wait()
                with self._proc_lock:
                    self._proc = None

            if not self._stop.is_set():
                delay = 5 if frames_read == 0 else 2
                log.info("[camera] reconnecting in %ds...", delay)
                time.sleep(delay)
