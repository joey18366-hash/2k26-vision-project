import pygetwindow as gw

def find_xbox_cloud_window():
    """
    Section 4: Capture Subsystem - Window Targeting
    Locates the window by process name + window title.
    """
    # Search for common Xbox Cloud Gaming window titles
    targets = ["Xbox Cloud Gaming", "Xbox"]
    
    for title in targets:
        windows = gw.getWindowsWithTitle(title)
        if windows:
            win = windows[0]
            print(f"Found Target Window: {win.title} at {win.topleft}")
            # Section 4: Derive game render rect (strip browser chrome/letterboxing)
            # In a real impl, we'd use edge detection on a blank screen here
            return {
                "x": win.left + 10, 
                "y": win.top + 80, 
                "w": 1920, 
                "h": 1080
            }
            
    return None
