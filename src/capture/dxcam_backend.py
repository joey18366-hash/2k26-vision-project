"""
Section 4: DXGI Desktop Duplication capture backend.

DXCamWorker runs on its own daemon thread at target_fps, caching
the latest BGR frame so the processing loop can always pull the
most recent frame without blocking capture.

Falls back to mss if dxcam is unavailable (driver/OS issue).
"""
import threading
import time
import numpy as np

try:
    import dxcam
    _DXCAM_AVAILABLE = True
except Exception:
    _DXCAM_AVAILABLE = False
    print("[DXCam] dxcam unavailable — will fall back to mss")

try:
    import mss
    import cv2 as _cv2_mss
    _MSS_AVAILABLE = True
except Exception:
    _MSS_AVAILABLE = False


class DXCamWorker:
    """
    Thread-safe screen capture worker.

    region: (left, top, right, bottom) in screen coordinates.
            Derived from find_xbox_cloud_window().
            None → full primary monitor.
    """

    def __init__(self, target_fps: int = 144, region: tuple = None):
        self.target_fps  = target_fps
        self.region      = region          # (left, top, right, bottom)

        self._camera     = None
        self._sct        = None            # mss instance
        self._latest_frame: np.ndarray | None = None
        self._lock       = threading.Lock()
        self._running    = False
        self._thread: threading.Thread | None = None

        # Diagnostics
        self._frame_count = 0
        self._drop_count  = 0
        self._t_start     = 0.0

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def start(self):
        """Start capture thread. Call once."""
        self._running = True
        self._t_start = time.perf_counter()

        if _DXCAM_AVAILABLE:
            self._camera = dxcam.create(output_idx=0, output_color="BGR")
            kwargs: dict = {"target_fps": self.target_fps, "video_mode": True}
            if self.region:
                kwargs["region"] = self.region
            self._camera.start(**kwargs)
            target = self._dxcam_loop
        elif _MSS_AVAILABLE:
            self._sct = mss.mss()
            target = self._mss_loop
        else:
            raise RuntimeError("Neither dxcam nor mss is available — cannot capture frames.")

        self._thread = threading.Thread(target=target, daemon=True, name="ScreenCapture")
        self._thread.start()
        backend = "dxcam" if _DXCAM_AVAILABLE else "mss"
        print(f"[DXCam] Started ({backend}) — {self.target_fps} fps, region={self.region}")

    def stop(self):
        """Signal the capture thread to stop and wait for it."""
        self._running = False
        if self._camera:
            try:
                self._camera.stop()
                self._camera.release()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=2.0)
        elapsed = time.perf_counter() - self._t_start
        fps_actual = self._frame_count / elapsed if elapsed > 0 else 0
        print(f"[DXCam] Stopped — {self._frame_count} frames, "
              f"{self._drop_count} drops, {fps_actual:.1f} avg fps")

    def get_latest_frame(self) -> np.ndarray | None:
        """
        Thread-safe read of the most recent captured frame.
        Returns a copy so the caller owns the buffer.
        """
        with self._lock:
            return self._latest_frame.copy() if self._latest_frame is not None else None

    @property
    def fps_actual(self) -> float:
        elapsed = time.perf_counter() - self._t_start
        return self._frame_count / elapsed if elapsed > 0 else 0.0

    @property
    def stats(self) -> dict:
        return {
            "frames":     self._frame_count,
            "drops":      self._drop_count,
            "fps_actual": round(self.fps_actual, 1),
        }

    # ------------------------------------------------------------------ #
    #  Internal loops                                                      #
    # ------------------------------------------------------------------ #

    def _dxcam_loop(self):
        while self._running:
            frame = self._camera.get_latest_frame()
            if frame is not None:
                with self._lock:
                    self._latest_frame = frame
                self._frame_count += 1
            else:
                self._drop_count += 1

    def _mss_loop(self):
        """Fallback path — mss is slower (~60Hz ceiling) but functional."""
        interval = 1.0 / self.target_fps
        if self.region:
            l, t, r, b = self.region
            monitor = {"left": l, "top": t, "width": r - l, "height": b - t}
        else:
            monitor = self._sct.monitors[1]

        while self._running:
            t0 = time.perf_counter()
            raw   = self._sct.grab(monitor)
            frame = np.array(raw)
            frame = _cv2_mss.cvtColor(frame, _cv2_mss.COLOR_BGRA2BGR)
            with self._lock:
                self._latest_frame = frame
            self._frame_count += 1
            spent = time.perf_counter() - t0
            slack = interval - spent
            if slack > 0:
                time.sleep(slack)
