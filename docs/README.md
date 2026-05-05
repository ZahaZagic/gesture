# Gesture Project Documentation Index

Generated: 2026-05-04

This documentation set summarizes the gesture, gaze, posture, game, and cross-platform pieces in this repository.

## Documents

- [Business Logic Summary](./BUSINESS_LOGIC.md): Product purpose, user value, major modules, workflows, and business-facing feature logic.
- [Technical Development Guide](./TECHNICAL_DEVELOPMENT.md): Python and web architecture, file responsibilities, key algorithms, and implementation notes.
- [iOS Technical Development Guide](./IOS_TECHNICAL_DEVELOPMENT.md): Standalone documentation for the native SwiftUI, SpriteKit, and ARKit version.
- [Operations Guide](./OPERATIONS_GUIDE.md): Local setup, run commands, testing approach, deployment notes, and troubleshooting.
- [Review And Recommendations](./REVIEW_AND_RECOMMENDATIONS.md): Current risks, maintainability observations, and suggested next improvements.
- [Resume Bullets](./RESUME_BULLETS.md): Resume-ready bullet points in the style of the provided resume template.

## Project Snapshot

This repository contains a multimodal human-computer interaction project centered on camera-based posture assessment, hand gesture mouse control, gaze tracking, and hands-free games. It includes:

- Python/OpenCV demos for posture analysis, hand gesture mouse control, eye tracking mouse control, and gaze/gesture games.
- A boxing game prototype with career progression, motion recognition, training, and save data.
- A web eye-controlled game prototype using EyeDid/SeeSo.
- A native iOS game, Above Saturn / Spacefall, built with SwiftUI, SpriteKit, ARKit Face Tracking, CoreMotion, and AVFoundation.

## Upkeep Notes

When the code changes, update the docs in this order:

1. Update business behavior in [Business Logic Summary](./BUSINESS_LOGIC.md).
2. Update file/function changes in [Technical Development Guide](./TECHNICAL_DEVELOPMENT.md) or [iOS Technical Development Guide](./IOS_TECHNICAL_DEVELOPMENT.md).
3. Update run/test/deploy changes in [Operations Guide](./OPERATIONS_GUIDE.md).
4. Add resume bullet refinements to [Resume Bullets](./RESUME_BULLETS.md) only when the project impact or technology story changes.

