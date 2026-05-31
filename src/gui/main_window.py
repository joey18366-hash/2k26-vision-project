"""
Section 8: Dashboard GUI — PyQt6 main window.

MUST be started on the main OS thread (Qt requirement).
Communicates with all backend threads exclusively via Qt signals
so there are no cross-thread widget accesses.

Layout
──────
Left column  : system state, statistics, controls
Right column : live ROI video feed, shot log
"""
import sys
import time
from typing import Optional

import numpy as np
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui  import (
    QImage, QPixmap, QFont, QKeySequence, QColor, QPalette, QShortcut
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QSizePolicy,
)


# ── Signal bridge ──────────────────────────────────────────────────────────
# Worker threads emit these; Qt delivers them on the GUI thread.

class _Bridge(QObject):
    frame_ready   = pyqtSignal(np.ndarray)              # latest annotated frame
    state_changed = pyqtSignal(str)                     # "IDLE", "RISE", …
    shot_logged   = pyqtSignal(str, str, str)           # time, result, offset_ms
    stats_updated = pyqtSignal(int, float, float)       # total, green_pct, latency_ms


# ── State → colour map ─────────────────────────────────────────────────────

_STATE_COLOUR = {
    "IDLE":           "#4b5563",
    "GATHER":         "#3b82f6",
    "RISE":           "#8b5cf6",
    "APEX":           "#f59e0b",
    "RELEASING":      "#10b981",
    "FOLLOW_THROUGH": "#6b7280",
}

_LOG_ROWS = 7


