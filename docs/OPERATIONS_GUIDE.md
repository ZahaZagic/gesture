# Operations Guide

Generated: 2026-05-04

## Environment

This project is currently developed from:

```text
C:\Users\zzhang1\PycharmProjects\gesture
```

Most Python demos require:

- A working webcam.
- Camera permissions.
- Python environment with dependencies installed.
- Desktop input permissions for mouse-control demos.
- Good lighting for landmark stability.

## Python Setup

From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If MediaPipe install compatibility is an issue, use a Python version supported by the installed MediaPipe release.

## Python Run Commands

### Posture Monitor

Interactive preview:

```powershell
python app_posture_demo.py
```

Background notification mode:

```powershell
python app_posture_demo.py --background
```

Alternate camera:

```powershell
python app_posture_demo.py --camera-id 1
```

Controls:

- `q`: quit.
- `c`: recalibrate posture baseline.
- `r`: generate a posture report from the current frame.

### Gesture Mouse

```powershell
python app_mouse_demo.py
```

Controls:

- `q`: quit.
- Index finger: move cursor.
- Thumb + middle pinch: left click.
- Thumb + index pinch: right click.
- Fist: drag.
- Open hand: scroll.
- Double blink: double click.

### Eye Mouse

```powershell
python app_eye_demo.py
```

Controls:

- `q`: quit.
- `c`: start moving-dot calibration.
- Gaze: move cursor.
- Double blink: double click.

### Python Eye Game

```powershell
python game_eye_control.py
```

### OpenVINO Gaze Prototype

```powershell
python game_eye_openvino.py
```

Before running, confirm the required OpenVINO model files exist under `models/intel`.

### Python Hand/Gaze Game

```powershell
python game_hand.py
```

### Boxing Game

```powershell
python app_boxing_demo.py
```

Alternative package entry may also work depending on Python path:

```powershell
python -m boxing_game
```

## Web Prototype Setup

The web game uses the EyeDid/SeeSo SDK and should be served through `serve.py` because the SDK may require cross-origin isolation headers.

Run:

```powershell
python serve.py
```

Open:

```text
http://localhost:8090
```

Browser requirements:

- Camera permission enabled.
- Network access to the EyeDid CDN.
- Browser support for required SDK features.

## iOS Setup

Open the Xcode project:

```text
Spacefall_ios\Spacefall_ios.xcodeproj
```

Recommended development path:

1. Open the project in Xcode.
2. Select the `Spacefall_ios` scheme.
3. Use a physical iPhone with TrueDepth camera support for ARKit Face Tracking.
4. Confirm camera permissions in `Info.plist`.
5. Build and run on device.

Simulator note:

- ARKit Face Tracking generally requires physical device hardware. The simulator is useful for UI checks but not full gameplay validation.

## Testing Strategy

No automated test suite is currently present. Recommended validation layers:

### Static Validation

```powershell
python -m compileall .
```

This checks Python syntax but does not validate camera or gameplay behavior.

### Manual Python Smoke Tests

- Start each Python entry point and confirm the webcam opens.
- Confirm `q` exits cleanly.
- For posture, confirm landmarks appear and recalibration works.
- For gesture mouse, confirm move/click/drag/scroll states display before enabling sensitive workflows.
- For eye mouse, run calibration and confirm gaze dot/cursor movement stabilizes.
- For boxing, confirm menus, tutorial, training, fight, save, and load behaviors.

### Manual Web Smoke Tests

- Start `python serve.py`.
- Open `http://localhost:8090`.
- Confirm assets load.
- Confirm camera permission prompt appears.
- Confirm status/debug overlay shows tracker progress.
- Confirm calibration button does not throw console errors.
- Confirm gaze moves the ship across lanes.

### Manual iOS Smoke Tests

- Launch on a TrueDepth iPhone.
- Confirm episode menu renders.
- Confirm AR tracking starts when an episode begins.
- Confirm gaze indicator moves smoothly.
- Confirm blink, double blink, and jaw-open gestures trigger expected episode actions.
- Confirm game over/victory returns to menu.
- Confirm background music stops on quit.

## Deployment Notes

### Python Desktop

The Python demos are currently development scripts, not packaged apps. For distribution, consider:

- PyInstaller packaging for Windows.
- A launcher menu that selects posture, gesture mouse, eye mouse, boxing, or game demo.
- Camera and input-permission onboarding screens.
- Config profiles for different users and cameras.

### Web

Before public deployment:

- Move the EyeDid/SeeSo license key out of source control or replace it with a safe domain-restricted production key.
- Host over HTTPS.
- Keep COOP/COEP headers enabled if the SDK requires cross-origin isolation.
- Replace debug overlay with optional dev-mode logging.
- Add responsive canvas sizing for non-1280x720 displays.

### iOS

Before App Store release or update:

- Verify camera usage description is clear.
- Test on multiple TrueDepth devices.
- Confirm all audio/image assets are licensed and bundled correctly.
- Validate app privacy answers for camera usage and data collection.
- Add crash reporting and analytics if desired.

## Troubleshooting

### Webcam Does Not Open

- Try `--camera-id 1` or another ID.
- Close other apps using the camera.
- Check OS camera permissions.
- Confirm OpenCV can read from the device.

### Landmarks Are Jittery

- Improve lighting.
- Move closer to the camera.
- Keep the face/body centered.
- Increase smoothing windows in `config.yaml`.
- Raise detection confidence only if detection is stable enough.

### Mouse Movement Feels Wrong

- Revisit screen resolution mapping in `core/gesture_mouse_controller.py`.
- Adjust `gesture.smoothing_factor` in `config.yaml`.
- Reduce camera frame margins or calibrate mapping behavior.
- On Windows, replace the macOS-specific `system_profiler` resolution detection.

### Web Tracker Does Not Initialize

- Confirm CDN script loads.
- Confirm browser camera permission.
- Confirm `serve.py` is used instead of directly opening `index.html`.
- Check the debug overlay and browser console.
- Verify the SDK API shape has not changed.

### iOS Gaze Does Not Track

- Use a TrueDepth-capable device.
- Confirm camera permission.
- Check ARKit Face Tracking availability.
- Avoid poor lighting or face occlusion.
- Confirm `GazeEngine.shared.start()` is called when game mode begins.

