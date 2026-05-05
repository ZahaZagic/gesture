# Business Logic Summary

Generated: 2026-05-04

## Executive Summary

This project is a multimodal accessibility and interactive gaming platform. It uses webcam, face, eye, hand, posture, and mobile AR signals to let users control software without traditional keyboard, mouse, or touch input. The product direction combines three themes:

- Accessibility: Hands-free and low-touch computer control using gaze, blink, and hand gestures.
- Wellness: Real-time posture analysis with feedback, sustained-bad-posture detection, alerts, and PDF reporting.
- Entertainment and HCI: Gesture- and gaze-controlled games that turn body movement into gameplay mechanics.

The repository contains multiple product surfaces: Python desktop demos, a web eye-controlled game prototype, a boxing command game, and a native iOS episodic game called Above Saturn / Spacefall.

## Business Goals

- Demonstrate practical human-computer interaction using commodity webcams and mobile AR sensors.
- Provide accessibility-oriented controls for users who benefit from hands-free cursor movement, blink clicks, or gesture actions.
- Convert body-awareness and posture monitoring into actionable feedback rather than static measurement.
- Package gaze and gesture interaction into game mechanics that are easier to understand, test, and showcase.
- Support portfolio and resume storytelling around computer vision, ARKit, MediaPipe, OpenCV, OpenVINO, SpriteKit, and multimodal interaction design.

## User Groups

- Accessibility users who need alternate input methods.
- Developers and researchers evaluating gesture, gaze, blink, and posture interaction patterns.
- Casual players interested in eye-controlled or motion-controlled games.
- Product reviewers, recruiters, or portfolio readers who need a clear technical story.

## Major Business Capabilities

### 1. Posture Analysis And Coaching

The posture workflow uses webcam pose landmarks to estimate shoulder balance, head tilt, lateral head offset, forward-head posture, neck compaction, and landmark quality. The business value is immediate posture feedback and longer-running background monitoring.

Key behaviors:

- Calibrates a user baseline during the first few seconds.
- Smooths noisy frame-level posture metrics before scoring.
- Classifies posture into good, warning, critical, low confidence, or no pose.
- Shows visual overlays and guidance bubbles in interactive mode.
- Sends sustained-bad-posture notifications in background mode.
- Exports reports with posture metrics and screenshots.

### 2. Gesture Air Mouse

The gesture mouse turns hand poses and blinks into desktop mouse actions. It provides a low-touch input alternative with visible feedback for debugging and learning.

Key behaviors:

- Index-finger movement maps to cursor movement.
- Thumb and middle-finger pinch triggers left click.
- Thumb and index-finger pinch triggers right click.
- Fist gesture holds drag.
- Open hand scrolls.
- Double blink triggers double click.
- Smoothing and state buffering reduce accidental actions.

### 3. Eye Tracking Mouse

The eye mouse maps iris position to screen coordinates using MediaPipe Face Mesh, optional homography calibration, and adaptive smoothing.

Key behaviors:

- Detects iris landmarks and computes normalized gaze offsets.
- Supports a moving-dot calibration path.
- Uses homography to map eye-space data to screen-space targets.
- Smooths gaze dynamically so small jitter is stable while fast eye movement remains responsive.
- Uses double blink as a double-click interaction.

### 4. Space-Themed Python Hand/Gaze Game

The Python game layer packages gaze and hand interaction into a series of playable episodes and prototypes. The core product idea is to make multimodal control visible and fun.

Key behaviors:

- Uses camera input to control player movement or actions.
- Loads themed assets for space, glacier, Medusa, dragon, desert, and obstacle scenarios.
- Includes sound management, animated menus, settings, episodes, obstacles, projectiles, and scoring.
- Demonstrates how gaze and gestures can drive real-time game state.

### 5. Boxing Command Arena

The boxing game is a career-mode motion training and fighting prototype. It uses body and wrist movement to classify punches, defensive moves, training reps, and menu controls.

Key behaviors:

- Lets players progress through arenas with entry fees, prizes, unlock rules, opponents, and career rank.
- Tracks wins, losses, cash, points, training stats, techniques, and sponsor tasks.
- Provides tutorial and training flows for punch and defense movement patterns.
- Learns motion profiles over repeated training samples and uses tolerance-based matching during fights.
- Supports save/load through JSON persistence.
- Contains visual UI panels, opponent sprites, player gloves, target prompts, stamina, HP, and round logic.

### 6. Web Eye-Controlled Game Prototype

The web version is a lightweight browser prototype using the EyeDid/SeeSo SDK. It demonstrates gaze-to-lane control in a canvas game.

Key behaviors:

- Initializes the EyeDid/SeeSo SDK with camera permission.
- Offers calibration hooks and visible calibration targets.
- Maps gaze coordinates to one of eight lanes.
- Spawns falling asteroids and checks collisions against a player ship.
- Uses COOP/COEP headers through the local server for SDK compatibility.

### 7. Native iOS Game: Above Saturn / Spacefall

The iOS subproject is the most production-like game surface. It uses SwiftUI for menus and HUD, SpriteKit for gameplay scenes, ARKit Face Tracking for gaze and face gestures, CoreMotion for device orientation, AVFoundation for audio, and UserDefaults for scores.

Key behaviors:

- Presents six episodes with distinct mechanics, art, music, and instructions.
- Uses ARKit lookAtPoint and smoothing to steer lanes and player position.
- Uses blink, double blink, and jaw-open gestures for firing, jumping, casting, digging, cleansing, or attacking depending on episode.
- Uses SpriteKit scenes for avoidance, target, dragon boss, and highway gameplay.
- Tracks HP, score, ammo, rewards, boss HP, high scores, and episode-specific counters.
- Adds narrative intertitles and music-driven presentation.

## End-To-End User Journeys

### Posture Monitor Journey

1. User runs the posture demo.
2. The webcam opens and MediaPipe Pose detects body landmarks.
3. The app calibrates a neutral baseline.
4. Each frame is scored for shoulder and head posture issues.
5. The UI displays metrics and guidance.
6. If posture remains bad long enough, the app notifies the user.
7. User can export a report from the current frame.

### Gesture Mouse Journey

1. User runs the gesture mouse demo.
2. The webcam detects hand landmarks and face blinks.
3. The state machine classifies hand pose into move, click, drag, or scroll.
4. The mouse controller maps normalized coordinates to screen pixels.
5. The user receives a visual overlay showing current state and mapped cursor region.

### Eye Mouse Journey

1. User runs the eye demo.
2. The app detects iris movement and blink events.
3. User can press `c` to follow a moving calibration dot.
4. Calibration data builds a gaze-to-screen homography.
5. Smoothed gaze controls mouse movement.
6. Double blink triggers double click.

### iOS Game Journey

1. User opens the iOS app and selects an episode.
2. `GazeEngine` starts AR face tracking.
3. The selected SpriteKit scene loads art, audio, and instructions.
4. Gaze steers the player or targeting cursor.
5. Face gestures trigger attacks, jumps, digs, or special actions.
6. The scene updates score, HP, rewards, and episode-specific goals.
7. Game over or victory returns the user to the menu.

## Success Metrics

Potential business/product metrics for future development:

- Input accuracy: percentage of intended gestures/gaze actions recognized correctly.
- Control latency: time from body/eye movement to on-screen response.
- Calibration completion rate and calibration duration.
- Session length and replay rate for games.
- Posture alert precision: number of helpful alerts versus false positives.
- Accessibility usability score from hands-free users.
- Crash-free sessions for Python demos, web prototype, and iOS app.

