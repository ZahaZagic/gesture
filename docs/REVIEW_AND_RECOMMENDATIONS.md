# Review And Recommendations

Generated: 2026-05-04

## Overall Assessment

This repository demonstrates a strong multimodal HCI portfolio: real-time camera input, posture assessment, gesture mouse control, gaze calibration, OpenVINO experimentation, web eye tracking, and a native iOS ARKit/SpriteKit game. The project has real breadth and multiple compelling product stories.

The main improvement opportunity is maintainability. Several implementation files have grown into large prototypes that combine input processing, game state, rendering, assets, UI, and persistence. That is normal for exploratory creative coding, but the next stage should separate systems so the project is easier to test, polish, and explain.

## Highest-Value Improvements

### 1. Add Automated Tests Around Pure Logic

Good first test targets:

- `utils/geometry.py`
- `utils/smoothing.py`
- `core/gesture_state_machine.py`
- `core/posture_assessment.py`
- `boxing_game/career.py`
- `boxing_game/motion.py`

These modules do not require a webcam if mocked landmarks or synthetic metrics are used.

### 2. Split Large Game Files

Recommended split for `app_boxing_demo.py`:

- `boxing_game/input.py`: pose and wrist memory.
- `boxing_game/rules.py`: hit/block/round resolution.
- `boxing_game/scenes.py`: hub, training, fight, tutorial scene state.
- `boxing_game/rendering.py`: all OpenCV drawing helpers.
- `boxing_game/assets.py`: asset loading and sprite helpers.

Recommended split for large iOS scenes:

- Spawn systems.
- Collision systems.
- Reward systems.
- Projectile systems.
- Lane/gaze movement helpers.

### 3. Improve Cross-Platform Mouse Mapping

`core/gesture_mouse_controller.py` currently attempts macOS screen detection through `system_profiler`, then defaults to `1920x1080`. On Windows, this can make cursor mapping inaccurate.

Recommended options:

- Use `pyautogui.size()` for cross-platform screen size.
- Allow screen dimensions in `config.yaml`.
- Add a calibration step for camera-to-screen mapping.

### 4. Remove Duplicate Logic

Known duplicates:

- `core/gesture_mouse_controller.py` has duplicate `DOUBLE_CLICK_LEFT` branches.
- `game_web_seeso/game.js` defines `startCalibration` twice.
- `Spacefall_ios/Spacefall_ios/Models/EpisodeConfig.swift` appears redundant with `Spacefall_ios/Spacefall_ios/EpisodeConfig.swift`.

### 5. Protect Credentials And Keys

`game_web_seeso/game.js` contains a client-side EyeDid/SeeSo license key. If this remains a local-only prototype, document that clearly. If deployed publicly, use a production-safe key strategy such as:

- Domain-restricted key.
- Environment-injected config at build/deploy time.
- Backend-issued token if supported by the provider.

### 6. Create A Unified Launcher

A simple launcher would make the project easier to demo:

- Posture monitor.
- Gesture mouse.
- Eye mouse.
- Boxing game.
- Python hand/gaze game.
- Web server launcher.

This could be a CLI menu first, then later a small desktop UI.

### 7. Add Debug/Calibration Modes

For all gaze/gesture experiences, add a consistent debug overlay showing:

- Raw input coordinates.
- Smoothed coordinates.
- Current state.
- Confidence/visibility.
- Active gesture.
- FPS.
- Calibration status.

This makes demos much easier to troubleshoot live.

## Product Recommendations

### Accessibility Track

Position posture, gaze mouse, and gesture mouse as a single accessibility input suite. Add:

- User profiles.
- Calibration wizard.
- Action remapping.
- Sensitivity presets.
- Practice mode.
- Safety confirmation for click/drag actions.

### Game Track

Position Above Saturn as the polished flagship. Add:

- Onboarding tutorial per gesture.
- Episode completion records.
- Difficulty options.
- More explicit calibration feedback.
- Analytics around where users fail or quit.

### Portfolio Track

For resume/interview use, lead with:

- ARKit gaze engine.
- Real-time smoothing and gesture recognition.
- Cross-platform prototypes.
- Game mechanics driven by face/eye input.
- Computer vision posture and accessibility tooling.

## Documentation Recommendations

Keep these docs updated during future development:

- Update `BUSINESS_LOGIC.md` when user-facing behavior changes.
- Update `TECHNICAL_DEVELOPMENT.md` when Python/web file responsibilities change.
- Update `IOS_TECHNICAL_DEVELOPMENT.md` when Swift files or episode mechanics change.
- Update `OPERATIONS_GUIDE.md` when run commands, dependencies, or deployment assumptions change.
- Update `RESUME_BULLETS.md` when impact, App Store status, or technical claims change.

## Suggested Next Milestones

1. Add tests for `boxing_game/career.py`, `boxing_game/motion.py`, `utils/smoothing.py`, and `core/posture_assessment.py`.
2. Fix duplicate `DOUBLE_CLICK_LEFT` and duplicate web `startCalibration` logic.
3. Replace screen-size detection with a cross-platform method.
4. Add a top-level `README.md` that links to `docs/README.md` and gives quick run commands.
5. Create short demo videos or GIFs for posture, gesture mouse, boxing, and iOS gameplay.

