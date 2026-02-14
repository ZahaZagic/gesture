const LICENSE_KEY = "dev_ttnb7y8a586tnd6f1hh964y3qgl5o0cqhjewufyr";

// --- ONSCREEN DEBUGGER ---
(function () {
    const oldLog = console.log;
    const oldWarn = console.warn;
    const oldError = console.error;
    const debugDiv = document.getElementById("debug-overlay");

    function logToScreen(type, args) {
        if (!debugDiv) return;
        const msg = args.map(a => {
            if (typeof a === 'object') {
                try { return JSON.stringify(a); } catch (e) { return String(a); }
            }
            return String(a);
        }).join(" ");
        const color = type === 'error' ? 'red' : (type === 'warn' ? 'yellow' : 'lime');
        debugDiv.innerHTML += `<div style="color:${color}">[${type}] ${msg}</div>`;
        debugDiv.scrollTop = debugDiv.scrollHeight;
    }

    console.log = function (...args) { oldLog.apply(console, args); logToScreen('log', args); };
    console.warn = function (...args) { oldWarn.apply(console, args); logToScreen('warn', args); };
    console.error = function (...args) { oldError.apply(console, args); logToScreen('error', args); };

    window.onerror = function (msg, url, line) {
        logToScreen('error', [`Uncaught Error: ${msg} @ ${url}:${line}`]);
    };
})();

// --- Game Constants ---
const LANES = 8;
const ASSETS_DIR = "assets/";

// --- Global State ---
let canvas, ctx;
let gameRunning = false;
let gameOver = false;
let score = 0;
let startTime = 0;
let lastTime = 0;
let spawnTimer = 0;
let spawnInterval = 1000;

// Entities
let ship = null;
let asteroids = [];
let bgImage = null;

// Eye Tracking State
let gazeX = 0.5; // Normalized 0.0 - 1.0
let gazeY = 0.5;
let seeso = null; // The EasySeeSo instance
let isCalibrating = false;
let calibrationPoints = []; // Current calibration point
let calibUserStatus = "Initializing...";

// Images
const imgShip = new Image();
const imgAsteroid = new Image();
const imgBg = new Image();

// Assets Loading
let assetsLoaded = 0;
let domLoaded = false;
const totalAssets = 3;

function checkAssets() {
    assetsLoaded++;
    console.log(`Assets Loaded: ${assetsLoaded}/${totalAssets}`);
    tryStartGame();
}

function onAssetError(e) {
    console.warn("Asset failed to load", e);
    // Continue anyway to avoid blocking the game
    checkAssets();
}

function tryStartGame() {
    if (assetsLoaded === totalAssets && domLoaded && !gameRunning) {
        console.log("Assets and DOM ready. Starting Game.");
        initGameComponents();
        startGame();
    }
}

imgShip.onload = checkAssets;
imgShip.onerror = onAssetError;

imgAsteroid.onload = checkAssets;
imgAsteroid.onerror = onAssetError;

imgBg.onload = checkAssets;
imgBg.onerror = onAssetError;

// Force start after 3 seconds if assets hang
setTimeout(() => {
    if (!gameRunning) {
        console.warn("Force starting game due to asset timeout");
        // Ensure DOM is ready even if forced
        if (domLoaded) {
            initGameComponents();
            startGame();
        }
    }
}, 3000);

imgShip.src = ASSETS_DIR + "ship.png";
imgAsteroid.src = ASSETS_DIR + "asteroid.png";
imgBg.src = ASSETS_DIR + "bg_normal.jpg";

// --- Components ---
class Ship {
    constructor() {
        if (!canvas) return; // Safety
        this.width = canvas.width / LANES * 0.8;
        this.height = this.width; // Approximation
        this.y = canvas.height - 100;
        this.lane = 4;
    }

    update(gx) {
        // Map gazeX (0-1) to Lane (0-7)
        let g = Math.max(0, Math.min(1, gx));
        this.lane = Math.floor(g * LANES);
        if (this.lane >= LANES) this.lane = LANES - 1;

        let laneWidth = canvas.width / LANES;
        this.x = (this.lane * laneWidth) + (laneWidth / 2) - (this.width / 2);
    }

    draw() {
        ctx.drawImage(imgShip, this.x, this.y, this.width, this.height);
    }
}

class Asteroid {
    constructor() {
        if (!canvas) return;
        this.lane = Math.floor(Math.random() * LANES);
        let laneWidth = canvas.width / LANES;
        this.width = laneWidth * 0.7;
        this.height = this.width;
        this.x = (this.lane * laneWidth) + (laneWidth / 2) - (this.width / 2);
        this.y = -100;
        this.speed = 3 + Math.random() * 5;
    }

    update() {
        this.y += this.speed;
    }

    draw() {
        ctx.drawImage(imgAsteroid, this.x, this.y, this.width, this.height);
    }
}

function initGameComponents() {
    if (ship) return;
    ship = new Ship();
}

