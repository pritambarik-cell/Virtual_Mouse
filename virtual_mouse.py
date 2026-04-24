# ═══════════════════════════════════════════════════════════════════════════════
# Project      : Virtual Mouse — Hand Sign
# Description  : AI based hand gesture mouse controller
#                Control your computer using only hand gestures
#                via webcam — no physical mouse needed!
#
# Features     : 3 Modes  → Mouse Control, Video Control, Brightness Control
#                Custom gesture mapping per mode with conflict detection
#                Two hand toggle to pause and resume detection
#                Persistent gesture storage via gestures.json
#                Smooth cursor movement with threshold filtering
#                Auto brightness check — skips mode if unavailable
#
# Requirements : opencv-python, mediapipe, pyautogui, numpy
#                screen-brightness-control (optional)
#
# Usage        : python virtual_mouse.py
# ═══════════════════════════════════════════════════════════════════════════════

import os
import cv2
import mediapipe as mp
import pyautogui
import numpy as np
import tkinter as tk
from tkinter import font, messagebox
from PIL import Image, ImageTk
import threading
import time
import json

# Suppress TensorFlow and MediaPipe internal warnings in terminal
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

# ── Optional Brightness Control ───────────────────────────────────────────────
# screen_brightness_control may not work on all devices (e.g. external monitors)
# If unavailable, Brightness mode button is hidden from GUI automatically
try:
    import screen_brightness_control as sbc
    BRIGHTNESS_AVAILABLE = True
except Exception:
    BRIGHTNESS_AVAILABLE = False

# ── System Setup ──────────────────────────────────────────────────────────────
pyautogui.FAILSAFE = False
screen_w, screen_h = pyautogui.size()

# ── MediaPipe Setup ───────────────────────────────────────────────────────────
mp_hands = mp.solutions.hands
mp_draw  = mp.solutions.drawing_utils
hands    = mp_hands.Hands(max_num_hands=2, min_detection_confidence=0.7)

# Camera feed display size — kept small to fit inside GUI
CAM_W, CAM_H = 450, 260

# ── Default Gesture Mappings ──────────────────────────────────────────────────
# Gesture = list of 5 values [thumb, index, middle, ring, pinky]
# 1 = finger up  |  0 = finger down
# These are loaded when no gestures.json exists or when new actions are added
DEFAULT_GESTURES = {
    "MOUSE": {
        "Move Cursor":  [0,1,0,0,0],
        "Left Click":   [0,1,1,0,0],
        "Right Click":  [0,1,1,1,0],
        "Scroll Up":    [1,1,1,1,1],
        "Scroll Down":  [0,0,0,0,1]
    },
    "VIDEO": {
        "Move Cursor":  [0,1,0,0,0],
        "Left Click":   [0,1,1,0,0],
        "Right Click":  [0,1,1,1,0],
        "Forward":      [1,1,0,0,0],
        "Backward":     [1,0,0,0,1],
        "Stop/Play":    [0,1,1,1,1]
    },
    "BRIGHTNESS": {
        "Move Cursor":      [0,1,0,0,0],
        "Left Click":       [0,1,1,0,0],
        "Right Click":      [0,1,1,1,0],
        "Brightness Up":    [1,0,0,0,0],
        "Brightness Down":  [0,0,0,0,1]
    }
}

# ── Gesture Display Names ─────────────────────────────────────────────────────
GESTURE_NAMES = {
    str([0,0,0,0,0]): "Fist",
    str([1,0,0,0,0]): "Thumb Only",
    str([1,1,0,0,0]): "Thumb+Index",
    str([1,1,1,0,0]): "Thumb+Index+Middle",
    str([1,0,0,0,1]): "Thumb+Pinky",
    str([0,1,0,0,0]): "Index Only",
    str([0,1,1,0,0]): "Index+Middle",
    str([0,1,1,1,0]): "Index+Middle+Ring",
    str([0,1,1,1,1]): "Index+Middle+Ring+Pinky",
    str([0,1,0,0,1]): "Index+Pinky",
    str([0,0,1,1,0]): "Middle+Ring",
    str([0,0,0,0,1]): "Pinky Only",
    str([1,1,1,1,1]): "Open Palm"
}

