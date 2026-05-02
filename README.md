# 🖱️ AI Virtual Mouse — Hand Sign

## 🌟 Overview
**AI Virtual Mouse** is a cutting-edge computer vision project that allows you to control your computer using simple hand gestures. Leveraging the power of **MediaPipe** and **OpenCV**, this application transforms your webcam into a high-precision gesture controller, eliminating the need for a physical mouse.

Whether you're presenting, browsing, or just want a touchless experience, this virtual mouse provides a seamless and intuitive way to interact with your system.

---

## ✨ Key Features
- **🎯 3 Operation Modes**:
  - **Mouse Mode**: Standard cursor movement, left/right clicks, and scrolling.
  - **Video Mode**: Control media players (Play/Pause, Forward, Backward).
  - **Brightness Mode**: Adjust system brightness on the fly.
- **🛠️ Custom Gesture Mapping**: Record and save your own hand gestures for any action.
- **⏸️ Two-Hand Toggle**: Easily pause and resume detection by bringing both hands into view.
- **⚡ Smooth Movement**: Advanced threshold filtering for jitter-free cursor control.
- **💾 Persistent Settings**: All your custom gestures are saved in `gestures.json`.
- **🖥️ Sleek GUI**: Built with a compact, modern Tkinter interface.

---

## 🚀 Tech Stack
- **Language**: [Python 3.x](https://www.python.org/)
- **Computer Vision**: [OpenCV](https://opencv.org/) & [MediaPipe](https://mediapipe.dev/)
- **Automation**: [PyAutoGUI](https://pyautogui.readthedocs.io/)
- **GUI**: [Tkinter](https://docs.python.org/3/library/tkinter.html)
- **Image Processing**: [Pillow (PIL)](https://python-pillow.org/)
- **System Control**: [screen-brightness-control](https://github.com/SaptakS/screen-brightness-control)

---

## 🛠️ Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/kumarpritam5/Virtual-Mouse.git
cd Virtual-Mouse
```

### 2. Install Dependencies
Ensure you have Python installed, then run:
```bash
pip install -r requirements.txt
```

### 3. Run the Application
```bash
python virtual_mouse.py
```

---

## 📖 Usage Guide
1. **Start Camera**: Click the "Start Camera" button to begin tracking.
2. **Switch Modes**: Use the mode buttons (Mouse, Video, Brightness) to toggle functionality.
3. **Control**:
   - **Move Cursor**: Raise your Index finger.
   - **Left Click**: Raise Index + Middle fingers.
   - **Scroll**: Use Open Palm (Up) or Pinky (Down).
4. **Custom Gestures**: Click "Set" next to any action, wait for the countdown, and show your gesture to record it.
5. **Pause**: Show **two hands** to the camera to toggle detection on/off.

---

## 📦 Deployment (Optional)
This project is ready to be packaged into an executable using **PyInstaller**:
```bash
pyinstaller --onefile --noconsole --add-data "gestures.json;." virtual_mouse.py
```

---

## 🤝 Contributing
Contributions are welcome! If you have ideas for new gestures or modes, feel free to open an issue or submit a pull request.

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
