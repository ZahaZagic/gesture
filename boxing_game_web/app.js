const STORAGE_KEY = "gesture-boxing-web-v2";
const MAX_HP = 16;
const TRAINING_DURATION_MS = 30000;

const HUB_ITEMS = [
  {
    id: "fight",
    title: "Fight Map",
    kicker: "Career",
    copy: "Choose an arena, bring up the webcam, and fight with real body motion prompts in the browser.",
  },
  {
    id: "training",
    title: "Training Gym",
    kicker: "Stats",
    copy: "Run live power, stamina, and agility drills with MediaPipe pose tracking and instant scoring.",
  },
  {
    id: "profile",
    title: "Profile / Fighters",
    kicker: "Identity",
    copy: "Modern profile editing, head uploads, crop flow, and full opponent roster management.",
  },
  {
    id: "locker",
    title: "Locker Room",
    kicker: "History",
    copy: "Recent results, stat progression, sponsor count, and your active rival setup.",
  },
];

const ARENAS = [
  {
    id: "town",
    name: "Los Angeles",
    scene: "Southland Amateur Hall",
    entryFee: 0,
    upkeep: 20,
    basePrize: 100,
    enemyHpBonus: 0,
    speedScale: 1.0,
    unlockRule: "Start here",
    challenge: "Local pace with longer reaction windows and simple reads.",
  },
  {
    id: "city",
    name: "Las Vegas",
    scene: "Desert Fight Club",
    entryFee: 80,
    upkeep: 35,
    basePrize: 260,
    enemyHpBonus: 4,
    speedScale: 0.92,
    unlockRule: "5 wins and 0 losses",
    challenge: "Sharper rhythm and quicker exchanges built for pressure testing.",
  },
  {
    id: "state",
    name: "London",
    scene: "West End Fight Night",
    entryFee: 160,
    upkeep: 60,
    basePrize: 520,
    enemyHpBonus: 8,
    speedScale: 0.86,
    unlockRule: "Career points above 500",
    challenge: "Technical pressure and punishment for sloppy counters.",
  },
  {
    id: "national",
    name: "Riyadh",
    scene: "Global Season Ring",
    entryFee: 320,
    upkeep: 95,
    basePrize: 1100,
    enemyHpBonus: 12,
    speedScale: 0.78,
    unlockRule: "Win the State belt",
    challenge: "Broadcast-speed opponent who attacks in volume.",
  },
  {
    id: "worldwide",
    name: "Chongqing",
    scene: "Mountain Megafight",
    entryFee: 650,
    upkeep: 140,
    basePrize: 2200,
    enemyHpBonus: 18,
    speedScale: 0.68,
    unlockRule: "Reach World Top 10",
    challenge: "Elite pace where combinations and reads matter every second.",
  },
];

const TRAINING = [
  {
    id: "power",
    title: "Power",
    copy: "Combo-focused work for heavier shots and better finish pressure.",
    baseCost: 60,
    moves: ["left_straight", "right_straight", "left_hook", "right_hook", "left_uppercut", "right_uppercut"],
  },
  {
    id: "stamina",
    title: "Stamina",
    copy: "Volume rounds that build late-fight durability and consistency.",
    baseCost: 70,
    moves: ["left_straight", "right_straight", "left_hook", "right_hook"],
  },
  {
    id: "agility",
    title: "Agility",
    copy: "Reaction drills for faster movement and tighter defense timing.",
    baseCost: 65,
    moves: ["guard", "slip_left", "slip_right", "duck"],
  },
];

const MOVES = {
  left_straight: { id: "left_straight", label: "LEFT STRAIGHT", type: "offense", hand: "left", hint: "Punch your left hand straight forward." },
  right_straight: { id: "right_straight", label: "RIGHT STRAIGHT", type: "offense", hand: "right", hint: "Punch your right hand straight forward." },
  left_hook: { id: "left_hook", label: "LEFT HOOK", type: "offense", hand: "left", hint: "Swing your left fist across." },
  right_hook: { id: "right_hook", label: "RIGHT HOOK", type: "offense", hand: "right", hint: "Swing your right fist across." },
  left_uppercut: { id: "left_uppercut", label: "LEFT UPPERCUT", type: "offense", hand: "left", hint: "Drive your left fist upward." },
  right_uppercut: { id: "right_uppercut", label: "RIGHT UPPERCUT", type: "offense", hand: "right", hint: "Drive your right fist upward." },
  guard: { id: "guard", label: "DOUBLE GUARD", type: "defense", hint: "Bring both hands high in front of your head." },
  slip_left: { id: "slip_left", label: "SLIP LEFT", type: "defense", hint: "Lean your head and torso left." },
  slip_right: { id: "slip_right", label: "SLIP RIGHT", type: "defense", hint: "Lean your head and torso right." },
  duck: { id: "duck", label: "DUCK", type: "defense", hint: "Squat down to dodge a hook." },
};

const OFFENSE_MOVE_IDS = Object.values(MOVES)
  .filter((move) => move.type === "offense")
  .map((move) => move.id);
const DEFENSE_MOVE_IDS = Object.values(MOVES)
  .filter((move) => move.type === "defense")
  .map((move) => move.id);

const DEFAULT_OPPONENTS = [
  {
    id: "milo_vega",
    name: "Milo Vega",
    title: "Garage Prospect",
    record: "6-1",
    heightFeet: 5,
    heightInches: 10,
    weight: 154,
    photo: "",
    rating: 18,
    minArenaRank: 0,
    maxArenaRank: 1,
    enabled: true,
    isBuiltin: true,
  },
  {
    id: "nyx_striker",
    name: "Nyx Striker",
    title: "Neon Runner",
    record: "12-2",
    heightFeet: 5,
    heightInches: 11,
    weight: 160,
    photo: "",
    rating: 34,
    minArenaRank: 1,
    maxArenaRank: 3,
    enabled: true,
    isBuiltin: true,
  },
  {
    id: "dante_crest",
    name: "Dante Crest",
    title: "State Technician",
    record: "19-4",
    heightFeet: 6,
    heightInches: 0,
    weight: 168,
    photo: "",
    rating: 48,
    minArenaRank: 2,
    maxArenaRank: 4,
    enabled: true,
    isBuiltin: true,
  },
  {
    id: "marcus_hale",
    name: "Marcus Hale",
    title: "Broadcast Champion",
    record: "26-3",
    heightFeet: 6,
    heightInches: 1,
    weight: 172,
    photo: "",
    rating: 62,
    minArenaRank: 3,
    maxArenaRank: 4,
    enabled: true,
    isBuiltin: true,
  },
  {
    id: "orion_voss",
    name: "Orion Voss",
    title: "World Summit",
    record: "34-2",
    heightFeet: 6,
    heightInches: 2,
    weight: 178,
    photo: "",
    rating: 76,
    minArenaRank: 4,
    maxArenaRank: 4,
    enabled: true,
    isBuiltin: true,
  },
];

const DEFAULT_STATE = {
  screen: "hub",
  previousScreens: [],
  selectedArenaId: "town",
  profileTab: "boxer",
  selectedOpponentId: "milo_vega",
  selectedTrainingId: "power",
  arenaAssignments: {},
  career: {
    playerName: "Zaha",
    cash: 500,
    points: 0,
    wins: 0,
    losses: 0,
    stats: {
      power: 21.4,
      stamina: 16.8,
      agility: 14.9,
    },
    matchHistory: [],
    sponsorCount: 0,
    stateBeltWon: false,
  },
  fighterProfile: {
    heightFeet: 5,
    heightInches: 10,
    weight: 165,
    photo: "",
  },
  opponents: DEFAULT_OPPONENTS,
};

const state = loadState();

const runtime = {
  pose: null,
  videoEl: null,
  canvasEl: null,
  canvasCtx: null,
  stream: null,
  cameraActive: false,
  processing: false,
  lastResults: null,
  lastPoseData: null,
  wristHistory: { left: [], right: [] },
  headYHistory: [],
  activeSession: null,
  statusText: "Camera is offline. Start camera to begin.",
  lastMoveFeedback: "",
  sessionMetrics: {},
};