# ── Main window ────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):

    def __init__(self, subsystems: dict):
        super().__init__()
        self._sub    = subsystems
        self._bridge = _Bridge()

        # Shot counters
        self._total_shots = 0
        self._green_shots = 0
        self._active      = False
        self._proc_timer: Optional[QTimer] = None

        self._build_ui()
        self._connect_signals()
        self._register_hotkeys()
        self._start_subsystems()

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self):
        self.setWindowTitle("NBA 2K26 CV Timing Tool")
        self.setMinimumSize(1000, 600)
        self.setStyleSheet(_STYLESHEET)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        left  = QVBoxLayout(); left.setSpacing(10)
        right = QVBoxLayout(); right.setSpacing(10)

        left.addWidget(self._mk_state_panel())
        left.addWidget(self._mk_stats_panel())
        left.addWidget(self._mk_controls_panel())
        left.addStretch()

        right.addWidget(self._mk_roi_panel(), stretch=4)
        right.addWidget(self._mk_log_panel(), stretch=2)

        root.addLayout(left,  stretch=2)
        root.addLayout(right, stretch=5)

        self.statusBar().showMessage(
            "Subsystems starting…  |  F8 = activate  F9 = re-detect  F10 = calibrate"
        )

    def _mk_state_panel(self) -> QGroupBox:
        box = QGroupBox("State Machine")
        v   = QVBoxLayout(box)

        self._lbl_state = QLabel("IDLE")
        self._lbl_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_state.setFont(QFont("Consolas", 26, QFont.Weight.Bold))
        self._lbl_state.setStyleSheet(f"color: {_STATE_COLOUR['IDLE']};")

        self._lbl_active = QLabel("● STANDBY")
        self._lbl_active.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_active.setStyleSheet("color: #ef4444; font-size: 11px; font-weight: bold;")

        v.addWidget(self._lbl_state)
        v.addWidget(self._lbl_active)
        return box

    def _mk_stats_panel(self) -> QGroupBox:
        box = QGroupBox("Statistics")
        g   = QGridLayout(box)
        g.setColumnStretch(1, 1)

        self._stat_shots   = self._mk_val("0")
        self._stat_green   = self._mk_val("—")
        self._stat_latency = self._mk_val("112 ms")
        self._stat_fps     = self._mk_val("— fps")

        rows = [
            ("Shots",   self._stat_shots),
            ("Green %", self._stat_green),
            ("Latency", self._stat_latency),
            ("Capture", self._stat_fps),
        ]
        for i, (label, widget) in enumerate(rows):
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #6b7280; font-size: 11px;")
            g.addWidget(lbl,    i, 0)
            g.addWidget(widget, i, 1)
        return box

    def _mk_controls_panel(self) -> QGroupBox:
        box = QGroupBox("Controls")
        v   = QVBoxLayout(box)

        self._btn_toggle = QPushButton("F8  —  ACTIVATE")
        self._btn_toggle.setCheckable(True)
        self._btn_toggle.clicked.connect(self._on_toggle)
        self._btn_toggle.setFixedHeight(38)

        btn_redetect = QPushButton("F9  —  Re-detect Window")
        btn_redetect.clicked.connect(self._on_redetect)
        btn_redetect.setFixedHeight(32)

        btn_cal = QPushButton("F10  —  Calibrate Sample")
        btn_cal.clicked.connect(self._on_calibrate)
        btn_cal.setFixedHeight(32)

        v.addWidget(self._btn_toggle)
        v.addSpacing(4)
        v.addWidget(btn_redetect)
        v.addWidget(btn_cal)
        return box

    def _mk_roi_panel(self) -> QGroupBox:
        box = QGroupBox("Live ROI — Meter Detection")
        v   = QVBoxLayout(box)

        self._roi_view = QLabel("Waiting for capture…")
        self._roi_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._roi_view.setStyleSheet("background: #0d0d0f; border-radius: 4px;")
        self._roi_view.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        v.addWidget(self._roi_view)
        return box

    def _mk_log_panel(self) -> QGroupBox:
        box = QGroupBox("Shot Log  (most recent first)")
        v   = QVBoxLayout(box)
        self._log_rows = []
        for _ in range(_LOG_ROWS):
            lbl = QLabel("—")
            lbl.setFont(QFont("Consolas", 9))
            lbl.setStyleSheet("color: #374151;")
            v.addWidget(lbl)
            self._log_rows.append(lbl)
        return box

    # ── Signals & hotkeys ─────────────────────────────────────────────────

    def _connect_signals(self):
        self._bridge.frame_ready.connect(self._on_frame)
        self._bridge.state_changed.connect(self._on_state_changed)
        self._bridge.shot_logged.connect(self._on_shot_logged)
        self._bridge.stats_updated.connect(self._on_stats_updated)

    def _register_hotkeys(self):
        QShortcut(QKeySequence("F8"),  self, self._btn_toggle.click)
        QShortcut(QKeySequence("F9"),  self, self._on_redetect)
        QShortcut(QKeySequence("F10"), self, self._on_calibrate)

    # ── Subsystem startup ─────────────────────────────────────────────────

    def _start_subsystems(self):
        inp = self._sub.get("input")
        cv  = self._sub.get("cv")

        if inp and hasattr(inp, "on_rs_change"):
            inp.on_rs_change(self._on_rs_edge)
        if inp:
            inp.start()
        if cv:
            cv.start()

        # Processing timer — tight loop on the main thread (lightweight tick)
        self._proc_timer = QTimer()
        self._proc_timer.setInterval(6)            # ~166 Hz ceiling
        self._proc_timer.timeout.connect(self._tick)

        self.statusBar().showMessage(
            "Subsystems online.  Press F8 to activate."
        )

    # ── Main processing tick ──────────────────────────────────────────────

    def _tick(self):
        cv    = self._sub.get("cv")
        logic = self._sub.get("logic")
        inp   = self._sub.get("input")
        out   = self._sub.get("output")
        det   = self._sub.get("detector")

        if not cv or not logic:
            return

        frame = cv.get_latest_frame()
        if frame is None:
            return

        # Detection
        cv_data: dict = {}
        if det:
            result = det.analyze_frame(frame)
            if result:
                cv_data = result
            annotated = det.get_annotated_frame(frame)
        else:
            annotated = frame

        self._bridge.frame_ready.emit(annotated)

        # State machine
        rs     = inp.rs_pressed if inp else False
        raw    = inp.get_full_state() if inp and hasattr(inp, "get_full_state") else {}
        action = logic.update(rs, cv_data)

        # Virtual controller output
        if out:
            out.emit_report(logic.state, raw)

        # Detect RELEASING → log a shot
        if logic.state == "RELEASING" and action == "RELEASE":
            self._record_shot(cv_data)

        # Update capture FPS stat
        if hasattr(cv, "fps_actual"):
            self._stat_fps.setText(f"{cv.fps_actual:.0f} fps")

        self._bridge.state_changed.emit(logic.state)

    # ── Slot handlers ─────────────────────────────────────────────────────

    def _on_frame(self, frame: np.ndarray):
        h, w = frame.shape[:2]
        qimg = QImage(frame.data, w, h, 3 * w, QImage.Format.Format_BGR888)
        pix  = QPixmap.fromImage(qimg).scaled(
            self._roi_view.width(),
            self._roi_view.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._roi_view.setPixmap(pix)

    def _on_state_changed(self, state: str):
        self._lbl_state.setText(state)
        colour = _STATE_COLOUR.get(state, "#6b7280")
        self._lbl_state.setStyleSheet(f"color: {colour};")

    def _on_shot_logged(self, ts: str, result: str, offset: str):
        # Shift rows down
        for i in range(_LOG_ROWS - 1, 0, -1):
            self._log_rows[i].setText(self._log_rows[i - 1].text())
            self._log_rows[i].setStyleSheet(self._log_rows[i - 1].styleSheet())
        good   = "EXCELLENT" in result or "GOOD" in result
        colour = "#10b981" if good else "#f59e0b"
        self._log_rows[0].setText(f"{ts}   {result:<22}  {offset}")
        self._log_rows[0].setStyleSheet(f"color: {colour};")

    def _on_stats_updated(self, total: int, rate: float, latency: float):
        self._stat_shots.setText(str(total))
        self._stat_green.setText(f"{rate:.1f} %")
        self._stat_latency.setText(f"{latency:.0f} ms")

    def _on_rs_edge(self, pressed: bool):
        # Callback from HID thread — no Qt calls here, just bookkeeping
        pass

    def _on_toggle(self, checked: bool):
        self._active = checked
        if checked:
            self._btn_toggle.setText("F8  —  DEACTIVATE")
            self._lbl_active.setText("● ACTIVE")
            self._lbl_active.setStyleSheet(
                "color: #10b981; font-size: 11px; font-weight: bold;"
            )
            self._proc_timer.start()
        else:
            self._btn_toggle.setText("F8  —  ACTIVATE")
            self._lbl_active.setText("● STANDBY")
            self._lbl_active.setStyleSheet(
                "color: #ef4444; font-size: 11px; font-weight: bold;"
            )
            self._proc_timer.stop()
            # Reset state machine to IDLE
            logic = self._sub.get("logic")
            if logic:
                logic.state = "IDLE"
            self._bridge.state_changed.emit("IDLE")

    def _on_redetect(self):
        from capture.window_finder import find_xbox_cloud_window
        rect = find_xbox_cloud_window()
        if rect:
            msg = f"Window found: {rect['x']},{rect['y']}  {rect['w']}x{rect['h']}"
            # Update capture region on the fly
            cv = self._sub.get("cv")
            if cv:
                cv.region = (
                    rect["x"], rect["y"],
                    rect["x"] + rect["w"],
                    rect["y"] + rect["h"],
                )
        else:
            msg = "Xbox Cloud Gaming window not found — make sure the stream is open."
        self.statusBar().showMessage(msg)

    def _on_calibrate(self):
        """
        Capture a sample frame and auto-detect the meter ROI.
        Uses a simple brightness threshold to find the horizontal
        meter bar near the bottom third of the frame.
        """
        import cv2
        cv  = self._sub.get("cv")
        det = self._sub.get("detector")
        if not cv or not det:
            self.statusBar().showMessage("Capture not running — activate first (F8).")
            return

        frame = cv.get_latest_frame()
        if frame is None:
            self.statusBar().showMessage("No frame available yet.")
            return

        # Search for meter bar in bottom 30% of frame
        h, w    = frame.shape[:2]
        search  = frame[int(h * 0.65):int(h * 0.90), :]
        gray    = cv2.cvtColor(search, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)

        # Find the widest horizontal run — that's the meter background
        row_sums  = mask.sum(axis=1)
        best_row  = int(np.argmax(row_sums))
        row_slice = mask[best_row]
        cols      = np.where(row_slice > 0)[0]

        if len(cols) < 40:
            self.statusBar().showMessage(
                "Meter not found in frame. Shoot a free throw first, then press F10."
            )
            return

        pad   = 6
        rx    = max(0, int(cols[0])  - pad)
        ry    = max(0, int(h * 0.65) + best_row - pad)
        rw    = min(w - rx, int(cols[-1] - cols[0]) + pad * 2)
        rh    = min(h - ry, 28)

        det.set_roi(rx, ry, rw, rh)
        self.statusBar().showMessage(
            f"ROI calibrated: x={rx} y={ry} w={rw} h={rh}  — now start shooting."
        )

    # ── Internal helpers ──────────────────────────────────────────────────

    def _record_shot(self, cv_data: dict):
        self._total_shots += 1
        offset_f  = cv_data.get("frames_to_green", 0.0)
        offset_ms = offset_f * (1000 / 144)
        if abs(offset_ms) <= 16:
            result = "EXCELLENT"
            self._green_shots += 1
        elif abs(offset_ms) <= 33:
            result = "GOOD"
            self._green_shots += 1
        elif offset_ms < -33:
            result = "SLIGHTLY EARLY"
        else:
            result = "SLIGHTLY LATE"

        rate = (self._green_shots / self._total_shots) * 100
        ts   = time.strftime("%H:%M:%S")
        self._bridge.shot_logged.emit(ts, result, f"{offset_ms:+.0f} ms")
        self._bridge.stats_updated.emit(self._total_shots, rate, 112.0)

    @staticmethod
    def _mk_val(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #10b981;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return lbl


# ── Stylesheet ─────────────────────────────────────────────────────────────

_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #0d0d0f;
    color: #d1d5db;
    font-family: 'Segoe UI', sans-serif;
    font-size: 12px;
}
QGroupBox {
    border: 1px solid #1f2937;
    border-radius: 8px;
    margin-top: 10px;
    padding: 8px 8px 6px 8px;
    font-weight: bold;
    font-size: 10px;
    color: #4b5563;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}
QPushButton {
    background: #111827;
    border: 1px solid #374151;
    border-radius: 6px;
    padding: 6px 12px;
    color: #d1d5db;
    font-size: 11px;
}
QPushButton:hover  { background: #1f2937; }
QPushButton:checked {
    background: #064e3b;
    border-color: #10b981;
    color: #10b981;
}
QStatusBar {
    color: #4b5563;
    font-size: 10px;
    border-top: 1px solid #1f2937;
}
"""


# ── Entry point ────────────────────────────────────────────────────────────

def run_gui(subsystems: dict):
    """Start the Qt event loop. Must be called from the main thread."""
    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow(subsystems)
    win.show()
    sys.exit(app.exec())
