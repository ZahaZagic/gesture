# iOS Technical Development Guide

Generated: 2026-05-04

This document covers the native iOS subproject under `Spacefall_ios/`. The Python and web portions are documented in `docs/TECHNICAL_DEVELOPMENT.md`.

## Product Summary

The iOS app is a native SwiftUI and SpriteKit game called Above Saturn / Spacefall. It uses ARKit Face Tracking to convert gaze and face expressions into hands-free gameplay. The app presents six music-inspired episodes with different mechanics, art, rewards, difficulty behavior, and face-triggered actions.

## iOS Technology Stack

- SwiftUI: app shell, main menu, episode selection, HUD overlays, animated background.
- SpriteKit: real-time gameplay scenes, sprites, collisions, actions, emitters, camera shake, particles, and scene transitions.
- ARKit: face tracking and `lookAtPoint` gaze signal.
- CoreMotion: device pitch/roll signals for supplementary orientation handling.
- AVFoundation: background music and sound effects.
- UserDefaults: high-score persistence.
- UIKit: idle timer control, haptics, links, colors, and visual effects.

## Directory Structure

```text
Spacefall_ios/
|-- Info.plist
|-- Spacefall_ios.xcodeproj/
`-- Spacefall_ios/
    |-- Spacefall_iosApp.swift       # App entry point
    |-- MainMenuView.swift           # SwiftUI menu, HUD, scene creation
    |-- GazeEngine.swift             # ARKit gaze/gesture state engine
    |-- GestureManager.swift         # Face-expression gesture detection
    |-- BaseEpisodeScene.swift       # Shared SpriteKit scene lifecycle and UI
    |-- AvoidanceScene.swift         # Episodes 1 and 2 mechanics
    |-- TargetScene.swift            # Episodes 3 and 5 mechanics
    |-- DragonScene.swift            # Episode 4 boss mechanics
    |-- HighwayScene.swift           # Episode 6 traffic mechanics
    |-- EpisodeConfig.swift          # Episode metadata and asset names
    |-- SoundManager.swift           # BGM/SFX management
    |-- ColorExtensions.swift        # Shared color palette
    |-- Localizable.strings          # Localized strings
    |-- Assets.xcassets/             # Episode art, app icon, backgrounds
    `-- Models/EpisodeConfig.swift  # Duplicate/legacy model file placeholder
```

## App Entry Point

### `Spacefall_iosApp.swift`

Responsibilities:

- Defines the `@main` app.
- Disables the iOS idle timer so the screen does not turn off during gaze-controlled play.
- Presents `MainMenuView` in the main window.

## SwiftUI Shell

### `MainMenuView.swift`

Responsibilities:

- Displays animated menu background and episode list.
- Starts/stops `GazeEngine` when gameplay begins or ends.
- Creates the correct SpriteKit scene for the selected episode.
- Hosts `SpriteView` for gameplay.
- Provides touch/drag fallback input by converting drag location into gaze coordinates.
- Renders SwiftUI HUD for score, HP, ammo, jump energy, boss HP, and episode-specific counters.
- Handles tracking error alerts from `GazeEngine`.

Scene routing:

- Episodes 1 and 2 use `AvoidanceScene`.
- Episodes 3 and 5 use `TargetScene`.
- Episode 4 uses `DragonScene`.
- Episode 6 uses `HighwayScene`.
- Unknown episode IDs fall back to `BaseEpisodeScene`.

## Shared Gaze And Gesture Engine

### `GazeEngine.swift`

`GazeEngine` is a singleton `NSObject`, `ARSessionDelegate`, and `ObservableObject`. It is the shared state bridge between ARKit, SwiftUI HUD, and SpriteKit gameplay.

Responsibilities:

- Start and stop `ARSession` with `ARFaceTrackingConfiguration`.
- Receive face anchors from ARKit.
- Extract `lookAtPoint` and normalize it into screen-style coordinates.
- Smooth gaze using a trend-aware filter.
- Convert gaze X into lane index.
- Track global gameplay state such as score, HP, max HP, ammo, weapon level, boss HP, rewards, jump energy, and episode counters.
- Save and read high scores with `UserDefaults`.
- Publish UI-visible values through `@Published` properties.
- Surface ARKit errors and interruptions.