const root = document.getElementById("screenRoot");
const cropModal = document.getElementById("cropModal");
const cropCanvas = document.getElementById("cropCanvas");
const cropTitle = document.getElementById("cropTitle");
const photoInput = document.getElementById("photoInput");
const cropZoom = document.getElementById("cropZoom");
const cropOffsetX = document.getElementById("cropOffsetX");
const cropOffsetY = document.getElementById("cropOffsetY");
const saveCropButton = document.getElementById("saveCropButton");

const cropState = {
  target: null,
  image: null,
};

document.addEventListener("keydown", (event) => {
  const tag = document.activeElement?.tagName?.toLowerCase();
  if (event.key.toLowerCase() === "q" && !["input", "textarea", "select"].includes(tag)) {
    event.preventDefault();
    goBack();
  }
});

[cropZoom, cropOffsetX, cropOffsetY].forEach((input) => input.addEventListener("input", renderCropPreview));

photoInput.addEventListener("change", async (event) => {
  const file = event.target.files?.[0];
  if (!file) {
    return;
  }
  cropState.image = await fileToImage(file);
  renderCropPreview();
});

saveCropButton.addEventListener("click", () => {
  if (!cropState.target || !cropState.image) {
    return;
  }
  const dataUrl = exportCropDataUrl();
  if (cropState.target.type === "player") {
    state.fighterProfile.photo = dataUrl;
  } else {
    const opponent = findOpponent(cropState.target.id);
    if (opponent) {
      opponent.photo = dataUrl;
    }
  }
  saveState();
  cropModal.close();
  render();
});

cropModal.addEventListener("close", () => {
  cropState.target = null;
  cropState.image = null;
  photoInput.value = "";
});

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return structuredClone(DEFAULT_STATE);
    }
    return mergeState(DEFAULT_STATE, JSON.parse(raw));
  } catch {
    return structuredClone(DEFAULT_STATE);
  }
}

function mergeState(base, incoming) {
  const merged = {
    ...structuredClone(base),
    ...incoming,
    career: {
      ...structuredClone(base.career),
      ...(incoming?.career || {}),
      stats: {
        ...structuredClone(base.career.stats),
        ...(incoming?.career?.stats || {}),
      },
      matchHistory: Array.isArray(incoming?.career?.matchHistory) ? incoming.career.matchHistory : [],
    },
    fighterProfile: {
      ...structuredClone(base.fighterProfile),
      ...(incoming?.fighterProfile || {}),
    },
    opponents: Array.isArray(incoming?.opponents) && incoming.opponents.length ? incoming.opponents : structuredClone(base.opponents),
  };
  merged.opponents = normalizeRoster(merged.opponents);
  merged.arenaAssignments = normalizeArenaAssignments(merged.arenaAssignments || {}, merged.opponents);
  return merged;
}

function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function arenaRank(arenaId = selectedArena().id) {
  return ARENAS.findIndex((arena) => arena.id === arenaId);
}

function worldRank() {
  const pressure = state.career.points + state.career.wins * 85 - state.career.losses * 40;
  return Math.max(1, 120 - Math.floor(pressure / 40));
}

function isArenaUnlocked(arenaId) {
  if (arenaId === "town") return true;
  if (arenaId === "city") return state.career.wins >= 5 && state.career.losses === 0;
  if (arenaId === "state") return state.career.points > 500;
  if (arenaId === "national") return state.career.stateBeltWon;
  if (arenaId === "worldwide") return state.career.stateBeltWon && worldRank() <= 10;
  return false;
}

function selectedArena() {
  return ARENAS.find((arena) => arena.id === state.selectedArenaId) || ARENAS[0];
}

function selectedTraining() {
  return TRAINING.find((item) => item.id === state.selectedTrainingId) || TRAINING[0];
}

function selectedOpponent() {
  return findOpponent(state.selectedOpponentId) || state.opponents[0] || null;
}

function currentArenaOpponent(arenaId = selectedArena().id) {
  const assignedId = state.arenaAssignments?.[arenaId];
  const assigned = assignedId ? findOpponent(assignedId) : null;
  if (assigned) {
    return assigned;
  }
  refreshArenaAssignments();
  return findOpponent(state.arenaAssignments?.[arenaId]) || state.opponents[0] || null;
}

function findOpponent(id) {
  return state.opponents.find((opponent) => opponent.id === id) || null;
}

function goTo(screen) {
  if (runtime.activeSession?.running && state.screen !== screen) {
    stopSession("Session stopped while leaving the ring.");
  }
  if (state.screen !== screen) {
    state.previousScreens.push(state.screen);
  }
  state.screen = screen;
  if (screen === "fight") {
    refreshArenaAssignments();
  }
  saveState();
  render();
}

function goBack() {
  if (cropModal.open) {
    cropModal.close();
    return;
  }
  if (runtime.activeSession?.running) {
    stopSession("Session stopped.");
    updateRuntimePanel();
    return;
  }
  if (state.screen === "hub") {
    return;
  }
  state.screen = state.previousScreens.pop() || "hub";
  saveState();
  render();
}

function formatHeight(feet, inches) {
  return `${feet}'${inches}"`;
}

function trainingCost(trainingId) {
  const item = TRAINING.find((entry) => entry.id === trainingId) || TRAINING[0];
  const value = state.career.stats[trainingId];
  return Math.round(item.baseCost + value * 3);
}

function sceneBackground(screen = state.screen) {
  if (screen === "fight") {
    return arenaBackground(selectedArena().id);
  }
  if (screen === "training") {
    return arenaBackground("city");
  }
  if (screen === "profile") {
    return arenaBackground("national");
  }
  if (screen === "locker") {
    return arenaBackground("state");
  }
  return arenaBackground("town");
}

function renderScene(title, subtitle, content, options = {}) {
  const actions = options.actions || "";
  return `
    <section class="scene" style="background-image: linear-gradient(180deg, rgba(5, 9, 16, 0.24), rgba(5, 9, 16, 0.66)), url('${sceneBackground(options.screen)}')">
      <div class="scene-overlay">
        <div class="screen-inner">
          <div class="scene-topbar">
            <div>
              <p class="eyebrow">${options.eyebrow || "Gesture Boxing"}</p>
              <h1 class="page-title">${title}</h1>
              ${subtitle ? `<p class="subcopy">${subtitle}</p>` : ""}
            </div>
            <div class="scene-actions">
              ${actions}
            </div>
          </div>
          ${content}
        </div>
      </div>
    </section>
  `;
}

function render() {
  if (!["fight", "training"].includes(state.screen) && runtime.cameraActive) {
    stopCamera();
  }
  root.innerHTML = screenTemplate();
  bindGlobalInputs();
  mountGameDom();
  updateRuntimePanel();
}

function screenTemplate() {
  if (state.screen === "fight") return renderFightScreen();
  if (state.screen === "training") return renderTrainingScreen();
  if (state.screen === "profile") return renderProfileScreen();
  if (state.screen === "locker") return renderLockerScreen();
  return renderHubScreen();
}

function renderHubScreen() {
  const content = `
    <div class="hub-grid">
      ${HUB_ITEMS.map(
        (item, index) => `
          <button class="menu-card ${index === 0 ? "selected" : ""}" data-go="${item.id}">
            <div class="menu-label">${item.title.toUpperCase()}</div>
          </button>
        `,
      ).join("")}
    </div>
    <div class="hub-footer">
      <strong>FIGHTER: ${escapeHtml(state.career.playerName).toUpperCase()}</strong>
      <div>Cash $${state.career.cash}   Points ${state.career.points}   W-L ${state.career.wins}-${state.career.losses}   Rank #${worldRank()}</div>
    </div>
  `;
  return renderScene("CAREER MAP", "Choose your next stop in the boxing career.", content, {
    screen: "hub",
    eyebrow: "Gesture Boxing",
    actions: `
      <button class="tech-button red" data-ui="reset-save">Reset Save</button>
    `,
  });
}

