"""
Section 6: Input Pipeline — Physical controller reader.

Polls the physical Xbox controller (or Cronus Zen / Titan Two output)
via the Windows XInput API at ~1 kHz.

HidHide must whitelist this process so the device is visible here
but invisible to the Xbox app — that app then exclusively sees the
ViGEmBus virtual controller emitted by vgamepad_writer.py.

Graceful degradation: if XInput fails (no driver, no controller,
non-Windows OS) rs_pressed always reads False and no callbacks fire,
so the rest of the pipeline keeps running in a degraded but stable state.
"""
import ctypes
import sys
import threading
import time
from typing import Callable, List


# ── XInput struct layout ───────────────────────────────────────────────────

class _XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [
        ("wButtons",      ctypes.c_ushort),
        ("bLeftTrigger",  ctypes.c_ubyte),
        ("bRightTrigger", ctypes.c_ubyte),
        ("sThumbLX",      ctypes.c_short),
        ("sThumbLY",      ctypes.c_short),
        ("sThumbRX",      ctypes.c_short),
        ("sThumbRY",      ctypes.c_short),
    ]


class _XINPUT_STATE(ctypes.Structure):
    _fields_ = [
        ("dwPacketNumber", ctypes.c_ulong),
        ("Gamepad",        _XINPUT_GAMEPAD),
    ]


# XInput button bitmasks (matching vgamepad_writer.py names)
XUSB_GAMEPAD_DPAD_UP        = 0x0001
XUSB_GAMEPAD_DPAD_DOWN      = 0x0002
XUSB_GAMEPAD_DPAD_LEFT      = 0x0004
XUSB_GAMEPAD_DPAD_RIGHT     = 0x0008
XUSB_GAMEPAD_START          = 0x0010
XUSB_GAMEPAD_BACK           = 0x0020
XUSB_GAMEPAD_LEFT_THUMB     = 0x0040
XUSB_GAMEPAD_RIGHT_THUMB    = 0x0080   # RS click = shoot button
XUSB_GAMEPAD_LEFT_SHOULDER  = 0x0100
XUSB_GAMEPAD_RIGHT_SHOULDER = 0x0200
XUSB_GAMEPAD_A              = 0x1000
XUSB_GAMEPAD_B              = 0x2000
XUSB_GAMEPAD_X              = 0x4000
XUSB_GAMEPAD_Y              = 0x8000

_POLL_INTERVAL_S = 0.001   # 1 ms → ~1000 Hz, well above any game frame rate
_ERROR_SUCCESS   = 0


class ZenHIDReader:
    """
    Polls XInput slot `controller_index` and fires registered callbacks on
    RS press/release transitions.

    Architecture
    ────────────
    • One background daemon thread does the polling.
    • Callers read `rs_pressed` (property) or register via `on_rs_change`.
    • `get_full_state()` returns every axis and button for pass-through use
      by vgamepad_writer.

    Usage
    ─────
        reader = ZenHIDReader(controller_index=0)
        reader.on_rs_change(lambda pressed: state_machine.update(pressed, {}))
        reader.start()
        ...
        reader.stop()
    """

    def __init__(self, controller_index: int = 0):
        self.controller_index = controller_index
        self._xinput          = self._load_xinput()
        self._state           = _XINPUT_STATE()
        self._rs_pressed      = False
        self._running         = False
        self._thread: threading.Thread | None = None
        self._callbacks: List[Callable[[bool], None]] = []
        self._last_packet     = 0

    # ── Public API ─────────────────────────────────────────────────────────

    def start(self):
        if not self._xinput:
            print("[HID] XInput unavailable — RS will always read False. "
                  "Check ViGEmBus/XInput installation.")
            return
        self._running = True
        self._thread  = threading.Thread(
            target=self._poll_loop, daemon=True, name="ZenHIDReader"
        )
        self._thread.start()
        print(f"[HID] Polling XInput slot {self.controller_index} at ~1 kHz")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        print("[HID] Stopped.")

    def on_rs_change(self, callback: Callable[[bool], None]):
        """
        Register a callback called on every RS press/release edge.
        `callback(True)`  → RS just pressed
        `callback(False)` → RS just released
        """
        self._callbacks.append(callback)

    @property
    def rs_pressed(self) -> bool:
        """Current RS state (non-blocking, thread-safe)."""
        return self._rs_pressed

    def get_full_state(self) -> dict:
        """
        Snapshot of all axes and buttons.
        Used by vgamepad_writer for 1-to-1 pass-through of every input
        except the gated shoot button.
        """
        gp = self._state.Gamepad
        return {
            # Normalised floats in [-1, 1] or [0, 1]
            "lx":  gp.sThumbLX      / 32767.0,
            "ly":  gp.sThumbLY      / 32767.0,
            "rx":  gp.sThumbRX      / 32767.0,
            "ry":  gp.sThumbRY      / 32767.0,
            "lt":  gp.bLeftTrigger  / 255.0,
            "rt":  gp.bRightTrigger / 255.0,
            # Raw bitmask
            "buttons":    gp.wButtons,
            "rs_pressed": self._rs_pressed,
        }

    def is_connected(self) -> bool:
        if not self._xinput:
            return False
        result = self._xinput.XInputGetState(
            self.controller_index, ctypes.byref(self._state)
        )
        return result == _ERROR_SUCCESS

    # ── Internal ───────────────────────────────────────────────────────────

    @staticmethod
    def _load_xinput():
        """Try each known XInput DLL in priority order."""
        if sys.platform != "win32":
            print("[HID] Non-Windows platform — XInput unavailable.")
            return None
        for dll in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
            try:
                lib = ctypes.windll.LoadLibrary(dll)
                print(f"[HID] Loaded {dll}")
                return lib
            except OSError:
                continue
        print("[HID] No XInput DLL found.")
        return None

    def _poll_loop(self):
        while self._running:
            ret = self._xinput.XInputGetState(
                self.controller_index, ctypes.byref(self._state)
            )

            if ret == _ERROR_SUCCESS:
                # Only process if packet actually changed (saves CPU)
                pkt = self._state.dwPacketNumber
                if pkt != self._last_packet:
                    self._last_packet = pkt
                    rs_now = bool(
                        self._state.Gamepad.wButtons & XUSB_GAMEPAD_RIGHT_THUMB
                    )
                    if rs_now != self._rs_pressed:
                        self._rs_pressed = rs_now
                        for cb in self._callbacks:
                            try:
                                cb(rs_now)
                            except Exception as exc:
                                print(f"[HID] Callback error: {exc}")

            time.sleep(_POLL_INTERVAL_S)
