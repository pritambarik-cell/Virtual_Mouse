# Technical Documentation: AI Virtual Mouse

## 1. Project Introduction
The AI Virtual Mouse project is a software-based solution for touchless human-computer interaction. It utilizes real-time hand gesture recognition to perform system-level tasks such as mouse movement, clicks, and media control.

## 2. Technical Stack & Architecture

### Core Components
- **MediaPipe (Hand Solution)**: The primary engine for hand tracking. It provides 21 3D hand landmarks. Our implementation uses these landmarks to determine finger states (up/down).
- **OpenCV**: Handles webcam input, frame preprocessing (flipping, resizing), and rendering the visual feedback overlay (landmarks, mode status).
- **PyAutoGUI**: A cross-platform library used to programmatically control the mouse cursor and keyboard shortcuts. It serves as the bridge between gesture recognition and OS actions.
- **Tkinter**: Provides the GUI for mode selection, gesture configuration, and status monitoring.

### Logic Flow
1. **Input**: Webcam captures a frame.
2. **Preprocessing**: OpenCV flips the frame to act like a mirror.
3. **Detection**: MediaPipe processes the frame to find hand landmarks.
4. **Classification**: 
   - Landmarks are analyzed to determine which fingers are raised (`fingers_up` function).
   - The resulting bit-array (e.g., `[0,1,0,0,0]` for Index only) is matched against the `gesture_map`.
5. **Execution**:
   - If a match is found, PyAutoGUI executes the mapped action.
   - For cursor movement, we apply a **Smoothening Filter** to prevent jitter by averaging current and previous coordinates.
6. **Persistence**: Gesture mappings are stored in `gestures.json` for persistent use across sessions.

## 3. Gesture Detection Mechanism
The system represents a gesture as a list of 5 integers, where `1` means the finger is extended and `0` means it is folded.
- **Thumb Detection**: Based on the horizontal distance between the thumb tip and its base (adjusted for Left/Right hand labels).
- **Finger Detection**: Based on the vertical distance between the tip landmark and the PIP joint landmark.

## 4. Mode-Specific Functionality

### Mouse Mode
- **Move Cursor**: Mapped to Index finger.
- **Left/Right Click**: Uses cooldown timers to prevent accidental double-clicks.
- **Scrolling**: Mapped to specific hand signs for vertical scrolling.

### Video Mode
- Uses system-level hotkeys:
  - `alt + tab`: To bring the media player to focus.
  - `space`: For Play/Pause.
  - `right/left`: For seek operations.

### Brightness Mode
- Utilizes the `screen-brightness-control` library.
- Automatically checks for hardware compatibility and hides the mode if unsupported (e.g., on some desktop monitors).

## 5. Deployment & Packaging
To distribute the application as a standalone Windows executable (`.exe`):

1. **Prerequisite**: Install PyInstaller.
   ```bash
   pip install pyinstaller
   ```
2. **Build Command**:
   ```bash
   pyinstaller --noconsole --onefile --add-data "gestures.json;." virtual_mouse.py
   ```
   - `--noconsole`: Hides the terminal window on launch.
   - `--onefile`: Bundles everything into a single `.exe`.
   - `--add-data`: Ensures the default gesture configuration is included in the package.

## 6. Challenges & Solutions
- **Jittering**: Solved using a coordinate smoothening algorithm: `curr_x = prev_x + (mouse_x - prev_x) / smoothening`.
- **False Positives**: Solved by implementing a "Two-Hand Toggle" to pause the system when not in use.
- **Platform Compatibility**: PyAutoGUI ensures the script works on Windows, macOS, and Linux without modification.