function renderFightScreen() {
  const current = selectedArena();
  const opponent = currentArenaOpponent(current.id);
  const content = `
    <div class="arena-layout">
      <div class="panel-frame gold">
        <p class="eyebrow">Arena Ladder</p>
        <div class="node-row">
          ${ARENAS.map((arena) => {
            const active = arena.id === state.selectedArenaId;
            const unlocked = isArenaUnlocked(arena.id);
            return `
              <button class="panel-card ${active ? "selected" : ""}" data-arena="${arena.id}">
                <div class="card-title">${arena.name.toUpperCase()}</div>
                <div class="muted">${arena.scene}</div>
                <div class="muted">${unlocked ? "READY" : arena.unlockRule}</div>
              </button>
            `;
          }).join("")}
        </div>
        <div class="hub-footer">
          <strong>${current.name.toUpperCase()} | ${current.scene.toUpperCase()}</strong>
          <div>${current.challenge}</div>
        </div>
      </div>
      <div class="panel-frame">
        <p class="eyebrow">Opponent</p>
        <div class="opponent-preview">
          <div class="avatar-ring small">${avatarMarkup(opponentAvatar(opponent), opponent?.name || "Opponent")}</div>
          <div>
            <div class="card-title">${escapeHtml(opponent?.name || "RIVAL").toUpperCase()}</div>
            <div class="muted">${opponent ? `${opponent.title}   ${formatHeight(opponent.heightFeet, opponent.heightInches)}   ${opponent.weight} lb   ${opponent.record}` : "Add an opponent in Profile first."}</div>
          </div>
        </div>
        <div class="hud-strip">
          <div class="hud-box"><span>Entry</span><strong class="hud-value">$${current.entryFee}</strong></div>
          <div class="hud-box"><span>Upkeep</span><strong class="hud-value">$${current.upkeep}</strong></div>
          <div class="hud-box"><span>Prize</span><strong class="hud-value">$${current.basePrize}</strong></div>
        </div>
      </div>
    </div>
    <div class="panel-frame" style="margin-top: 20px;">
      ${renderCameraStage("fight")}
    </div>
  `;
  return renderScene("FIGHT MAP", "Move through the ladder one arena at a time.", content, {
    screen: "fight",
    actions: `
      <button class="tech-button green" data-camera="toggle">${runtime.cameraActive ? "Stop Camera" : "Start Camera"}</button>
      <button class="tech-button gold" data-action="start-fight">Enter Fight</button>
      <button class="tech-button red" data-ui="go-back">Back</button>
    `,
  });
}

function renderTrainingScreen() {
  const selected = selectedTraining();
  const content = `
    <div class="training-layout">
      <div class="panel-frame gold">
        <p class="eyebrow">Programs</p>
        <div class="training-grid">
          ${TRAINING.map((item) => `
            <button class="training-card ${state.selectedTrainingId === item.id ? "selected" : ""}" data-training="${item.id}">
              <div class="card-title">${item.title.toUpperCase()}</div>
              <div class="muted">Value ${state.career.stats[item.id].toFixed(1)}</div>
              <div class="muted">Cost $${trainingCost(item.id)}</div>
            </button>
          `).join("")}
        </div>
      </div>
      <div class="panel-frame">
        <p class="eyebrow">Program Notes</p>
        <div class="card-title">${selected.title.toUpperCase()}</div>
        <p class="panel-subcopy">${selected.copy}</p>
        <div class="record-list">
          <div class="record-item"><strong>Tracked Moves</strong><br /><span class="muted">${selected.moves.map((id) => MOVES[id].label).join(" · ")}</span></div>
          <div class="record-item"><strong>Gain Rule</strong><br /><span class="muted">Average quality becomes your stat gain, clamped between 0.25 and 2.4.</span></div>
        </div>
      </div>
    </div>
    <div class="panel-frame" style="margin-top: 20px;">
      ${renderCameraStage("training")}
    </div>
  `;
  return renderScene("TRAINING GYM", "Pick a drill and move cleanly on camera.", content, {
    screen: "training",
    actions: `
      <button class="tech-button green" data-camera="toggle">${runtime.cameraActive ? "Stop Camera" : "Start Camera"}</button>
      <button class="tech-button gold" data-action="start-training">Start ${selected.title}</button>
      <button class="tech-button red" data-ui="go-back">Back</button>
    `,
  });
}

function renderCameraStage(mode) {
  return `
    <div class="camera-shell">
      <div class="camera-stage">
        <video id="poseVideo" playsinline muted></video>
        <canvas id="poseCanvas" width="960" height="540"></canvas>
        <div class="camera-overlay">
          <span class="badge ${runtime.cameraActive ? "online" : "offline"}">${runtime.cameraActive ? "Camera Live" : "Camera Idle"}</span>
          <div class="camera-message" id="cameraStatus">${escapeHtml(runtime.statusText)}</div>
        </div>
      </div>
      <div class="camera-hud">
        <div class="camera-hud-row">
          <span class="eyebrow">Prompt</span>
          <strong id="promptLabel">No session running</strong>
        </div>
        <div class="camera-hud-row">
          <span class="eyebrow">Feedback</span>
          <strong id="feedbackLabel">${escapeHtml(runtime.lastMoveFeedback || "Stand centered so the camera sees your head, both hands, and hips.")}</strong>
        </div>
        <div class="session-stats" id="sessionStats">${renderSessionStats(mode)}</div>
      </div>
    </div>
  `;
}

function renderSessionStats(mode) {
  if (mode === "fight") {
    return `
      <div class="stat-card"><span class="eyebrow">Player HP</span><strong>${runtime.activeSession?.playerHp ?? "-"}</strong></div>
      <div class="stat-card"><span class="eyebrow">Enemy HP</span><strong>${runtime.activeSession?.enemyHp ?? "-"}</strong></div>
      <div class="stat-card"><span class="eyebrow">Combo</span><strong>${runtime.activeSession?.combo ?? 0}</strong></div>
    `;
  }
  return `
    <div class="stat-card"><span class="eyebrow">Time</span><strong>${runtime.activeSession?.remainingSeconds ?? "-"}</strong></div>
    <div class="stat-card"><span class="eyebrow">Hits</span><strong>${runtime.activeSession?.hits ?? 0}</strong></div>
    <div class="stat-card"><span class="eyebrow">Misses</span><strong>${runtime.activeSession?.misses ?? 0}</strong></div>
  `;
}

