"""
Section 5.2: Shot meter detector — HSV analysis inside calibrated ROI.

Detects the white shot marker and the green zone, computes marker
velocity from the previous frame, and predicts how many frames remain
until the marker centre hits the green zone centre.

That `frames_to_green` number is what ShotStateMachine consumes.
"""
import time
import numpy as np
import cv2
from typing import Optional


# ── Default HSV ranges for 2K26's shot meter ──────────────────────────────
# Tune these via F10 calibration if your stream has colour shifts
# from H.264 compression artifacts.

DEFAULT_HSV_RANGE = {
    # White-ish shot marker (high V, low S)
    "marker_min": np.array([0,   0,   190], dtype=np.uint8),
    "marker_max": np.array([180, 45,  255], dtype=np.uint8),
    # Green zone
    "green_min":  np.array([40,  120, 120], dtype=np.uint8),
    "green_max":  np.array([90,  255, 255], dtype=np.uint8),
}

# Minimum contour area (px^2) to reject noise from compression artifacts
_MIN_MARKER_AREA = 20
_MIN_GREEN_AREA  = 60


class MeterDetector:
    """
    Stateful frame-by-frame meter detector.

    roi: (x, y, w, h) relative to the full captured frame.
         Set during calibration; None means detection is disabled.
    """

    def __init__(self, hsv_range: dict = None):
        self.hsv_range = hsv_range or DEFAULT_HSV_RANGE
        self.roi = None                            # (x, y, w, h)

        # Velocity tracking
        self._prev_marker_x = None
        self._prev_ts       = 0.0
        self._velocity_px_per_s = 0.0             # positive = moving right

        # Cache green zone centre (static once meter appears)
        self._green_cx = None

        # Last annotated ROI (returned to GUI)
        self._annotated = None

    # ── Public API ─────────────────────────────────────────────────────────

    def set_roi(self, x: int, y: int, w: int, h: int):
        self.roi = (x, y, w, h)
        self._prev_marker_x = None
        self._green_cx      = None
        print(f"[Detector] ROI set: x={x} y={y} w={w} h={h}")

    def analyze_frame(self, frame: np.ndarray) -> Optional[dict]:
        """
        Analyse one BGR frame.

        Returns dict:
            frames_to_green   – predicted frames until marker hits green zone
            marker_x          – marker centroid x inside ROI (px)
            green_cx          – green zone centre x inside ROI (px)
            velocity_px_per_s – marker velocity (positive = moving right)
        Returns None if ROI not set or meter not found.
        """
        if self.roi is None:
            return None

        x, y, w, h = self.roi
        cutout = frame[y:y+h, x:x+w]
        if cutout.size == 0:
            return None

        now = time.perf_counter()
        hsv = cv2.cvtColor(cutout, cv2.COLOR_BGR2HSV)

        # ── Green zone ───────────────────────────────────────────────────
        mask_green = cv2.inRange(
            hsv, self.hsv_range["green_min"], self.hsv_range["green_max"]
        )
        green_cx = self._find_centroid_x(mask_green, _MIN_GREEN_AREA)
        if green_cx is not None:
            self._green_cx = green_cx   # cache; green zone is static

        # ── Shot marker ──────────────────────────────────────────────────
        mask_marker = cv2.inRange(
            hsv, self.hsv_range["marker_min"], self.hsv_range["marker_max"]
        )
        marker_cx = self._find_centroid_x(mask_marker, _MIN_MARKER_AREA)

        if marker_cx is None:
            self._prev_marker_x = None
            self._annotated = self._draw_annotations(
                cutout, None, mask_green, mask_marker
            )
            return None

        # ── Velocity estimation (EMA smoothed) ───────────────────────────
        dt = now - self._prev_ts
        if self._prev_marker_x is not None and 0 < dt < 0.5:
            alpha   = 0.4
            raw_v   = (marker_cx - self._prev_marker_x) / dt
            self._velocity_px_per_s = (
                alpha * raw_v + (1 - alpha) * self._velocity_px_per_s
            )
        self._prev_marker_x = marker_cx
        self._prev_ts       = now

        # ── Frame-distance prediction ─────────────────────────────────────
        frames_to_green = 9999.0
        if self._green_cx is not None and self._velocity_px_per_s > 0.1:
            dist_px      = self._green_cx - marker_cx
            px_per_frame = self._velocity_px_per_s / 144.0   # nominal 144fps
            if px_per_frame > 0:
                frames_to_green = max(0.0, dist_px / px_per_frame)

        self._annotated = self._draw_annotations(
            cutout, marker_cx, mask_green, mask_marker,
            green_cx=self._green_cx,
            frames_to_green=frames_to_green,
        )

        return {
            "frames_to_green":   frames_to_green,
            "marker_x":          marker_cx,
            "green_cx":          self._green_cx,
            "velocity_px_per_s": self._velocity_px_per_s,
        }

    def get_annotated_frame(self, full_frame: np.ndarray) -> np.ndarray:
        """
        Returns the full frame with ROI replaced by the annotated version.
        Safe to call even before any detection has run.
        """
        if self._annotated is None or self.roi is None:
            return full_frame
        out = full_frame.copy()
        x, y, w, h = self.roi
        ah, aw = self._annotated.shape[:2]
        out[y:y+ah, x:x+aw] = self._annotated[:ah, :aw]
        return out

    # ── Internal helpers ───────────────────────────────────────────────────

    @staticmethod
    def _find_centroid_x(mask: np.ndarray, min_area: int) -> Optional[float]:
        """Return x centroid of the largest blob in mask, or None."""
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            return None
        biggest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(biggest) < min_area:
            return None
        M = cv2.moments(biggest)
        if M["m00"] == 0:
            return None
        return M["m10"] / M["m00"]

    @staticmethod
    def _draw_annotations(
        cutout: np.ndarray,
        marker_cx,
        mask_green: np.ndarray,
        mask_marker: np.ndarray,
        green_cx=None,
        frames_to_green: float = 9999.0,
    ) -> np.ndarray:
        out = cutout.copy()
        h, w = out.shape[:2]

        # Green zone tint
        tint = np.zeros_like(out)
        tint[mask_green > 0] = (0, 200, 80)
        out = cv2.addWeighted(out, 0.7, tint, 0.3, 0)

        # Green zone centre
        if green_cx is not None:
            gx = int(green_cx)
            cv2.line(out, (gx, 0), (gx, h), (0, 255, 80), 1)

        # Marker
        if marker_cx is not None:
            mx = int(marker_cx)
            cv2.line(out, (mx, 0), (mx, h), (255, 255, 255), 2)
            label = "FIRE" if frames_to_green < 3 else f"{frames_to_green:.0f}f"
            color = (0, 255, 80) if frames_to_green < 3 else (200, 200, 200)
            cv2.putText(
                out, label, (max(0, mx - 12), h - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA,
            )

        if frames_to_green < 3:
            cv2.rectangle(out, (0, 0), (w - 1, h - 1), (0, 255, 80), 2)

        return out