// --- Main Init ---
window.addEventListener('DOMContentLoaded', () => {
    canvas = document.getElementById("gameCanvas");
    ctx = canvas.getContext("2d");

    // Resize canvas
    canvas.width = 1280;
    canvas.height = 720;

    domLoaded = true;
    console.log("DOM Loaded and Canvas Initialized");
    tryStartGame();

    // UI Listeners
    document.getElementById("btn-calibrate").addEventListener("click", startCalibration);
    window.addEventListener("keydown", (e) => {
        if (e.key === 'c' || e.key === 'C') startCalibration();
        if (e.key === 'r' || e.key === 'R') if (gameOver) resetGame();
    });

    // Init SeeSo
    initSeeSo();
});

// --- SeeSo Integration ---
let trackerReady = false;

// --- SeeSo Integration ---
async function initSeeSo() {
    logDebug("Initializing Eye Tracker...");

    try {
        // Poll for SDK (max 5 seconds)
        for (let i = 0; i < 25; i++) {
            if (window.eyedid || window.seeso) break;
            logDebug("Waiting for EyeDid/SeeSo SDK... " + (i + 1));
            await new Promise(r => setTimeout(r, 200));
        }

        const sdk = window.eyedid || window.seeso;
        if (!sdk) throw new Error("SDK not loaded.");

        let tracker = null;
        logDebug("Instantiating SDK...");

        // Check for EasySeeSo first (High Level)
        if (sdk.EasySeeSo) {
            console.log("Found EasySeeSo class");
            tracker = new sdk.EasySeeSo();
        }
        // Check for GazeTracker (Low Level)
        else if (sdk.GazeTracker) {
            console.log("Found GazeTracker class");
            tracker = new sdk.GazeTracker(LICENSE_KEY);
        }
        else {
            throw new Error("Unknown SDK structure: " + JSON.stringify(Object.keys(sdk)));
        }

        window.seesoTracker = tracker;

        // 1. Get Camera Access - Just to ensure permission is granted
        logDebug("Click 'Allow' on Camera Prompt!");
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ video: true });
            logDebug("Camera Access Granted");
            // Release stream lock immediately so SDK can open it
            stream.getTracks().forEach(track => track.stop());
        } catch (err) {
            logDebug("Camera Blocked! Please Allow.");
            throw err;
        }

        // 2. Initialize
        logDebug("Calling tracker.initialize()...");

        if (tracker.initialize) {
            // Set callbacks BEFORE calling initialize
            tracker.onInitialized = (result, error) => {
                logDebug("onInitialized Callback: " + result);
                if (result) {
                    logDebug("Tracker Initialized!");
                    trackerReady = true;
                    if (tracker.startTracking) tracker.startTracking();
                } else {
                    logDebug("Init Failed");
                    console.error(error);
                }
            };

            tracker.onGaze = onGaze;
            tracker.onDebug = onDebug;

            // Timeout check
            setTimeout(() => {
                if (!trackerReady) logDebug("Warning: Init is taking a while...");
            }, 5000);

            // Call initialize with Key and Options
            // Based on similar SDKs, sometimes key is passed here even if in constructor
            tracker.initialize(LICENSE_KEY, {
                useWebAssembly: true,
                devMode: true
            });
        } else {
            logDebug("Error: tracker.initialize not found!");
            console.log(tracker);
        }

        document.getElementById("loading").style.display = "none";

    } catch (e) {
        console.error("SeeSo Init Error:", e);
        logDebug("Error: " + e.message);
    }
}

function startCalibration() {
    if (!window.seesoTracker) {
        logDebug("Tracker not created yet.");
        return;
    }
    if (!trackerReady) {
        logDebug("Tracker not ready (wait for Camera).");
        return;
    }
    isCalibrating = true;
    // ... rest of function
    document.getElementById("status").innerText = "Calibrating... Follow the Dot";

    // SeeSo Calibration API
    // 5 points is standard
    try {
        window.seesoTracker.startCalibration(onCalibrationNextPoint, onCalibrationProgress, onCalibrationFinished, 5);
    } catch (e) {
        console.error("Calibration Start Error:", e);
        isCalibrating = false;
    }
}

function logDebug(msg) {
    document.getElementById("status").innerText = msg;
    console.log(msg);
}

function onGaze(gazeInfo) {
    // gazeInfo: {x, y, trackingState, ...}
    // x, y are usually in pixels relative to screen/window

    // Map to Canvas Coordinates
    const rect = canvas.getBoundingClientRect();

    // Normalization logic depends on if x,y are screen or viewport
    // SeeSo usually returns viewport coordinates

    let rawX = gazeInfo.x;
    let rawY = gazeInfo.y;

    // Canvas-relative
    let cx = rawX - rect.left;
    let cy = rawY - rect.top;

    // Normalize 0-1 relative to canvas
    gazeX = cx / rect.width;
    gazeY = cy / rect.height;

    // Visual Feedback (Debug Dot)
    // We draw this in the game loop
}

function onDebug(FPS, latency_min, latency_max, latency_avg) {
    // Optional debug info
}