function renderProfileScreen() {
  const opponent = selectedOpponent();
  const content =
    state.profileTab === "boxer"
      ? `
        <div class="profile-tabs" style="margin-bottom: 16px;">
          <button class="${state.profileTab === "boxer" ? "active" : ""}" data-tab="boxer">My Boxer</button>
          <button class="${state.profileTab === "opponents" ? "active" : ""}" data-tab="opponents">Opponents</button>
        </div>
        <div class="panel-frame gold">
          <div class="profile-layout">
            <div class="avatar-stage">
              <div class="avatar-ring">${avatarMarkup(state.fighterProfile.photo, "Your boxer portrait")}</div>
              <button class="tech-button cyan" data-upload="player">Upload Head</button>
            </div>
            <div class="form-grid">
              <label class="field">
                <span>Fighter Name</span>
                <input id="playerName" type="text" maxlength="18" value="${escapeHtml(state.career.playerName)}" />
              </label>
              <div class="split">
                <label class="slider-field">
                  <span>Height</span>
                  <div class="field-value">${formatHeight(state.fighterProfile.heightFeet, state.fighterProfile.heightInches)}</div>
                  <input id="playerHeightFeet" type="range" min="4" max="7" step="1" value="${state.fighterProfile.heightFeet}" />
                  <input id="playerHeightInches" type="range" min="0" max="11" step="1" value="${state.fighterProfile.heightInches}" />
                </label>
                <label class="slider-field">
                  <span>Weight</span>
                  <div class="field-value">${state.fighterProfile.weight} lb</div>
                  <input id="playerWeight" type="range" min="110" max="260" step="1" value="${state.fighterProfile.weight}" />
                </label>
              </div>
              <div class="hud-strip">
                <div class="hud-box"><span>Power</span><strong class="hud-value">${state.career.stats.power.toFixed(1)}</strong></div>
                <div class="hud-box"><span>Stamina</span><strong class="hud-value">${state.career.stats.stamina.toFixed(1)}</strong></div>
                <div class="hud-box"><span>Agility</span><strong class="hud-value">${state.career.stats.agility.toFixed(1)}</strong></div>
              </div>
            </div>
          </div>
        </div>
      `
      : `
        <div class="profile-tabs" style="margin-bottom: 16px;">
          <button class="${state.profileTab === "boxer" ? "active" : ""}" data-tab="boxer">My Boxer</button>
          <button class="${state.profileTab === "opponents" ? "active" : ""}" data-tab="opponents">Opponents</button>
        </div>
        <div class="panel-frame magenta">
          <div class="profile-layout">
            <div class="list-stack">
              <div class="inline-actions">
                <button class="tech-button gold" data-action="add-opponent">Add Opponent</button>
              </div>
              ${state.opponents.map(
                (item) => `
                  <button class="list-card ${item.id === state.selectedOpponentId ? "selected" : ""}" data-opponent="${item.id}">
                    <div class="card-title">${escapeHtml(item.name).toUpperCase()}</div>
                    <div class="muted">${item.id === state.selectedOpponentId ? "ACTIVE" : item.title}</div>
                  </button>
                `,
              ).join("")}
            </div>
            ${
              opponent
                ? `
                  <div class="form-grid">
                    <div class="avatar-stage">
                      <div class="avatar-ring">${avatarMarkup(opponentAvatar(opponent), `${opponent.name} portrait`)}</div>
                      <div class="inline-actions">
                        <button class="tech-button magenta" data-upload="opponent">Upload Head</button>
                        <button class="tech-button cyan" data-action="toggle-roster-opponent">${opponent.enabled === false ? "Add To Roster" : "In Rotation"}</button>
                        <button class="tech-button red" data-action="delete-opponent">Delete</button>
                      </div>
                    </div>
                    <label class="field">
                      <span>Name</span>
                      <input id="opponentName" type="text" maxlength="20" value="${escapeHtml(opponent.name)}" />
                    </label>
                    <label class="field">
                      <span>Title</span>
                      <input id="opponentTitle" type="text" maxlength="24" value="${escapeHtml(opponent.title)}" />
                    </label>
                    <label class="field">
                      <span>Record</span>
                      <input id="opponentRecord" type="text" maxlength="12" value="${escapeHtml(opponent.record)}" />
                    </label>
                    <div class="hud-strip">
                      <div class="hud-box"><span>Rating</span><strong class="hud-value">${opponent.rating ?? 20}</strong></div>
                      <div class="hud-box"><span>Arena From</span><strong class="hud-value">${(opponent.minArenaRank ?? 0) + 1}</strong></div>
                      <div class="hud-box"><span>Status</span><strong class="hud-value">${opponent.enabled === false ? "OUT" : "LIVE"}</strong></div>
                    </div>
                    <div class="split">
                      <label class="slider-field">
                        <span>Height</span>
                        <div class="field-value">${formatHeight(opponent.heightFeet, opponent.heightInches)}</div>
                        <input id="opponentHeightFeet" type="range" min="4" max="7" step="1" value="${opponent.heightFeet}" />
                        <input id="opponentHeightInches" type="range" min="0" max="11" step="1" value="${opponent.heightInches}" />
                      </label>
                      <label class="slider-field">
                        <span>Weight</span>
                        <div class="field-value">${opponent.weight} lb</div>
                        <input id="opponentWeight" type="range" min="110" max="280" step="1" value="${opponent.weight}" />
                      </label>
                    </div>
                  </div>
                `
                : `<div class="muted">Add an opponent to start managing the roster.</div>`
            }
          </div>
        </div>
      `;
  return renderScene("PROFILE / FIGHTERS", "Upload photos, crop the head, and choose who appears across the ring.", content, {
    screen: "profile",
    actions: `
      <button class="tech-button red" data-ui="go-back">Back</button>
    `,
  });
}

function renderLockerScreen() {
  const opponent = currentArenaOpponent();
  const content = `
    <div class="locker-layout">
      <div class="panel-frame gold">
        <p class="eyebrow">Snapshot</p>
        <div class="hud-strip">
          <div class="hud-box"><span>Power</span><strong class="hud-value">${state.career.stats.power.toFixed(1)}</strong></div>
          <div class="hud-box"><span>Stamina</span><strong class="hud-value">${state.career.stats.stamina.toFixed(1)}</strong></div>
          <div class="hud-box"><span>Agility</span><strong class="hud-value">${state.career.stats.agility.toFixed(1)}</strong></div>
        </div>
        <div class="opponent-preview">
          <div class="avatar-ring small">${avatarMarkup(opponentAvatar(opponent), opponent?.name || "Opponent")}</div>
          <div>
            <div class="card-title">ACTIVE RIVAL</div>
            <div class="muted">${opponent ? `${opponent.name} · ${opponent.title}` : "No active rival selected yet."}</div>
          </div>
        </div>
      </div>
      <div class="panel-frame">
        <p class="eyebrow">Recent Results</p>
        <div class="record-list">
          ${
            state.career.matchHistory.length
              ? state.career.matchHistory
                  .slice(0, 8)
                  .map(
                    (item) => `
                      <div class="record-item">
                        <strong>${item.result}</strong> ${item.arena} vs ${escapeHtml(item.opponent)}<br />
                        <span class="muted">${escapeHtml(item.detail)} · Payout $${item.payout} · Combo ${item.combo}</span>
                      </div>
                    `,
                  )
                  .join("")
              : '<div class="record-item"><span class="muted">No results yet. Start a live webcam fight from the Fight Map.</span></div>'
          }
        </div>
      </div>
    </div>
  `;
  return renderScene("LOCKER ROOM", "Review your career snapshot and recent fights.", content, {
    screen: "locker",
    actions: `
      <button class="tech-button red" data-ui="go-back">Back</button>
    `,
  });
}

function bindGlobalInputs() {
  root.querySelectorAll("[data-ui]").forEach((button) =>
    button.addEventListener("click", () => {
      if (button.dataset.ui === "go-back") {
        goBack();
        return;
      }
      if (button.dataset.ui === "reset-save") {
        localStorage.removeItem(STORAGE_KEY);
        Object.assign(state, structuredClone(DEFAULT_STATE));
        stopSession();
        stopCamera();
        saveState();
        render();
      }
    }),
  );
  root.querySelectorAll("[data-go]").forEach((button) => button.addEventListener("click", () => goTo(button.dataset.go)));
  root.querySelectorAll("[data-tab]").forEach((button) =>
    button.addEventListener("click", () => {
      state.profileTab = button.dataset.tab;
      saveState();
      render();
    }),
  );
  root.querySelectorAll("[data-arena]").forEach((button) =>
    button.addEventListener("click", () => {
      state.selectedArenaId = button.dataset.arena;
      saveState();
      render();
    }),
  );
  root.querySelectorAll("[data-training]").forEach((button) =>
    button.addEventListener("click", () => {
      state.selectedTrainingId = button.dataset.training;
      saveState();
      render();
    }),
  );
  root.querySelectorAll("[data-opponent]").forEach((button) =>
    button.addEventListener("click", () => {
      state.selectedOpponentId = button.dataset.opponent;
      saveState();
      render();
    }),
  );
  root.querySelectorAll("[data-upload]").forEach((button) =>
    button.addEventListener("click", () => {
      if (button.dataset.upload === "player") {
        openCropModal({ type: "player" });
      } else if (state.selectedOpponentId) {
        openCropModal({ type: "opponent", id: state.selectedOpponentId });
      }
    }),
  );
  root.querySelectorAll("[data-action]").forEach((button) =>
    button.addEventListener("click", () => handleAction(button.dataset.action)),
  );
  root.querySelectorAll("[data-camera]").forEach((button) =>
    button.addEventListener("click", () => {
      if (runtime.cameraActive) {
        stopCamera();
        updateRuntimePanel();
        render();
      } else {
        startCamera();
      }
    }),
  );

  bindInput("playerName", (value) => (state.career.playerName = value));
  bindSlider("playerHeightFeet", (value) => (state.fighterProfile.heightFeet = Number(value)));
  bindSlider("playerHeightInches", (value) => (state.fighterProfile.heightInches = Number(value)));
  bindSlider("playerWeight", (value) => (state.fighterProfile.weight = Number(value)));

  const opponent = selectedOpponent();
  if (opponent) {
    bindInput("opponentName", (value) => (opponent.name = value));
    bindInput("opponentTitle", (value) => (opponent.title = value));
    bindInput("opponentRecord", (value) => (opponent.record = value));
    bindSlider("opponentHeightFeet", (value) => (opponent.heightFeet = Number(value)));
    bindSlider("opponentHeightInches", (value) => (opponent.heightInches = Number(value)));
    bindSlider("opponentWeight", (value) => (opponent.weight = Number(value)));
  }
}

function bindInput(id, setter) {
  const el = document.getElementById(id);
  if (!el) return;
  el.addEventListener("input", (event) => {
    setter(event.target.value);
    saveState();
    render();
  });
}

