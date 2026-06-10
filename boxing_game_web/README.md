# Boxing Game Web

Independent browser-first boxing game project designed for static hosting.

## Included now

- Hub / Fight Map / Training / Locker / Profile navigation
- `Q` keyboard back behavior
- Modern profile editor with slider-based height and weight controls
- In-browser head upload and crop flow for boxer and opponents
- Manage Opponents roster with add, edit, delete, and active selection
- Browser camera gameplay powered by MediaPipe Pose
- Live fight prompts with offense and defense move detection
- Live training drills for power, stamina, and agility
- `localStorage` save state for fighter data, stats, and match history

## Motion gameplay notes

The browser build uses rule-based landmark motion recognition in JavaScript, inspired by the standalone Python logic:

- Straights: forward extension detection
- Hooks: lateral swing detection
- Uppercuts: upward hand path detection
- Guard / Slip / Duck: head and hand posture detection

This gives you a real playable webcam version without needing a Python backend.

## Local run

From the project root:

```bash
python3 -m http.server 8000
```

Then open:

- `http://localhost:8000/`

Important:

- Use `http://` or `https://`, not `file://`
- Camera access requires browser permission
- MediaPipe CDN scripts require internet access the first time they load

## How to test

1. Open `Fight Map`
2. Click `Start Camera`
3. Stand back until your head, hands, and hips are visible
4. Click `Start Fight`
5. Follow the on-screen prompt with real body movement

For training:

1. Open `Training Gym`
2. Choose `Power`, `Stamina`, or `Agility`
3. Start camera
4. Click `Start <mode>`
5. Complete prompts for 30 seconds and check the stat increase

## Cloudflare Pages

- Framework preset: `None`
- Build command: none
- Output directory: `/`

## Project structure

- `index.html`: app shell and modal
- `styles.css`: game UI and responsive layout
- `app.js`: state, UI rendering, MediaPipe camera loop, motion detection, fight/training logic
- `assets/`: copied backgrounds and opponent art
