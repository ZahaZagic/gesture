# Technical Development Guide

Generated: 2026-05-04

This guide covers the Python desktop modules, boxing game, and web prototype. The iOS subproject has a standalone guide in `docs/IOS_TECHNICAL_DEVELOPMENT.md`.

## Repository Structure

```text
.
|-- app_posture_demo.py          # Posture monitoring entry point
|-- app_mouse_demo.py            # Hand gesture mouse entry point
|-- app_eye_demo.py              # Eye tracking mouse entry point
|-- app_boxing_demo.py           # Main boxing game implementation
|-- game_hand.py                 # Python episodic hand/gaze game
|-- game_eye_control.py          # Python gaze-controlled Space Rocks game
|-- game_eye_openvino.py         # OpenVINO gaze tracker prototype
|-- serve.py                     # Local web server with COOP/COEP headers
|-- config.yaml                  # Camera, posture, gesture thresholds
|-- requirements.txt             # Python dependencies
|-- assets/                      # Shared game art assets
|-- boxing_game/                 # Modular boxing game support package
|-- core/                        # Computer vision, posture, gesture, and rendering modules
|-- game_web_seeso/              # Browser EyeDid/SeeSo game prototype
|-- models/                      # OpenVINO model files
|-- utils/                       # Geometry and smoothing helpers
|-- Spacefall_ios/               # Native iOS app, documented separately
`-- docs/                        # Project documentation
```

## Runtime Dependencies

Primary Python dependencies:

- `opencv-python`: webcam capture, image drawing, image processing, report screenshots.
- `mediapipe`: pose, hands, and face mesh landmark detection.
- `numpy` and `scipy`: numeric calculations and geometry.
- `pyautogui` and `pynput`: desktop control for gesture and eye mouse flows.
- `reportlab`: PDF posture reports.
- `pyyaml`: configuration loading.
- `openvino` and `openvino-dev`: OpenVINO gaze model prototype.
- `win10toast`: optional Windows posture notifications.

## Configuration

`config.yaml` defines shared camera and interaction parameters.

Top-level settings:

- `camera_id`: default webcam index.
- `width`, `height`: capture resolution.
- `fps_target`: desired camera FPS.

`posture` settings include MediaPipe confidence thresholds, posture warning/critical thresholds, smoothing window, baseline calibration duration, sustained warning duration, notification controls, and visualization colors.

`gesture` settings include hand detection confidence, cursor sensitivity, EMA smoothing factor, movement threshold, pinch threshold, drag hold frames, scroll speed, and scroll mode.

## Core Python Modules

### `core/posture_detector.py`

Wraps MediaPipe Pose detection.

Responsibilities:

- Initialize `mp.solutions.pose.Pose`.
- Convert frames into pose detection results.
- Return 2D image landmarks and 3D world landmarks.

### `core/spine_kyphosis.py`

Computes posture metrics from MediaPipe landmarks.

Key implementation details:

- Uses shoulder, ear, eye, and nose landmarks.
- Computes shoulder slope, head tilt, shoulder height delta, lateral head offset, forward-head angle, forward-head projection, neck compaction, and landmark visibility quality.
- Uses 3D world landmarks when available to estimate camera-relative forward head offset.
- Treats kyphosis as a heuristic posture proxy rather than a medical Cobb-angle measurement.

### `core/face_alignment.py`

Computes face symmetry/alignment metrics from landmarks and frame geometry. It supplements posture metrics with head/face alignment signals.

### `core/posture_assessment.py`

Turns raw posture metrics into stable posture state.

Key implementation details:

- Maintains rolling metric histories using `deque`.
- Builds a per-user baseline during the configured calibration window.
- Computes deviations from baseline for forward head, lateral head, shoulder height, projection, and neck compaction.
- Applies warning and critical thresholds.
- Produces a structured assessment with `metrics`, `issues`, `status`, `score`, `calibrating`, and `sustained_bad`.
- Tracks `bad_since` to avoid noisy one-frame alerts.

### `core/posture_notifier.py`

Sends posture reminders.

Responsibilities:

- Respect notification enablement and cooldown settings.
- Provide sound or desktop alerts where supported.
- Use `win10toast` when available on Windows.

### `core/overlay_renderer.py` And `core/guidance_bubbles.py`

Render posture landmarks, lines, metrics, guidance messages, and status feedback onto OpenCV frames.

### `core/report_exporter.py`

Generates a posture report using captured metrics and screenshot imagery.

### `core/gesture_detector.py`

Wraps MediaPipe Hands.

Responsibilities:

- Process frames for hand landmarks.
- Return the first detected hand landmarks and handedness metadata.

### `core/gesture_state_machine.py`

Classifies hand landmark geometry into mouse states.

States:

- `IDLE`: no active gesture.
- `MOVE`: index finger extended.
- `CLICK_LEFT`: thumb and middle finger pinch.
- `CLICK_RIGHT`: thumb and index finger pinch.
- `DRAG`: fist.
- `SCROLL`: open hand.

Key implementation details:

- Uses normalized distances from `utils/geometry.py`.
- Checks finger extension by comparing fingertip-to-wrist distance against PIP-to-wrist distance.
- Uses a small state buffer and majority vote to reduce jitter.
- Emits transition actions like `START_MOVE` and hold actions like `HOLD_MOVE`.

### `core/gesture_mouse_controller.py`

Executes mouse actions using `pynput`.

Key implementation details:

- Maps normalized camera coordinates into screen pixels using a central region of interest.
- Applies exponential smoothing to cursor coordinates.
- Handles left click, right click, drag press/release, scroll, move, and double click.
- Defaults to `1920x1080` if screen resolution detection fails.

Note: screen resolution detection currently uses macOS `system_profiler`, which does not match the Windows development environment. A cross-platform resolution method is recommended.

### `core/gaze_tracker.py`

Tracks gaze from MediaPipe Face Mesh iris landmarks.

Key implementation details:

- Uses refined face mesh landmarks for iris points.
- Computes iris displacement relative to each eye center and eye width.
- Averages left and right eye gaze offsets.
- Supports calibration by collecting raw eye-space points and normalized screen-space targets.
- Uses `cv2.findHomography` with RANSAC to map gaze offsets to screen coordinates.
- Falls back to simple scaling when calibration has not been completed.

### `core/blink_detector.py`

Detects blink and double-blink events using eye aspect ratio style calculations from face landmarks.

### `utils/geometry.py`

Provides reusable geometry helpers:

- `calculate_distance`
- `calculate_distance_normalized`
- `get_midpoint`
- `map_range`

### `utils/smoothing.py`

Provides reusable smoothing filters:

- `ExponentialSmoothing`: simple EMA for cursor positions.
- `AdaptiveSmoothing`: velocity-aware smoothing for gaze movement.

## Python Entry Points

### `app_posture_demo.py`

Purpose: run posture monitoring in preview or background mode.

Flow:

1. Load `config.yaml`.
2. Open webcam and configure capture dimensions/FPS.
3. Initialize posture detector, metric calculators, assessment, notifier, renderer, guidance bubbles, and report exporter.
4. For each frame, detect pose landmarks.
5. Calculate posture metrics and assess status.
6. Render landmarks, lines, metrics, and guidance when not in background mode.
7. Notify on sustained bad posture.
8. Press `r` to export a report, `c` to recalibrate, or `q` to quit.

Command examples:

```powershell
python app_posture_demo.py
python app_posture_demo.py --background
python app_posture_demo.py --camera-id 1
```

### `app_mouse_demo.py`

Purpose: control the desktop mouse with hand gestures and double blink.

Flow:

1. Load config and webcam.
2. Detect hand landmarks and blink events.
3. Classify hand pose through `GestureStateMachine`.
4. Execute mouse actions through `GestureMouseController`.
5. Draw hand landmarks, state text, cursor mapper, and instructions.
6. Release drag when leaving the `DRAG` state.

Command:

```powershell
python app_mouse_demo.py
```

### `app_eye_demo.py`

Purpose: control the desktop mouse with gaze and blink.

Flow:

1. Load config and webcam.
2. Detect gaze and blinks.
3. Optional calibration starts with `c`.
4. Moving-dot calibration collects raw gaze and target coordinate pairs.
5. Homography calibration maps eye-space to screen-space.
6. Adaptive smoothing controls cursor motion.
7. Double blink triggers double click.

Command:

```powershell
python app_eye_demo.py
```

### `game_eye_control.py`

Purpose: Python Space Rocks eye-control game.

Main classes:

- `EyeInput`: gaze update and calibration management.
- `Ship`: player entity.
- `Asteroid`: falling obstacle entity.
- `SpaceRocksGame`: game loop, calibration UI, spawning, reset, rendering.

### `game_eye_openvino.py`

Purpose: OpenVINO gaze estimation prototype.

Main class: `OpenVINOGazeTracker`.

Responsibilities:

- Load face detection, facial landmarks, head pose, and gaze estimation models from `models/intel`.
- Preprocess images for model inference.
- Detect face, landmarks, head pose, and gaze vector.
- Process frames and map gaze through calibration.

### `game_hand.py`

Purpose: Python multimodal episodic game engine.

Main classes:

- `AssetLoader`: image loading and variant selection.
- `SoundManager`: BGM/SFX playback and volume updates.
- `HandInput`: camera-based hand input.
- `Episode`: base episode interface.
- `AvoidanceEpisode`: obstacle avoidance gameplay.
- `MedusaEpisode`: gaze/target transformation gameplay.
- `DragonEpisode`: dragon combat gameplay.
- `DesertEpisode`: additional themed obstacle gameplay.
- `Obstacle`, `Figure`, `Mirror`, `DragonTarget`, `Projectile`: game entities.
- `GazeOfTheCosmosEngine`: top-level menu, settings, episode updates, drawing, and runtime loop.

## Boxing Game Subproject

### Business Intent

The boxing game turns body movement into a boxing career simulator. The user trains punches and defenses, earns career progress, unlocks arenas, and fights increasingly difficult opponents.

### Files

#### `app_boxing_demo.py`

Main implementation file. It contains `BoxingCommandArena`, which owns the game state, UI rendering, motion detection, tutorial flow, training flow, fight logic, career state, save/load, and the OpenCV game loop.

Major responsibilities:

- Load visual/audio assets.
- Manage hub, locker, training, tutorial, and fight scenes.
- Detect offense moves such as straight punches, hooks, and uppercuts.
- Detect defense moves such as guard, slips, and duck.
- Track wrist motion memory and summarize movement vectors.
- Match user movements against learned profiles.
- Queue enemy attacks, blocks, real-time exchanges, and target prompts.
- Resolve hit, block, timeout, knockdown, stamina, combo, HP, and round outcomes.
- Render HUD, target cards, prompts, opponent, gloves, menus, and training overlays.

#### `boxing_game/constants.py`

Defines gameplay constants and structured content:

- Window and timing constants.
- Color palette.
- Offensive and defensive move definitions.
- Tutorial sequence.
- Career arenas with unlock rules, prizes, fees, enemy difficulty, and narrative challenge text.
- Hub and training menu labels.
- Opponent roster metadata.

#### `boxing_game/career.py`

Defines `BoxingCareer`.

Responsibilities:

- Store player name, cash, points, record, stats, techniques, belt status, sponsor tasks, and match history.
- Calculate world rank from points and record.
- Gate arena unlocks.
- Calculate match score and rewards.
- Apply win/loss results, costs, payouts, points, belt progression, sponsor rewards, and history logging.
- Price and apply training upgrades.
- Progress punch technique levels.

#### `boxing_game/motion.py`

Defines motion profile helpers.

Responsibilities:

- Define feature keys for each punch family.
- Determine tutorial repetition targets.
- Merge new motion samples into learned profiles using running averages and min/max ranges.
- Compare live motion to learned profiles with tolerance windows and vote thresholds.

#### `boxing_game/storage.py`

Defines `SaveStore` for JSON persistence.

Responsibilities:

- Load `save_data.json` safely.
- Save payloads with indentation.
- Create the save directory if needed.

#### `boxing_game/audio.py`

Defines `AudioManager` for sound effect and looping audio support.

#### `boxing_game/app.py` And `boxing_game/__init__.py`

Provide package-level exports and entry points for `BoxingCommandArena` and `main`.

## Web Eye-Controlled Game

### Files

#### `game_web_seeso/index.html`

- Loads `style.css` and the EyeDid SDK from CDN.
- Creates a debug overlay, loading message, game canvas, score UI, calibration button, and status text.
- Loads `game.js`.

#### `game_web_seeso/game.js`

Main browser implementation.

Responsibilities:

- Load ship, asteroid, and background assets.
- Initialize canvas and UI events.
- Initialize EyeDid/SeeSo tracker.
- Request camera permission.
- Register gaze and calibration callbacks.
- Map gaze coordinates to normalized canvas coordinates.
- Spawn asteroids, move ship by gaze lane, update score, detect collisions, render game state, and support reset.

Important implementation notes:

- `LANES = 8` divides the canvas into gaze-controlled movement lanes.
- `startCalibration` is defined twice; this should be consolidated.
- The license key is currently hard-coded in client-side JavaScript; this is acceptable only for local prototype use and should be moved to a safer configuration strategy before public deployment.

#### `game_web_seeso/style.css`

Styles the fixed-size `1280x720` game container, full-canvas rendering, score/status UI, calibration button, and loading text.

#### `serve.py`

Serves `game_web_seeso` on port `8090` with headers required by SDKs that use `SharedArrayBuffer`:

- `Cross-Origin-Embedder-Policy: require-corp`
- `Cross-Origin-Opener-Policy: same-origin`

Command:

```powershell
python serve.py
```

Then open:

```text
http://localhost:8090
```

## OpenVINO Models

The `models/intel` directory contains OpenVINO model files for:

- `face-detection-adas-0001`
- `facial-landmarks-35-adas-0002`
- `gaze-estimation-adas-0002`
- `head-pose-estimation-adas-0001`

Each model includes precision variants such as `FP16`, `FP16-INT8`, and `FP32`.

## Technical Patterns

### Calibration

The project uses calibration in multiple ways:

- Posture calibration: build a neutral baseline for per-user posture deviations.
- Eye mouse calibration: map raw iris offsets to screen targets using homography.
- Web/iOS calibration: use SDK or ARKit-derived gaze normalization and smoothing.
- Boxing training calibration: learn user-specific motion profiles from repeated reps.

### Smoothing

Smoothing is critical because camera landmarks are noisy.

- Posture uses rolling averages over a configurable window.
- Mouse control uses exponential smoothing.
- Eye control uses adaptive smoothing so static gaze is stable and fast gaze remains responsive.
- iOS uses trend-aware smoothing in `GazeEngine`.

### State Machines

State machine logic appears in:

- Gesture mouse: stable gesture classification and action transitions.
- Posture: calibrating, low confidence, good, warning, critical, sustained bad.
- Boxing: hub, tutorial, training, fight, prompt resolution, round resolution.
- iOS scenes: intro, playing, victory, game over, exiting.

## Known Technical Debt

- No automated test suite is currently present.
- Some files are very large, especially `app_boxing_demo.py`, which would benefit from separation into input, game state, rendering, and scene modules.
- `core/gesture_mouse_controller.py` contains duplicate `DOUBLE_CLICK_LEFT` handling and macOS-specific screen-size detection.
- `game_web_seeso/game.js` contains duplicate `startCalibration` definitions.
- The web license key is hard-coded in client code.
- Python entry points depend on webcam and desktop input permissions, which makes automated validation harder.