function bindSlider(id, setter) {
  const el = document.getElementById(id);
  if (!el) return;
  el.addEventListener("input", (event) => {
    setter(event.target.value);
    saveState();
    render();
  });
}

function handleAction(action) {
  if (action === "add-opponent") {
    const id = `opponent_${Math.random().toString(36).slice(2, 10)}`;
    state.opponents.unshift({
      id,
      name: `Opponent ${state.opponents.length + 1}`,
      title: "Personal Rival",
      record: "0-0",
      heightFeet: 5,
      heightInches: 10,
      weight: 165,
      photo: "",
      rating: 20,
      minArenaRank: 0,
      maxArenaRank: 1,
      enabled: true,
      isBuiltin: false,
    });
    state.selectedOpponentId = id;
    state.profileTab = "opponents";
    refreshArenaAssignments();
    saveState();
    render();
    return;
  }
  if (action === "delete-opponent") {
    state.opponents = state.opponents.filter((item) => item.id !== state.selectedOpponentId);
    state.selectedOpponentId = state.opponents[0]?.id || "";
    refreshArenaAssignments();
    saveState();
    render();
    return;
  }
  if (action === "toggle-roster-opponent") {
    const opponent = selectedOpponent();
    if (opponent) {
      opponent.enabled = opponent.enabled === false;
      refreshArenaAssignments();
      saveState();
      render();
    }
    return;
  }
  if (action === "set-active-opponent") {
    saveState();
    render();
    return;
  }
  if (action === "start-fight") {
    beginFightSession();
    return;
  }
  if (action === "start-training") {
    beginTrainingSession();
    return;
  }
}

function mountGameDom() {
  runtime.videoEl = document.getElementById("poseVideo");
  runtime.canvasEl = document.getElementById("poseCanvas");
  runtime.canvasCtx = runtime.canvasEl ? runtime.canvasEl.getContext("2d") : null;
  if (runtime.videoEl && runtime.stream) {
    runtime.videoEl.srcObject = runtime.stream;
    runtime.videoEl.play().catch(() => {});
  }
}

function updateRuntimePanel() {
  const status = document.getElementById("cameraStatus");
  const prompt = document.getElementById("promptLabel");
  const feedback = document.getElementById("feedbackLabel");
  const stats = document.getElementById("sessionStats");
  if (status) status.textContent = runtime.statusText;
  if (prompt) {
    if (!runtime.activeSession?.running) {
      prompt.textContent = "No session running";
    } else {
      const promptLabel = runtime.activeSession.prompt ? MOVES[runtime.activeSession.prompt.expectedMoveId].label : "Get ready";
      prompt.textContent = `${runtime.activeSession.mode.toUpperCase()} · ${promptLabel}`;
    }
  }
  if (feedback) {
    feedback.textContent = runtime.lastMoveFeedback || "Stand centered so the camera sees your head, both hands, and hips.";
  }
  if (stats) {
    stats.innerHTML = renderSessionStats(state.screen === "training" ? "training" : "fight");
  }
}

