# NBA 2K26 Computer-Vision Jumpshot Timing Tool
Repository requirements based on Section 11 of master specification.

## Core Dependencies
```text
dxcam==0.0.5          # DXGI Desktop Duplication
vgamepad==0.1.2       # ViGEmBus implementation
pyqt6==6.6.1          # Dashboard UI
opencv-python==4.9.0  # Image processing
numpy==1.26.4
pytesseract==0.3.10   # Result feedback OCR
pynput==1.7.6         # Global hotkeys
```

## Setup Instructions
1. Install **ViGEmBus** and **HidHide** drivers (see `installer/vendor`).
2. Run `pip install -r requirements.txt`.
3. Launch with `python src/main.py`.
4. Perform the 3-minute initial calibration wizard.
5. `F8` toggles the tool state.
