"""
NBA 2K26 CV Timing Tool — entry point.

Wires all subsystems together and hands off to the GUI main loop.
Run from the src/ directory:
    python main.py
"""
import sys
import os

# Ensure src/ is on the path for intra-package imports
sys.path.insert(0, os.path.dirname(__file__))

from capture.window_finder       import find_xbox_cloud_window
from capture.dxcam_backend       import DXCamWorker
from input_pipeline.hid_reader   import ZenHIDReader
from input_pipeline.vgamepad_writer import ViGEmEmitter
from detection.meter_detector    import MeterDetector, DEFAULT_HSV_RANGE
from detection.state_machine     import ShotStateMachine
from gui.main_window             import run_gui


def main():
    print("=" * 52)
    print("  NBA 2K26 Computer-Vision Jumpshot Timing Tool")
    print("=" * 52)

    # ── 1. Window discovery ───────────────────────────────────────────
    print("\n[Init] Locating Xbox Cloud Gaming window…")
    window_rect = find_xbox_cloud_window()

    region = None
    if window_rect:
        # Convert {x, y, w, h} → (left, top, right, bottom) for dxcam
        region = (
            window_rect["x"],
            window_rect["y"],
            window_rect["x"] + window_rect["w"],
            window_rect["y"] + window_rect["h"],
        )
        print(f"[Init] Window found — capture region: {region}")
    else:
        print("[Init] Window not found — will capture full screen. "
              "Press F9 after the stream opens to re-detect.")

    # ── 2. Instantiate subsystems ─────────────────────────────────────
    print("\n[Init] Initialising subsystems…")

    cv_worker   = DXCamWorker(target_fps=144, region=region)
    hid_reader  = ZenHIDReader(controller_index=0)
    detector    = MeterDetector(hsv_range=DEFAULT_HSV_RANGE)
    state_mach  = ShotStateMachine(prediction_ms=112)
    emitter     = ViGEmEmitter()

    print("[Init] All subsystems ready.\n")

    # ── 3. Hand off to GUI (blocks until window is closed) ───────────
    run_gui(subsystems={
        "cv":       cv_worker,
        "input":    hid_reader,
        "detector": detector,
        "logic":    state_mach,
        "output":   emitter,
    })


if __name__ == "__main__":
    main()