Important implementation details:

- `resetState(for:)` initializes episode-specific counters and resources.
- `start()` configures AR face tracking.
- `session(_:didUpdate:)` receives face anchors and updates gaze and face gestures.
- `updateGaze(xAxis:yAxis:)` clamps, smooths, and converts gaze coordinates into lane state.
- Lane movement steps one lane at a time toward the target lane to prevent over-jumpy control.

### `GestureManager.swift`

`GestureManager` extracts expression signals from `ARFaceAnchor.blendShapes`.

Tracked gestures:

- Left-eye blink.
- Right-eye blink.
- Any single blink.
- Double blink.
- Jaw open.

These gestures are interpreted differently by each episode.

## Shared SpriteKit Base Scene

### `BaseEpisodeScene.swift`

Responsibilities:

- Own shared scene lifecycle and phase management.
- Set up camera, background, eye indicator, narrative intertitle, music link, and common UI elements.
- Track score and HP through `GazeEngine`.
- Handle damage, healing, game over, victory, rewards, camera shake, particles, and quitting.
- Show/hide SwiftUI HUD via `GazeEngine.shared.isGameplayHUDVisible`.
- Map gaze into an on-screen eye indicator each frame.

Scene phases:

- `intro`: narrative/intertitle is visible.
- `playing`: gameplay is active.
- `victory`: episode completed.
- `gameOver`: terminal failure state.
- `exiting`: returning to menu.

Shared gameplay helpers:

- `takeDamage()` and `modifyHP(by:feedback:)`.
- `evaluateGameOver()`.
- `shakeCamera(duration:intensity:)`.
- `createExplosion(at:color:)`.
- `spawnPersistentReward(type:at:)`.
- `applyReward(type:)`.
- `updateRewardPersistence()`.
- `completeEpisode(...)`.
- `requestQuit()`.

## Episode Configuration

### `EpisodeConfig.swift`

Defines each episode as data:

- `id`
- `name`
- `quote`
- `instruction`
- `bgAsset`
- `alternateBackgroundAssets`
- `playerAsset`
- `obstacleAsset`
- `sfxAsset`
- `bgmAssets`

Episodes:

1. `SPACE FALL`: steer ship with eyes, double blink to fire, break asteroids, collect rewards.
2. `GLACIER ESCAPE`: steer runner with eyes, blink to jump, collect checkpoints.
3. `CURSE OF GLIMPSE`: gaze target falling characters, double blink to cast, avoid mirrors, jaw-open cleanse.
4. `DRAGON RAGE`: steer dragon, eat food, jaw-open fire breath, boss combat.
5. `SPIRITUAL RECON`: memorize coffin board, scan bottom row, blink to dig, avoid ghosts, collect treasure.
6. `ROAD RAGE 405`: steer bike through traffic, double blink to throw projectiles, avoid heavy vehicles.

## Episode Scene Implementations

### `AvoidanceScene.swift`

Used by episodes 1 and 2.

Episode 1 responsibilities:

- Spawn asteroids/satellites.
- Move ship based on gaze X and lanes.
- Handle laser firing with blink/double-blink input.
- Scale weapon level and temporary weapon upgrades.
- Support projectile patterns such as homing, spiral, and zigzag depending on level.
- Spawn rewards such as hearts, barrier, or upgrades.
- Increase difficulty over time.

Episode 2 responsibilities:

- Spawn ice obstacles and checkpoints.
- Move player laterally with gaze.
- Use blink transitions for jump behavior.
- Track jump energy and checkpoints.
- Apply difficulty ramping.

### `TargetScene.swift`

Used by episodes 3 and 5.

Episode 3 responsibilities:

- Spawn humans, monsters, mirrors, rewards, and bombs across lanes.
- Use gaze position to choose best target.
- Use blink/double-blink to cast or transform targets.
- Use jaw-open as a screen-level cleanse action when charges are available.
- Track population or HP-like episode counters.