// --- Calibration Logic ---
function startCalibration() {
    if (!window.seesoTracker) return;
    isCalibrating = true;
    document.getElementById("status").innerText = "Calibrating... Follow the Dot";

    // SeeSo Calibration API
    // 5 points is standard
    try {
        window.seesoTracker.startCalibration(onCalibrationNextPoint, onCalibrationProgress, onCalibrationFinished, 5);
    } catch (e) {
        console.error("Calibration Start Error:", e);
        isCalibrating = false;
    }
}

function onCalibrationNextPoint(ptX, ptY) {
    // Next point to look at (px coordinates)
    // We need to map this to our canvas local coordinates to draw it if we want it inside canvas
    // Or just overlay a div. Drawing on canvas is easier for game context.

    const rect = canvas.getBoundingClientRect();
    // Convert screen/viewport px to canvas px
    // Assuming ptX/ptY are relative to viewport

    let cx = ptX - rect.left;
    let cy = ptY - rect.top;

    calibrationPoints = [{ x: cx, y: cy }];
}

function onCalibrationProgress(progress) {
    // progress 0.0 - 1.0 for current point
    // We can animate the dot shrink/grow
}

function onCalibrationFinished() {
    isCalibrating = false;
    calibrationPoints = [];
    document.getElementById("status").innerText = "Calibration Done!";
}

// --- Game Logic ---
function startGame() {
    gameRunning = true;
    initGameComponents(); // Ensure ship is created
    startTime = Date.now();
    lastTime = startTime;
    requestAnimationFrame(gameLoop);
}

function resetGame() {
    gameOver = false;
    score = 0;
    asteroids = [];
    startTime = Date.now();
    lastTime = startTime;
    document.getElementById("status").innerText = "Eye Tracker Active";
}

function gameLoop() {
    if (!gameRunning) return;

    let now = Date.now();
    let dt = now - lastTime;
    lastTime = now;

    // Clear
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Background
    if (imgBg.complete) ctx.drawImage(imgBg, 0, 0, canvas.width, canvas.height);

    if (isCalibrating) {
        // Draw Calibration UI
        ctx.fillStyle = "rgba(0,0,0,0.8)";
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        ctx.font = "40px Arial";
        ctx.fillStyle = "white";
        ctx.textAlign = "center";
        ctx.fillText("Focus on the Red Dot", canvas.width / 2, 100);

        // Draw Points
        if (calibrationPoints.length > 0) {
            let pt = calibrationPoints[0];
            ctx.beginPath();
            ctx.arc(pt.x, pt.y, 20, 0, Math.PI * 2);
            ctx.fillStyle = "red";
            ctx.fill();

            ctx.beginPath();
            ctx.arc(pt.x, pt.y, 10, 0, Math.PI * 2);
            ctx.fillStyle = "yellow";
            ctx.fill();
        }
    } else {
        // Game Play
        if (!gameOver) {
            score = Math.floor((Date.now() - startTime) / 100); // Score by time
            document.getElementById("score").innerText = "Score: " + score;

            // Spawn
            spawnTimer += dt;
            if (spawnTimer > spawnInterval) {
                asteroids.push(new Asteroid());
                spawnTimer = 0;
                if (spawnInterval > 200) spawnInterval -= 5;
            }

            // Update
            ship.update(gazeX);

            for (let i = asteroids.length - 1; i >= 0; i--) {
                let a = asteroids[i];
                a.update();

                // Collision
                if (
                    ship.x < a.x + a.width &&
                    ship.x + ship.width > a.x &&
                    ship.y < a.y + a.height &&
                    ship.y + ship.height > a.y
                ) {
                    gameOver = true;
                }

                if (a.y > canvas.height) {
                    asteroids.splice(i, 1);
                }
            }
        }

        // Draw
        ship.draw();
        asteroids.forEach(a => a.draw());

        // Gaze Indicator (Green Dot)
        let gxPx = gazeX * canvas.width;
        let gyPx = gazeY * canvas.height;
        ctx.beginPath();
        ctx.arc(gxPx, gyPx, 10, 0, Math.PI * 2);
        ctx.fillStyle = "lime";
        ctx.fill();

        // Lane Lines (Faint)
        ctx.strokeStyle = "rgba(255,255,255,0.1)";
        for (let i = 1; i < LANES; i++) {
            let lx = i * (canvas.width / LANES);
            ctx.beginPath();
            ctx.moveTo(lx, 0);
            ctx.lineTo(lx, canvas.height);
            ctx.stroke();
        }

        if (gameOver) {
            ctx.fillStyle = "rgba(0,0,0,0.7)";
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            ctx.font = "60px Arial";
            ctx.fillStyle = "red";
            ctx.textAlign = "center";
            ctx.fillText("GAME OVER", canvas.width / 2, canvas.height / 2);

            ctx.font = "30px Arial";
            ctx.fillStyle = "white";
            ctx.fillText("Press 'R' to Restart", canvas.width / 2, canvas.height / 2 + 60);
        }
    }

    requestAnimationFrame(gameLoop);
}