# ── Gesture File Path ─────────────────────────────────────────────────────────
# Always saved in the same folder as this script — works correctly as EXE too
GESTURES_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "gestures.json"
)

# ── Gesture Persistence ───────────────────────────────────────────────────────
def load_gestures():
    """
    Load gesture mappings from gestures.json.
    - If file missing  → returns fresh default gestures
    - If file exists   → loads it and auto-adds any new actions from DEFAULT
    This means users never need to manually delete gestures.json after updates.
    """
    if os.path.exists(GESTURES_FILE):
        with open(GESTURES_FILE, "r") as f:
            data = json.load(f)
        updated = False
        for mode, actions in DEFAULT_GESTURES.items():
            if mode not in data:
                data[mode] = dict(actions)
                updated = True
            else:
                for action, gesture in actions.items():
                    if action not in data[mode]:
                        data[mode][action] = gesture
                        updated = True
        if updated:
            save_gestures(data)
        return data
    return {m: dict(a) for m, a in DEFAULT_GESTURES.items()}

def save_gestures(data):
    with open(GESTURES_FILE, "w") as f:
        json.dump(data, f, indent=2)

gesture_map = load_gestures()
save_gestures(gesture_map)

# ── Global State ──────────────────────────────────────────────────────────────
current_mode     = "MOUSE"
camera_running   = False
click_cooldown   = 0
action_cooldown  = 0
prev_x, prev_y   = 0, 0
smoothening      = 3
recording        = False
recorded_gesture = None
recording_action = None
recording_mode   = None
detection_active = True
current_frame    = None


# ── Finger Detection ──────────────────────────────────────────────────────────
def fingers_up(lm, hand_label):
    """
    Determine which fingers are currently raised.

    Uses MediaPipe landmark coordinates:
    - Thumb: compare X positions (left/right depends on hand_label)
    - Other fingers: compare Y positions (tip vs middle joint)

    Returns list of 5 values: [thumb, index, middle, ring, pinky]
    1 = up, 0 = down
    """
    fingers = []
    if hand_label == "Right":
        fingers.append(1 if lm[4].x < lm[3].x else 0)
    else:
        fingers.append(1 if lm[4].x > lm[3].x else 0)
    for tip_id in [8, 12, 16, 20]:
        fingers.append(1 if lm[tip_id].y < lm[tip_id - 2].y else 0)
    return fingers


# ── Action Execution ──────────────────────────────────────────────────────────
def execute_action(action, mode, lm):
    global click_cooldown, action_cooldown, prev_x, prev_y

    if action == "Move Cursor":
        mouse_x = int(lm[8].x * screen_w)
        mouse_y = int(lm[8].y * screen_h)
        if abs(mouse_x - prev_x) > 5 or abs(mouse_y - prev_y) > 5:
            curr_x = prev_x + (mouse_x - prev_x) / smoothening
            curr_y = prev_y + (mouse_y - prev_y) / smoothening
            pyautogui.moveTo(curr_x, curr_y)
            prev_x, prev_y = curr_x, curr_y
        return

    if action == "Left Click":
        if click_cooldown == 0:
            pyautogui.click()
            click_cooldown = 15
        return

    if action == "Right Click":
        if click_cooldown == 0:
            pyautogui.rightClick()
            click_cooldown = 15
        return

    if mode == "MOUSE":
        if action == "Scroll Up":
            pyautogui.scroll(3)
        elif action == "Scroll Down":
            pyautogui.scroll(-3)

    elif mode == "VIDEO":
        if action_cooldown == 0:
            pyautogui.hotkey("alt", "tab")
            time.sleep(0.2)
            if action == "Forward":
                pyautogui.hotkey("right")
            elif action == "Backward":
                pyautogui.hotkey("left")
            elif action == "Stop/Play":
                pyautogui.press("space")
            action_cooldown = 30

    elif mode == "BRIGHTNESS":
        if BRIGHTNESS_AVAILABLE and action_cooldown == 0:
            try:
                current_b = sbc.get_brightness()[0]
                if action == "Brightness Up":
                    sbc.set_brightness(min(100, current_b + 5))
                elif action == "Brightness Down":
                    sbc.set_brightness(max(0, current_b - 5))
            except Exception:
                pass
            action_cooldown = 15