Episode 5 responsibilities:

- Generate a memory board of covered coffins.
- Assign hidden content such as treasure or ghosts.
- Let gaze hover/select cells.
- Use blink to dig selected cells.
- Add ghost pressure and treasure progression.

### `DragonScene.swift`

Used by episode 4.

Responsibilities:

- Move dragon by gaze.
- Spawn food and targets.
- Track fire ammo and boss HP.
- Use jaw-open for fire attacks.
- Run boss movement patterns and fireball attacks.
- Increase boss behavior difficulty across phases.

### `HighwayScene.swift`

Used by episode 6.

Responsibilities:

- Render a scrolling highway.
- Move bike/rider with gaze lanes.
- Spawn vehicle traffic with lane spacing safety checks.
- Spawn brick/projectile ammo.
- Use double blink to throw projectiles.
- Make lighter vehicles dodge while heavy trucks resist.
- Track traffic density and difficulty over time.

## Audio System

### `SoundManager.swift`

Responsibilities:

- Play episode background music from configured candidates.
- Queue and transition tracks.
- Play sound effects.
- Track temporary SFX players by UUID to avoid early deallocation.
- Stop all audio on scene exit.
- Provide Spotify album URL for narrative/music links.

## Visual System

### `ColorExtensions.swift`

Defines reusable colors such as cosmic primary, nebula rose, slate tones, and background colors. These colors create a consistent sci-fi visual identity across SwiftUI and SpriteKit.

### `Assets.xcassets`

Contains episode-specific art:

- `ep1`: ship, asteroids, lasers, backgrounds.
- `ep2`: glacier runner, ice, gate/checkpoint assets.
- `ep3`: humans, monsters, stoned variants, mirror, rewards, bombs.
- `ep4`: dragon, bosses, fire, food, backgrounds.
- `ep5`: tombs, ghosts, treasure, backgrounds.
- `ep6`: bike, cars, trucks, projectiles, road background.

## Data Flow

```text
ARKit Face Tracking
        |
        v
GazeEngine.session(_:didUpdate:)
        |
        +--> GestureManager.update(with:)
        |
        +--> GazeEngine.updateGaze(xAxis:yAxis:)
        |
        v
Published GazeEngine state
        |
        +--> SwiftUI HUD in MainMenuView
        |
        +--> SpriteKit scenes during update loops
                    |
                    v
              Game objects, score, HP, ammo, rewards, victory/game-over
```

## Implementation Strengths

- Strong separation between SwiftUI shell, shared gaze engine, base scene behavior, and episode scenes.
- Data-driven episode metadata makes content expansion easier.
- Shared `BaseEpisodeScene` avoids repeating core HP, score, reward, background, and terminal-state behavior.
- ARKit-based face tracking provides native, low-latency gaze and expression signals on supported devices.
- SwiftUI HUD sits above SpriteKit without forcing all UI into SpriteKit nodes.

## iOS Technical Debt And Risks

- Some scenes are large and could be split into episode-specific systems for spawning, collision, rewards, and input handling.
- `Spacefall_ios/Spacefall_ios/Models/EpisodeConfig.swift` appears redundant or placeholder-like compared with the main `EpisodeConfig.swift`; verify whether it is needed.
- Asset names include spaces and mixed conventions; future automation would be easier with normalized names.
- ARKit Face Tracking requires compatible devices with TrueDepth camera support.
- Automated tests are not currently present for scene logic or gaze smoothing.

## Recommended iOS Refactors

- Extract reusable lane math into a `LaneController` or `LaneGrid` helper.
- Extract projectile behavior into reusable SpriteKit components.
- Add deterministic unit tests for `GazeEngine.updateGaze`, lane conversion, high-score persistence, and episode reset state.
- Add a debug overlay for raw gaze, smoothed gaze, lane index, blink state, jaw state, FPS, and current scene phase.
- Normalize asset naming before expanding more episodes.

