import vgamepad as vg

class ViGEmEmitter:
    """
    Section 6: Input Pipeline - Interception layer
    Emits a virtual Xbox 360 controller to the Xbox Cloud Gaming app.
    """
    def __init__(self):
        self.gamepad = vg.VX360Gamepad()
        print("ViGEm Virtual Controller Initialized.")

    def emit_report(self, state, raw_inputs):
        """
        Gating logic (Section 6):
        Copies all axes 1:1 EXCEPT the shoot input which is gated by the CV state.
        """
        # Copy standard buttons (Joysticks, D-Pad, etc)
        # self.gamepad.left_joystick_float(x=raw_inputs['lx'], y=raw_inputs['ly'])
        
        # Shoot Gating Logic
        if state == "RELEASING":
            # Force a single frame of release
            self.gamepad.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB)
        elif state in ["RISE", "APEX", "GATHER"]:
            # Force hold if we are in a shot sequence
            self.gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB)
        
        self.gamepad.update()