# ── Camera Thread ─────────────────────────────────────────────────────────────
def run_camera():
    """
    Main camera processing loop — runs in a background thread.

    Each frame:
    1. Reads and flips webcam image
    2. Detects hands using MediaPipe
    3. Checks for two-hand toggle
    4. If detection active: identifies gesture and executes action
    5. Overlays mode, status and gesture info on camera feed
    """
    global camera_running, click_cooldown, action_cooldown
    global recording, recorded_gesture, detection_active
    global prev_x, prev_y, current_frame

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        camera_running = False
        root.after(0, lambda: status_label.config(
            text="Camera not found! Check your webcam.", fg="#FF4C4C"))
        root.after(0, lambda: btn_start.config(
            text="Start Camera", bg="#00C896", fg="#0D0D0D"))
        return

    # Capture at display size directly
    cap.set(3, CAM_W)
    cap.set(4, CAM_H)
    last_toggle_time = 0

    while camera_running:
        success, img = cap.read()
        if not success:
            root.after(0, lambda: status_label.config(
                text="Camera disconnected!", fg="#FF4C4C"))
            break

        img     = cv2.flip(img, 1)
        # Resize to exact display size every frame
        img     = cv2.resize(img, (CAM_W, CAM_H))
        h, w, _ = img.shape
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = hands.process(img_rgb)

        mode_colors = {
            "MOUSE":      (0, 220, 150),
            "VIDEO":      (0, 200, 255),
            "BRIGHTNESS": (100, 255, 100)
        }
        color = mode_colors.get(current_mode, (255, 255, 255))

        # Top bar
        cv2.rectangle(img, (0, 0), (w, 32), (10, 10, 10), -1)
        if recording:
            cv2.putText(img, "SHOW GESTURE NOW", (8, 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1)
        else:
            cv2.putText(img, f"MODE: {current_mode}", (8, 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1)

        # Bottom bar
        cv2.rectangle(img, (0, h - 26), (w, h), (10, 10, 10), -1)

        if results.multi_hand_landmarks:
            if len(results.multi_hand_landmarks) == 2:
                wrist1   = results.multi_hand_landmarks[0].landmark[0]
                wrist2   = results.multi_hand_landmarks[1].landmark[0]
                distance = ((wrist1.x - wrist2.x)**2 + (wrist1.y - wrist2.y)**2) ** 0.5
                now      = time.time()
                if distance > 0.3 and now - last_toggle_time > 1.5:
                    detection_active = not detection_active
                    last_toggle_time = now

            s_text  = "ACTIVE" if detection_active else "PAUSED"
            s_color = (0, 220, 100) if detection_active else (120, 120, 120)
            cv2.putText(img, s_text, (w - 85, h - 7),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, s_color, 1)

            if detection_active:
                for i, hand_landmarks in enumerate(results.multi_hand_landmarks):
                    mp_draw.draw_landmarks(img, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                    lm = hand_landmarks.landmark
                    try:
                        hand_label = results.multi_handedness[i].classification[0].label
                    except Exception:
                        hand_label = "Right"

                    fingers = fingers_up(lm, hand_label)

                    if recording:
                        recorded_gesture = fingers
                        name = GESTURE_NAMES.get(str(fingers), str(fingers))
                        cv2.rectangle(img, (0, 34), (w, 62), (20, 20, 20), -1)
                        cv2.putText(img, f"Detected: {name}", (8, 54),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 100), 1)
                    else:
                        click_cooldown  = max(0, click_cooldown - 1)
                        action_cooldown = max(0, action_cooldown - 1)

                        matched_action = None
                        for act, saved_gesture in gesture_map[current_mode].items():
                            if fingers == saved_gesture:
                                matched_action = act
                                break

                        if matched_action:
                            cv2.rectangle(img, (0, 34), (w, 62), (20, 20, 20), -1)
                            cv2.putText(img, matched_action.upper(), (8, 54),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                            execute_action(matched_action, current_mode, lm)
        else:
            cv2.putText(img, "No hand detected", (8, h - 7),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (70, 70, 70), 1)

        current_frame = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    cap.release()
    current_frame  = None
    camera_running = False
    root.after(0, lambda: btn_start.config(
        text="Start Camera", bg="#00C896", fg="#0D0D0D"))


# ── GUI Frame Updater ─────────────────────────────────────────────────────────
def update_camera_display():
    if camera_running and current_frame is not None:
        try:
            img_pil = Image.fromarray(current_frame)
            img_tk  = ImageTk.PhotoImage(image=img_pil)
            camera_label.img_tk = img_tk
            camera_label.config(image=img_tk)
        except Exception:
            pass
    root.after(33, update_camera_display)


# ═══════════════════════════════════════════════════════════════════════════════
# GUI — compact layout, no wasted space
# ═══════════════════════════════════════════════════════════════════════════════

root = tk.Tk()
root.title("Virtual Mouse - Hand Sign")
root.geometry("500x600")   # Compact default size
root.resizable(False, False)
root.configure(bg="#0D0D0D")

title_font = tk.font.Font(family="Courier New", size=18, weight="bold")
sub_font   = tk.font.Font(family="Courier New", size=9)
mode_font  = tk.font.Font(family="Courier New", size=11, weight="bold")
guide_font = tk.font.Font(family="Courier New", size=9)
btn_font   = tk.font.Font(family="Courier New", size=11, weight="bold")
small_font = tk.font.Font(family="Courier New", size=9)

# Header — reduced padding
tk.Label(root, text="VIRTUAL MOUSE", font=title_font,
         bg="#0D0D0D", fg="#00C896").pack(pady=(12, 1))
tk.Label(root, text="Hand Gesture Controller", font=sub_font,
         bg="#0D0D0D", fg="#444444").pack(pady=(0, 8))

# Mode buttons
tk.Label(root, text="SELECT MODE", font=sub_font,
         bg="#0D0D0D", fg="#444444").pack()
mode_frame = tk.Frame(root, bg="#0D0D0D")
mode_frame.pack(pady=5)

mode_indicator = tk.Label(root, text="MOUSE MODE ACTIVE", font=mode_font,
                           bg="#0D0D0D", fg="#00C896")
mode_indicator.pack(pady=(2, 6))

# Gesture settings panel — compact height
settings_frame = tk.Frame(root, bg="#111111", bd=0, height=195)
settings_frame.pack(padx=20, pady=2, fill="x")
settings_frame.pack_propagate(False)

settings_title = tk.Label(settings_frame, text="GESTURE SETTINGS - MOUSE MODE",
                           font=small_font, bg="#111111", fg="#555555")
settings_title.pack(pady=(6, 3))

canvas_s   = tk.Canvas(settings_frame, bg="#111111", height=155, highlightthickness=0)
scrollbar  = tk.Scrollbar(settings_frame, orient="vertical", command=canvas_s.yview)
rows_frame = tk.Frame(canvas_s, bg="#111111")

rows_frame.bind("<Configure>", lambda e: canvas_s.configure(
    scrollregion=canvas_s.bbox("all")))
canvas_s.create_window((0, 0), window=rows_frame, anchor="nw")
canvas_s.configure(yscrollcommand=scrollbar.set)
canvas_s.pack(side="left", fill="both", expand=True, padx=8, pady=3)
scrollbar.pack(side="right", fill="y")

action_labels = {}
set_buttons   = {}

def refresh_settings_panel(mode):
    """
    Rebuild gesture settings rows for the selected mode.
    Shows action name, current gesture and Set button for each action.
    """
    for widget in rows_frame.winfo_children():
        widget.destroy()
    action_labels.clear()
    set_buttons.clear()
    settings_title.config(text=f"GESTURE SETTINGS - {mode} MODE")
    mode_accent = {"MOUSE": "#00C896", "VIDEO": "#00BFFF", "BRIGHTNESS": "#FFD700"}
    accent = mode_accent.get(mode, "#00C896")
    for action in gesture_map[mode]:
        row = tk.Frame(rows_frame, bg="#111111")
        row.pack(fill="x", pady=2)
        tk.Label(row, text=action, font=guide_font, bg="#111111",
                 fg="#AAAAAA", width=16, anchor="w").pack(side="left")
        saved = gesture_map[mode][action]
        gname = GESTURE_NAMES.get(str(saved), str(saved))
        lbl   = tk.Label(row, text=gname, font=guide_font,
                         bg="#1A1A1A", fg=accent, width=20, anchor="w")
        lbl.pack(side="left", padx=5)
        action_labels[action] = lbl
        btn = tk.Button(row, text="Set", font=small_font, bg="#222222", fg="#888888",
                        relief="flat", cursor="hand2", padx=5,
                        command=lambda a=action: start_recording(a))
        btn.pack(side="left", padx=3)
        set_buttons[action] = btn


def start_recording(action):
    """
    Start the gesture recording process for a specific action.
    Runs a 3 second countdown, captures the held gesture,
    checks for conflicts with existing gestures in the same mode
    and saves to gestures.json if no conflict found.
    """
    global recording, recorded_gesture, recording_action, recording_mode
    if not camera_running:
        messagebox.showwarning("Camera Off", "Please start the camera first!")
        return
    recording_action = action
    recording_mode   = current_mode
    recorded_gesture = None
    recording        = True
    set_buttons[action].config(text="...", bg="#FFD700", fg="#0D0D0D")

    def do_record():
        global recording, recorded_gesture
        for i in range(3, 0, -1):
            root.after(0, lambda i=i: status_label.config(
                text=f"Get ready... {i}", fg="#FFD700"))
            time.sleep(1)
        root.after(0, lambda: status_label.config(
            text="Capturing gesture!", fg="#00FF99"))
        time.sleep(1.5)
        if recorded_gesture is not None:
            conflict = None
            for ex_action, ex_gesture in gesture_map[recording_mode].items():
                if ex_gesture == recorded_gesture and ex_action != recording_action:
                    conflict = ex_action
                    break
            if conflict:
                recording = False
                root.after(0, lambda: set_buttons[recording_action].config(
                    text="Set", bg="#222222", fg="#888888"))
                root.after(0, lambda: status_label.config(
                    text=f"Already used for {conflict}!", fg="#FF4C4C"))
                time.sleep(2)
                root.after(0, lambda: status_label.config(text="", fg="#444444"))
            else:
                gesture_map[recording_mode][recording_action] = recorded_gesture
                save_gestures(gesture_map)
                recording = False
                name = GESTURE_NAMES.get(str(recorded_gesture), str(recorded_gesture))
                root.after(0, lambda n=name: action_labels[recording_action].config(text=n))
                root.after(0, lambda: set_buttons[recording_action].config(
                    text="Set", bg="#222222", fg="#888888"))
                root.after(0, lambda n=name: status_label.config(
                    text=f"Saved {n} for {recording_action}!", fg="#00C896"))
                time.sleep(2)
                root.after(0, lambda: status_label.config(text="", fg="#444444"))
        else:
            recording = False
            root.after(0, lambda: set_buttons[recording_action].config(
                text="Set", bg="#222222", fg="#888888"))
            root.after(0, lambda: status_label.config(
                text="No hand detected! Try again.", fg="#FF4C4C"))
            time.sleep(2)
            root.after(0, lambda: status_label.config(text="", fg="#444444"))

    threading.Thread(target=do_record, daemon=True).start()


# Status label
status_label = tk.Label(root, text="", font=small_font, bg="#0D0D0D", fg="#444444")
status_label.pack(pady=1)

if not BRIGHTNESS_AVAILABLE:
    tk.Label(root, text="Brightness control not available on this device",
             font=small_font, bg="#0D0D0D", fg="#888888").pack(pady=(0, 1))

tk.Frame(root, bg="#222222", height=1).pack(fill="x", padx=20, pady=5)


def set_mode(mode, btn):
    """
    Switch active mode, update indicator label color
    and refresh gesture settings panel for the new mode.
    """
    global current_mode
    current_mode = mode
    colors = {"MOUSE": "#00C896", "VIDEO": "#00BFFF", "BRIGHTNESS": "#FFD700"}
    labels = {"MOUSE": "MOUSE MODE ACTIVE",
              "VIDEO": "VIDEO MODE ACTIVE",
              "BRIGHTNESS": "BRIGHTNESS MODE ACTIVE"}
    mode_indicator.config(text=labels[mode], fg=colors[mode])
    for b in mode_buttons:
        b.config(bg="#1A1A1A", fg="#888888")
    btn.config(bg=colors[mode], fg="#0D0D0D")
    refresh_settings_panel(mode)


mode_buttons = []

btn_mouse = tk.Button(mode_frame, text="Mouse", font=btn_font, width=12,
                      bg="#00C896", fg="#0D0D0D", relief="flat", cursor="hand2",
                      command=lambda: set_mode("MOUSE", btn_mouse))
btn_mouse.grid(row=0, column=0, padx=8, ipady=6)
mode_buttons.append(btn_mouse)

btn_video = tk.Button(mode_frame, text="Video", font=btn_font, width=12,
                      bg="#1A1A1A", fg="#888888", relief="flat", cursor="hand2",
                      command=lambda: set_mode("VIDEO", btn_video))
btn_video.grid(row=0, column=1, padx=8, ipady=6)
mode_buttons.append(btn_video)

if BRIGHTNESS_AVAILABLE:
    btn_bright = tk.Button(mode_frame, text="Brightness", font=btn_font, width=12,
                           bg="#1A1A1A", fg="#888888", relief="flat", cursor="hand2",
                           command=lambda: set_mode("BRIGHTNESS", btn_bright))
    btn_bright.grid(row=0, column=2, padx=8, ipady=6)
    mode_buttons.append(btn_bright)

refresh_settings_panel("MOUSE")


def toggle_camera():
    global camera_running
    if not camera_running:
        camera_running = True
        status_label.config(text="", fg="#444444")
        btn_start.config(text="Stop Camera", bg="#FF4C4C", fg="#FFFFFF")
        # Show camera feed and expand window just enough
        camera_label.pack(padx=20, pady=(0, 10))
        root.geometry(f"500x{600 + CAM_H + 15}")
        threading.Thread(target=run_camera, daemon=True).start()
    else:
        camera_running = False
        btn_start.config(text="Start Camera", bg="#00C896", fg="#0D0D0D")
        # Hide camera and restore compact window
        camera_label.pack_forget()
        root.geometry("500x600")


btn_start = tk.Button(root, text="Start Camera", font=btn_font,
                      bg="#00C896", fg="#0D0D0D", relief="flat", cursor="hand2",
                      width=22, command=toggle_camera)
btn_start.pack(ipady=10, pady=(0, 8))

# Camera label — hidden by default, no space taken
camera_label = tk.Label(root, bg="#0D0D0D")

update_camera_display()
root.mainloop()