async function startCamera() {
  if (runtime.cameraActive) {
    return;
  }
  if (typeof Pose === "undefined") {
    runtime.statusText = "MediaPipe did not load. Check your network connection and reload.";
    updateRuntimePanel();
    return;
  }
  mountGameDom();
  if (!runtime.videoEl || !runtime.canvasEl) {
    runtime.statusText = "Open Fight Map or Training first to mount the camera stage.";
    updateRuntimePanel();
    return;
  }
  try {
    runtime.stream = await navigator.mediaDevices.getUserMedia({
      video: { width: 960, height: 540, facingMode: "user" },
      audio: false,
    });
    runtime.videoEl.srcObject = runtime.stream;
    await runtime.videoEl.play();

    runtime.pose = new Pose({
      locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`,
    });
    runtime.pose.setOptions({
      modelComplexity: 1,
      smoothLandmarks: true,
      enableSegmentation: false,
      minDetectionConfidence: 0.5,
      minTrackingConfidence: 0.5,
    });
    runtime.pose.onResults(handlePoseResults);
    runtime.cameraActive = true;
    runtime.statusText = "Camera live. Stand back until head, hands, and hips are visible.";
    requestAnimationFrame(processCameraFrame);
    render();
  } catch (error) {
    runtime.statusText = `Could not start camera: ${error.message}`;
    updateRuntimePanel();
  }
}

function stopCamera() {
  runtime.cameraActive = false;
  runtime.processing = false;
  runtime.lastResults = null;
  runtime.lastPoseData = null;
  runtime.wristHistory = { left: [], right: [] };
  runtime.headYHistory = [];
  if (runtime.stream) {
    runtime.stream.getTracks().forEach((track) => track.stop());
  }
  runtime.stream = null;
  if (runtime.videoEl) {
    runtime.videoEl.srcObject = null;
  }
  if (runtime.canvasCtx && runtime.canvasEl) {
    runtime.canvasCtx.clearRect(0, 0, runtime.canvasEl.width, runtime.canvasEl.height);
  }
  runtime.statusText = "Camera stopped.";
}

async function processCameraFrame() {
  if (!runtime.cameraActive || !runtime.pose || !runtime.videoEl) {
    return;
  }
  if (runtime.videoEl.readyState >= 2 && !runtime.processing) {
    try {
      runtime.processing = true;
      await runtime.pose.send({ image: runtime.videoEl });
    } catch (error) {
      runtime.statusText = `Pose processing error: ${error.message}`;
    } finally {
      runtime.processing = false;
    }
  }
  requestAnimationFrame(processCameraFrame);
}

function handlePoseResults(results) {
  runtime.lastResults = results;
  drawPoseScene(results);
  if (!results.poseLandmarks || !runtime.canvasEl) {
    runtime.lastPoseData = null;
    if (!runtime.activeSession?.running) {
      runtime.statusText = "Pose not found yet. Step into the frame.";
      updateRuntimePanel();
    }
    return;
  }
  const poseData = buildPoseData(results.poseLandmarks, runtime.canvasEl.width, runtime.canvasEl.height);
  runtime.lastPoseData = poseData;
  runtime.wristHistory.left.push({ t: performance.now(), point: [...poseData.l_wrist] });
  runtime.wristHistory.right.push({ t: performance.now(), point: [...poseData.r_wrist] });
  runtime.wristHistory.left = runtime.wristHistory.left.slice(-7);
  runtime.wristHistory.right = runtime.wristHistory.right.slice(-7);
  runtime.headYHistory.push(poseData.nose[1]);
  runtime.headYHistory = runtime.headYHistory.slice(-30);

  if (poseData.minVisibility < 0.45) {
    runtime.statusText = "Move back a little so camera sees your head, both hands, and hips.";
    updateRuntimePanel();
    return;
  }
  const defense = defenseState(poseData);
  runtime.statusText = `Guard ${defense.guard ? "ON" : "OFF"} · Lean ${defense.leanRatio.toFixed(2)} · Camera tracking stable`;
  if (runtime.activeSession?.running) {
    processSession(poseData, defense);
  }
  updateRuntimePanel();
}

function drawPoseScene(results) {
  if (!runtime.canvasCtx || !runtime.canvasEl || !runtime.videoEl) {
    return;
  }
  const ctx = runtime.canvasCtx;
  const canvas = runtime.canvasEl;
  ctx.save();
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.translate(canvas.width, 0);
  ctx.scale(-1, 1);
  ctx.drawImage(runtime.videoEl, 0, 0, canvas.width, canvas.height);
  ctx.restore();

  if (results.poseLandmarks) {
    const drawPoint = (indexA, indexB) => {
      const a = results.poseLandmarks[indexA];
      const b = results.poseLandmarks[indexB];
      if (!a || !b) return;
      const ax = canvas.width - a.x * canvas.width;
      const ay = a.y * canvas.height;
      const bx = canvas.width - b.x * canvas.width;
      const by = b.y * canvas.height;
      ctx.strokeStyle = "rgba(103, 232, 249, 0.72)";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(ax, ay);
      ctx.lineTo(bx, by);
      ctx.stroke();
    };

    [
      [11, 13],
      [13, 15],
      [12, 14],
      [14, 16],
      [11, 12],
      [11, 23],
      [12, 24],
      [23, 24],
    ].forEach(([a, b]) => drawPoint(a, b));

    [0, 11, 12, 13, 14, 15, 16, 23, 24].forEach((index) => {
      const point = results.poseLandmarks[index];
      const x = canvas.width - point.x * canvas.width;
      const y = point.y * canvas.height;
      ctx.fillStyle = index === 15 || index === 16 ? "#facc15" : "#67e8f9";
      ctx.beginPath();
      ctx.arc(x, y, index === 15 || index === 16 ? 7 : 5, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  if (runtime.activeSession?.running && runtime.activeSession.prompt) {
    ctx.fillStyle = "rgba(7, 17, 31, 0.82)";
    ctx.fillRect(24, 24, 320, 110);
    ctx.strokeStyle = runtime.activeSession.prompt.type === "defense" ? "#fb7185" : "#facc15";
    ctx.lineWidth = 2;
    ctx.strokeRect(24, 24, 320, 110);
    ctx.fillStyle = "#67e8f9";
    ctx.font = "18px Rajdhani";
    ctx.fillText(runtime.activeSession.mode === "fight" ? "LIVE PROMPT" : "TRAINING PROMPT", 42, 54);
    ctx.fillStyle = "#f5fbff";
    ctx.font = "36px Rajdhani";
    ctx.fillText(MOVES[runtime.activeSession.prompt.expectedMoveId].label, 42, 92);
    ctx.fillStyle = "#9bb3c8";
    ctx.font = "17px Space Grotesk";
    ctx.fillText(MOVES[runtime.activeSession.prompt.expectedMoveId].hint, 42, 118);
  }
}

function buildPoseData(landmarks, frameW, frameH) {
  const pt = (idx) => {
    const lm = landmarks[idx];
    return [[lm.x * frameW, lm.y * frameH, lm.z], lm.visibility ?? 1];
  };

  const [nose, noseVis] = pt(0);
  const [mpLElbow, leVis] = pt(13);
  const [mpRElbow, reVis] = pt(14);
  const [mpLShoulder, lsVis] = pt(11);
  const [mpRShoulder, rsVis] = pt(12);
  const [mpLWrist, lwVis] = pt(15);
  const [mpRWrist, rwVis] = pt(16);
  const [lHip, lhVis] = pt(23);
  const [rHip, rhVis] = pt(24);

  let lElbow = mpLElbow;
  let rElbow = mpRElbow;
  let lShoulder = mpLShoulder;
  let rShoulder = mpRShoulder;
  let lWrist = mpLWrist;
  let rWrist = mpRWrist;

  if (mpLShoulder[0] > mpRShoulder[0]) {
    lElbow = mpRElbow;
    rElbow = mpLElbow;
    lShoulder = mpRShoulder;
    rShoulder = mpLShoulder;
    lWrist = mpRWrist;
    rWrist = mpLWrist;
  }

  const shoulderMid = averagePoint(lShoulder, rShoulder);
  const hipMid = averagePoint(lHip, rHip);
  const shoulderWidth = Math.max(distance2D(lShoulder, rShoulder), 1);
  const torsoHeight = Math.max(distance2D(shoulderMid, hipMid), 1);

  return {
    nose,
    shoulderMid,
    hipMid,
    l_elbow: lElbow,
    r_elbow: rElbow,
    l_shoulder: lShoulder,
    r_shoulder: rShoulder,
    l_wrist: lWrist,
    r_wrist: rWrist,
    shoulderWidth,
    torsoHeight,
    minVisibility: Math.min(noseVis, leVis, reVis, lsVis, rsVis, lwVis, rwVis, lhVis, rhVis),
  };
}

function averagePoint(a, b) {
  return [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2];
}

function distance2D(a, b) {
  return Math.hypot(a[0] - b[0], a[1] - b[1]);
}

function defenseState(poseData) {
  const nose = poseData.nose;
  const shoulderMid = poseData.shoulderMid;
  const shoulderWidth = poseData.shoulderWidth;
  const lWrist = poseData.l_wrist;
  const rWrist = poseData.r_wrist;

  const guardRadius = shoulderWidth * 0.42;
  const leftNear = distance2D(lWrist, nose) < guardRadius;
  const rightNear = distance2D(rWrist, nose) < guardRadius;
  const handsHigh = lWrist[1] < shoulderMid[1] + shoulderWidth * 0.08 && rWrist[1] < shoulderMid[1] + shoulderWidth * 0.08;
  const guard = leftNear && rightNear && handsHigh;

  const leanRatio = (nose[0] - shoulderMid[0]) / shoulderWidth;
  const baselineY = runtime.headYHistory.length > 10 ? Math.min(...runtime.headYHistory) : nose[1];
  const duck = nose[1] - baselineY > shoulderWidth * 0.35;

  return {
    guard,
    slip_left: leanRatio < -0.18,
    slip_right: leanRatio > 0.18,
    duck,
    leanRatio,
  };
}

function summarizeWristMotion(hand, poseData) {
  const history = runtime.wristHistory[hand];
  if (!history || history.length < 5) {
    return null;
  }
  const points = history.map((item) => item.point);
  const times = history.map((item) => item.t);
  const start = points[0];
  const end = points[points.length - 1];
  const mid = points[Math.floor(points.length / 2)];
  const shoulderWidth = poseData.shoulderWidth;
  const torsoHeight = poseData.torsoHeight;

  let pathLen = 0;
  let peakSpeed = 0;
  for (let index = 1; index < points.length; index += 1) {
    const segment = distance2D(points[index - 1], points[index]);
    pathLen += segment / shoulderWidth;
    const dt = Math.max(1, times[index] - times[index - 1]) / 1000;
    peakSpeed = Math.max(peakSpeed, segment / shoulderWidth / dt);
  }

  const shoulder = hand === "left" ? poseData.l_shoulder : poseData.r_shoulder;
  const elbow = hand === "left" ? poseData.l_elbow : poseData.r_elbow;
  const wrist = hand === "left" ? poseData.l_wrist : poseData.r_wrist;

  return {
    pre_dx: (mid[0] - start[0]) / shoulderWidth,
    pre_dy: (mid[1] - start[1]) / torsoHeight,
    dx: (end[0] - start[0]) / shoulderWidth,
    dy: (end[1] - start[1]) / torsoHeight,
    dz: start[2] - end[2],
    mid_dz: mid[2] - end[2],
    late_dx: (end[0] - mid[0]) / shoulderWidth,
    late_dy: (end[1] - mid[1]) / torsoHeight,
    planar: distance2D(start, end) / shoulderWidth,
    path_len: pathLen,
    net_displacement: distance2D(start, end) / shoulderWidth,
    peak_speed: peakSpeed,
    reach_x: (wrist[0] - shoulder[0]) / shoulderWidth,
    end_hand_height: (shoulder[1] - end[1]) / torsoHeight,
    start_hand_height: (shoulder[1] - start[1]) / torsoHeight,
    elbow_to_wrist_y: (elbow[1] - wrist[1]) / torsoHeight,
    motion_energy: pathLen + Math.abs(start[2] - end[2]) * 0.9 + Math.abs((end[1] - start[1]) / torsoHeight) * 0.55,
  };
}

function motionIsActive(motion, strict = false) {
  if (!motion) {
    return false;
  }
  const minPath = strict ? 0.22 : 0.16;
  const minDisplacement = strict ? 0.17 : 0.13;
  const minPeakSpeed = strict ? 1.95 : 1.34;
  const minEnergy = strict ? 0.46 : 0.31;
  return (
    motion.path_len >= minPath &&
    motion.net_displacement >= minDisplacement &&
    motion.peak_speed >= minPeakSpeed &&
    motion.motion_energy >= minEnergy
  );
}

function detectMove(moveId, poseData, defense) {
  if (!poseData) {
    return false;
  }
  if (DEFENSE_MOVE_IDS.includes(moveId)) {
    if (moveId === "guard") return defense.guard;
    if (moveId === "slip_left") return defense.slip_left;
    if (moveId === "slip_right") return defense.slip_right;
    if (moveId === "duck") return defense.duck;
    return false;
  }

  const move = MOVES[moveId];
  const motion = summarizeWristMotion(move.hand, poseData);
  if (!motionIsActive(motion, false)) {
    return false;
  }
  if (moveId.endsWith("hook")) {
    const directionOk = move.hand === "left" ? motion.dx > 0.11 : motion.dx < -0.11;
    const recoilOk = move.hand === "left" ? motion.pre_dx < -0.02 : motion.pre_dx > 0.02;
    return directionOk && motion.planar > 0.14 && (recoilOk || Math.abs(motion.dx) > 0.18);
  }
  if (moveId.endsWith("straight")) {
    const reachOk = move.hand === "left" ? motion.reach_x > 0.05 : motion.reach_x < -0.05;
    return motion.dz > 0.04 && motion.mid_dz > 0.015 && reachOk;
  }
  if (moveId.endsWith("uppercut")) {
    return (
      motion.pre_dy > 0.02 &&
      motion.dy < -0.07 &&
      motion.late_dy < -0.03 &&
      motion.end_hand_height > motion.start_hand_height + 0.02
    );
  }
  return false;
}

function beginFightSession() {
  if (!runtime.cameraActive) {
    runtime.statusText = "Start camera first.";
    updateRuntimePanel();
    return;
  }
  const arena = selectedArena();
  const opponent = currentArenaOpponent(arena.id);
  if (!isArenaUnlocked(arena.id)) {
    runtime.statusText = `Arena locked: ${arena.unlockRule}`;
    updateRuntimePanel();
    return;
  }
  if (state.career.cash < arena.entryFee) {
    runtime.statusText = "Not enough cash for the entry fee.";
    updateRuntimePanel();
    return;
  }

  runtime.activeSession = {
    mode: "fight",
    running: true,
    startedAt: performance.now(),
    arenaId: arena.id,
    opponentId: opponent?.id || "",
    prompt: null,
    promptExpiresAt: 0,
    nextPromptAt: performance.now() + 1200,
    playerHp: MAX_HP + Math.round(state.career.stats.stamina * 0.45),
    enemyHp: MAX_HP + arena.enemyHpBonus + 6 + arenaRank(arena.id) * 4,
    combo: 0,
    landedHits: 0,
    thrown: 0,
    taken: 0,
    lastDetectionAt: 0,
  };
  runtime.lastMoveFeedback = "Fight started. Wait for the first prompt.";
  runtime.statusText = `Live fight started in ${arena.name}.`;
  updateRuntimePanel();
}

function beginTrainingSession() {
  if (!runtime.cameraActive) {
    runtime.statusText = "Start camera first.";
    updateRuntimePanel();
    return;
  }
  const drill = selectedTraining();
  const cost = trainingCost(drill.id);
  if (state.career.cash < cost) {
    runtime.statusText = `Need $${cost} to start ${drill.title}.`;
    updateRuntimePanel();
    return;
  }
  runtime.activeSession = {
    mode: "training",
    running: true,
    trainingId: drill.id,
    startedAt: performance.now(),
    endsAt: performance.now() + TRAINING_DURATION_MS,
    prompt: null,
    promptExpiresAt: 0,
    nextPromptAt: performance.now() + 900,
    hits: 0,
    misses: 0,
    score: 0,
    samples: 0,
    remainingSeconds: 30,
    lastDetectionAt: 0,
  };
  runtime.lastMoveFeedback = `${drill.title} drill started.`;
  runtime.statusText = "Training is live.";
  updateRuntimePanel();
}

function stopSession(message = "Session stopped.") {
  runtime.activeSession = null;
  runtime.lastMoveFeedback = message;
  runtime.statusText = message;
}

function processSession(poseData, defense) {
  const session = runtime.activeSession;
  if (!session?.running) {
    return;
  }
  const now = performance.now();

  if (session.mode === "training") {
    session.remainingSeconds = Math.max(0, Math.ceil((session.endsAt - now) / 1000));
    if (now >= session.endsAt) {
      finishTrainingSession();
      return;
    }
  }

  if (!session.prompt && now >= session.nextPromptAt) {
    session.prompt = makePrompt(session);
    session.promptExpiresAt = now + session.prompt.windowMs;
    runtime.lastMoveFeedback = MOVES[session.prompt.expectedMoveId].hint;
  }

  if (!session.prompt) {
    return;
  }

  if (now - session.lastDetectionAt > 220 && detectMove(session.prompt.expectedMoveId, poseData, defense)) {
    session.lastDetectionAt = now;
    resolvePrompt(true);
    return;
  }

  if (now > session.promptExpiresAt) {
    resolvePrompt(false);
  }
}

function makePrompt(session) {
  if (session.mode === "training") {
    const drill = TRAINING.find((item) => item.id === session.trainingId) || TRAINING[0];
    const expectedMoveId = sample(drill.moves);
    return {
      type: MOVES[expectedMoveId].type,
      expectedMoveId,
      windowMs: drill.id === "agility" ? 1300 : 1600,
    };
  }

  const rank = arenaRank(session.arenaId);
  const offenseChance = 0.62 - rank * 0.07;
  if (Math.random() < offenseChance) {
    return {
      type: "offense",
      expectedMoveId: sample(OFFENSE_MOVE_IDS),
      windowMs: Math.max(900, 1600 * selectedArena().speedScale),
    };
  }
  const expectedMoveId = sample(["guard", "slip_left", "slip_right", "duck"]);
  return {
    type: "defense",
    expectedMoveId,
    windowMs: Math.max(800, 1450 * selectedArena().speedScale),
  };
}

function resolvePrompt(success) {
  const session = runtime.activeSession;
  if (!session?.prompt) {
    return;
  }
  const prompt = session.prompt;
  if (session.mode === "training") {
    session.samples += 1;
    if (success) {
      session.hits += 1;
      session.score += prompt.type === "defense" ? 1.15 : 1.0;
      runtime.lastMoveFeedback = `${MOVES[prompt.expectedMoveId].label} counted clean.`;
    } else {
      session.misses += 1;
      runtime.lastMoveFeedback = `${MOVES[prompt.expectedMoveId].label} missed.`;
    }
  } else if (success) {
    session.combo += 1;
    if (prompt.type === "offense") {
      session.thrown += 1;
      session.landedHits += 1;
      const damage = 1 + Number(state.career.stats.power > 14) + Number(session.combo >= 3);
      session.enemyHp = Math.max(0, session.enemyHp - damage);
      runtime.lastMoveFeedback = `${MOVES[prompt.expectedMoveId].label} landed for ${damage} damage.`;
    } else {
      runtime.lastMoveFeedback = `${MOVES[prompt.expectedMoveId].label} defended clean.`;
    }
  } else {
    session.combo = 0;
    if (prompt.type === "offense") {
      session.thrown += 1;
      runtime.lastMoveFeedback = `${MOVES[prompt.expectedMoveId].label} did not land in time.`;
    } else {
      const damage = 2 + Number(arenaRank(session.arenaId) >= 2);
      session.playerHp = Math.max(0, session.playerHp - damage);
      session.taken += 1;
      runtime.lastMoveFeedback = `${MOVES[prompt.expectedMoveId].label} late. You took ${damage} damage.`;
    }
  }

  session.prompt = null;
  session.nextPromptAt = performance.now() + (session.mode === "fight" ? 550 : 380);

  if (session.mode === "fight" && (session.playerHp <= 0 || session.enemyHp <= 0)) {
    finishFightSession(session.enemyHp <= 0);
  }
}

function finishFightSession(won) {
  const session = runtime.activeSession;
  const arena = selectedArena();
  const opponent = findOpponent(session.opponentId) || currentArenaOpponent(arena.id);
  state.career.cash -= arena.entryFee + arena.upkeep;
  if (won) {
    const payout = Math.round(arena.basePrize * (1 + session.landedHits * 0.06 + session.combo * 0.04));
    state.career.cash += payout;
    state.career.points += Math.round(arena.basePrize * 0.65 + session.landedHits * 8 + session.combo * 5);
    state.career.wins += 1;
    state.career.sponsorCount += Number(session.combo >= 3);
    if (arena.id === "state") {
      state.career.stateBeltWon = true;
    }
    state.career.matchHistory.unshift({
      result: "WIN",
      arena: arena.name,
      opponent: opponent?.name || "Rival",
      detail: "KO/TKO",
      payout,
      combo: session.combo,
    });
    runtime.lastMoveFeedback = `Fight won. Payout $${payout}.`;
  } else {
    state.career.losses += 1;
    state.career.points += Math.max(20, Math.round(arena.basePrize * 0.12));
    state.career.matchHistory.unshift({
      result: "LOSS",
      arena: arena.name,
      opponent: opponent?.name || "Rival",
      detail: "Stopped",
      payout: 0,
      combo: session.combo,
    });
    runtime.lastMoveFeedback = "Fight lost. Back to the map and train up.";
  }
  state.career.matchHistory = state.career.matchHistory.slice(0, 10);
  evolveRosterAfterFight(opponent?.id, won);
  refreshArenaAssignments(arena.id);
  runtime.statusText = won ? "Fight complete: win." : "Fight complete: loss.";
  runtime.activeSession = null;
  saveState();
  render();
}

function finishTrainingSession() {
  const session = runtime.activeSession;
  const trainingId = session.trainingId;
  const cost = trainingCost(trainingId);
  state.career.cash -= cost;
  const average = session.samples ? session.score / session.samples : 0.25;
  const gain = clamp(average, 0.25, 2.4);
  state.career.stats[trainingId] += gain;
  runtime.lastMoveFeedback = `${capitalize(trainingId)} +${gain.toFixed(2)}.`;
  runtime.statusText = "Training complete.";
  runtime.activeSession = null;
  saveState();
  render();
}

function openCropModal(target) {
  cropState.target = target;
  cropState.image = null;
  cropTitle.textContent = target.type === "player" ? "Crop Boxer Head" : "Crop Opponent Head";
  cropZoom.value = "1.2";
  cropOffsetX.value = "0";
  cropOffsetY.value = "0";
  photoInput.value = "";
  renderCropPreview();
  cropModal.showModal();
}

function renderCropPreview() {
  const ctx = cropCanvas.getContext("2d");
  ctx.clearRect(0, 0, cropCanvas.width, cropCanvas.height);
  ctx.fillStyle = "#08131f";
  ctx.fillRect(0, 0, cropCanvas.width, cropCanvas.height);

  if (!cropState.image) {
    ctx.fillStyle = "#9bb3c8";
    ctx.font = "16px Space Grotesk";
    ctx.textAlign = "center";
    ctx.fillText("Choose a photo to begin", cropCanvas.width / 2, cropCanvas.height / 2);
    return;
  }

  const zoom = Number(cropZoom.value);
  const offsetX = Number(cropOffsetX.value);
  const offsetY = Number(cropOffsetY.value);
  const image = cropState.image;
  const baseScale = Math.max(cropCanvas.width / image.width, cropCanvas.height / image.height) * zoom;
  const width = image.width * baseScale;
  const height = image.height * baseScale;
  const x = (cropCanvas.width - width) / 2 + offsetX;
  const y = (cropCanvas.height - height) / 2 + offsetY;

  ctx.drawImage(image, x, y, width, height);
  ctx.strokeStyle = "#facc15";
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.ellipse(cropCanvas.width / 2, cropCanvas.height / 2, 132, 132, 0, 0, Math.PI * 2);
  ctx.stroke();
}

function exportCropDataUrl() {
  const exportCanvas = document.createElement("canvas");
  exportCanvas.width = 384;
  exportCanvas.height = 384;
  const ctx = exportCanvas.getContext("2d");
  const zoom = Number(cropZoom.value);
  const offsetX = Number(cropOffsetX.value) * 1.2;
  const offsetY = Number(cropOffsetY.value) * 1.2;
  const image = cropState.image;
  const baseScale = Math.max(exportCanvas.width / image.width, exportCanvas.height / image.height) * zoom;
  const width = image.width * baseScale;
  const height = image.height * baseScale;
  const x = (exportCanvas.width - width) / 2 + offsetX;
  const y = (exportCanvas.height - height) / 2 + offsetY;
  ctx.save();
  ctx.beginPath();
  ctx.ellipse(exportCanvas.width / 2, exportCanvas.height / 2, 176, 176, 0, 0, Math.PI * 2);
  ctx.clip();
  ctx.drawImage(image, x, y, width, height);
  ctx.restore();
  return exportCanvas.toDataURL("image/png");
}

function fileToImage(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = reject;
      img.src = reader.result;
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function sample(array) {
  return array[Math.floor(Math.random() * array.length)];
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function capitalize(value) {
  return value[0].toUpperCase() + value.slice(1);
}

function arenaBackground(arenaId) {
  return `./assets/backgrounds/${arenaId}.png`;
}

function normalizeRoster(opponents) {
  const fallbackById = Object.fromEntries(DEFAULT_OPPONENTS.map((opponent) => [opponent.id, opponent]));
  return opponents.map((opponent) => {
    const fallback = fallbackById[opponent.id] || {};
    return {
      ...fallback,
      ...opponent,
      rating: Number(opponent.rating ?? fallback.rating ?? 20),
      minArenaRank: Number(opponent.minArenaRank ?? fallback.minArenaRank ?? 0),
      maxArenaRank: Number(opponent.maxArenaRank ?? fallback.maxArenaRank ?? 4),
      enabled: opponent.enabled !== false,
      isBuiltin: opponent.isBuiltin ?? fallback.isBuiltin ?? false,
    };
  });
}

function normalizeArenaAssignments(assignments, opponents) {
  const validIds = new Set(opponents.map((opponent) => opponent.id));
  const normalized = {};
  for (const arena of ARENAS) {
    if (assignments[arena.id] && validIds.has(assignments[arena.id])) {
      normalized[arena.id] = assignments[arena.id];
    }
  }
  return normalized;
}

function eligibleOpponentsForArena(arenaId) {
  const rank = arenaRank(arenaId);
  const roster = state.opponents.filter((opponent) => opponent.enabled !== false);
  const eligible = roster.filter((opponent) => rank >= (opponent.minArenaRank ?? 0) && rank <= (opponent.maxArenaRank ?? 4));
  return eligible.length ? eligible : roster;
}

function refreshArenaAssignments(forceArenaId = "") {
  const usedIds = new Set();
  for (const arena of ARENAS) {
    if (forceArenaId && arena.id !== forceArenaId && state.arenaAssignments?.[arena.id]) {
      usedIds.add(state.arenaAssignments[arena.id]);
    }
  }
  for (const arena of ARENAS) {
    if (!forceArenaId && state.arenaAssignments?.[arena.id] && findOpponent(state.arenaAssignments[arena.id])) {
      usedIds.add(state.arenaAssignments[arena.id]);
      continue;
    }
    if (forceArenaId && arena.id !== forceArenaId && state.arenaAssignments?.[arena.id]) {
      continue;
    }
    const pool = eligibleOpponentsForArena(arena.id);
    const available = pool.filter((opponent) => !usedIds.has(opponent.id));
    const picked = sample((available.length ? available : pool));
    if (picked) {
      state.arenaAssignments[arena.id] = picked.id;
      usedIds.add(picked.id);
    }
  }
}

function evolveRosterAfterFight(foughtOpponentId, playerWon) {
  state.opponents.forEach((opponent) => {
    const delta = opponent.id === foughtOpponentId
      ? (playerWon ? -2 : 2)
      : Math.round((Math.random() - 0.5) * 4);
    opponent.rating = Math.max(12, Math.min(96, Number(opponent.rating ?? 20) + delta));
    const wins = Math.max(0, parseInt(String(opponent.record).split("-")[0] || "0", 10));
    const losses = Math.max(0, parseInt(String(opponent.record).split("-")[1] || "0", 10));
    const nextWins = delta > 0 ? wins + 1 : wins;
    const nextLosses = delta < 0 ? losses + 1 : losses;
    opponent.record = `${nextWins}-${nextLosses}`;
    opponent.minArenaRank = arenaFloorFromRating(opponent.rating);
    opponent.maxArenaRank = Math.min(4, opponent.minArenaRank + 1 + Number(opponent.rating >= 52) + Number(opponent.rating >= 70));
  });
}

function arenaFloorFromRating(rating) {
  if (rating >= 70) return 3;
  if (rating >= 54) return 2;
  if (rating >= 34) return 1;
  return 0;
}

function opponentAvatar(opponent) {
  if (!opponent) {
    return "";
  }
  if (opponent.photo) {
    return opponent.photo;
  }
  return `./assets/opponents/${opponent.id}.png`;
}

function avatarMarkup(src, alt) {
  if (!src) {
    return `<div class="avatar-placeholder">${escapeHtml(alt)}</div>`;
  }
  return `<img src="${src}" alt="${escapeHtml(alt)}" />`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

render();
