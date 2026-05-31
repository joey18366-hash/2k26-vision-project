import time

class ShotStateMachine:
    """
    Implementation of Section 5.1: Shot State Machine
    IDLE -> GATHER -> RISE -> APEX -> RELEASE_WINDOW -> FOLLOW_THROUGH -> IDLE
    """
    def __init__(self, prediction_ms):
        self.state = "IDLE"
        self.prediction_ms = prediction_ms
        self.last_state_change = time.time()
        self.gather_buffer_ms = 14 # From Section 6: Architecture Insight

    def update(self, input_pressed, cv_data):
        now = time.time() * 1000
        
        # Identity logic: Only transitions based on high-integrity signals
        if self.state == "IDLE" and input_pressed:
            self.state = "GATHER"
            self.last_state_change = now
            return "SUPPRESS" # Block physical shoot from reaching game yet

        if self.state == "GATHER":
            if (now - self.last_state_change) >= self.gather_buffer_ms:
                self.state = "RISE"
                return "HOLD"
        
        # CV Predictive Logic (Section 5.2)
        if self.state in ["RISE", "APEX"]:
            if cv_data.get('predicted_frames_to_green', 99) <= (self.prediction_ms / 7): # Convert ms to frames
                self.state = "RELEASING"
                return "RELEASE"
        
        return "PASS_THROUGH"
