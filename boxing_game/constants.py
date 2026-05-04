WINDOW_NAME = "Boxing Command Arena"
MAX_HP = 16
ROUNDS_TO_WIN = 3
REACTION_TIME = 2.0
ROUND_FREEZE_TIME = 5.0
PUNCH_COOLDOWN = 0.30
TUTORIAL_WINDOW = 2.8

BG = (18, 14, 26)
CYAN = (52, 223, 226)
MAGENTA = (255, 90, 150)
GOLD = (255, 212, 90)
GREEN = (80, 215, 120)
RED = (60, 60, 255)
WHITE = (245, 245, 245)
SOFT = (180, 180, 200)
PANEL = (24, 21, 38)
ORANGE = (0, 165, 255)
LIME = (80, 255, 160)
BLUE_GLOW = (255, 180, 60)

OFFENSE_MOVES = [
    {"id": "left_hook", "label": "LEFT HOOK", "hand": "left", "hint": "Swing your left fist across"},
    {"id": "left_straight", "label": "LEFT STRAIGHT", "hand": "left", "hint": "Punch your left fist straight forward"},
    {"id": "left_uppercut", "label": "LEFT UPPERCUT", "hand": "left", "hint": "Drive your left fist upward"},
    {"id": "right_hook", "label": "RIGHT HOOK", "hand": "right", "hint": "Swing your right fist across"},
    {"id": "right_straight", "label": "RIGHT STRAIGHT", "hand": "right", "hint": "Punch your right fist straight forward"},
    {"id": "right_uppercut", "label": "RIGHT UPPERCUT", "hand": "right", "hint": "Drive your right fist upward"},
]

DEFENSE_MOVES = [
    {"id": "guard", "label": "DOUBLE GUARD", "hint": "Put both fists tightly in front of your head"},
    {"id": "slip_left", "label": "SLIP LEFT", "hint": "Lean your head and torso to the left"},
    {"id": "slip_right", "label": "SLIP RIGHT", "hint": "Lean your head and torso to the right"},
    {"id": "duck", "label": "DUCK", "hint": "Squat down to dodge high attacks"},
]

MOVE_BY_ID = {move["id"]: move for move in OFFENSE_MOVES + DEFENSE_MOVES}
TUTORIAL_SEQUENCE = [
    "left_straight",
    "right_straight",
    "left_hook",
    "right_hook",
    "left_uppercut",
    "right_uppercut",
    "guard",
    "slip_left",
    "slip_right",
    "duck",
]

CAREER_ARENAS = [
    {
        "id": "town",
        "name": "Los Angeles",
        "scene": "Southland Amateur Hall",
        "entry_fee": 0,
        "base_prize": 100,
        "upkeep": 20,
        "enemy_hp_bonus": 0,
        "speed_scale": 1.00,
        "unlock_rule": "Start here",
        "challenge": "Local SoCal pace. Slow single jabs and long reaction windows to learn your reads.",
    },
    {
        "id": "city",
        "name": "Las Vegas",
        "scene": "Desert Fight Club",
        "entry_fee": 80,
        "base_prize": 260,
        "upkeep": 35,
        "enemy_hp_bonus": 80,
        "speed_scale": 0.92,
        "unlock_rule": "5 wins and 0 losses",
        "challenge": "Sharper purse-fight rhythm. Rival starts chaining 2-hit combos and slipping off center.",
    },
    {
        "id": "state",
        "name": "London",
        "scene": "West End Fight Night",
        "entry_fee": 160,
        "base_prize": 520,
        "upkeep": 60,
        "enemy_hp_bonus": 25,
        "speed_scale": 0.86,
        "unlock_rule": "Career points above 500",
        "challenge": "Pressure boxing starts here. Empty swings can trigger counters and live exchanges.",
    },
    {
        "id": "national",
        "name": "Riyadh",
        "scene": "Global Season Ring",
        "entry_fee": 320,
        "base_prize": 1100,
        "upkeep": 95,
        "enemy_hp_bonus": 50,
        "speed_scale": 0.78,
        "unlock_rule": "Win the State belt",
        "challenge": "Broadcast-speed rival. Guard high, read the shoulders, and survive the volume.",
    },
    {
        "id": "worldwide",
        "name": "Chongqing",
        "scene": "Mountain Megafight",
        "entry_fee": 650,
        "base_prize": 2200,
        "upkeep": 140,
        "enemy_hp_bonus": 100,
        "speed_scale": 0.64,
        "unlock_rule": "Reach World Top 10",
        "challenge": "World summit pace. Build real combinations to break elite guard adjustments and late counters.",
    },
]

HUB_MENU = ["Fight", "Locker", "Training"]
TRAINING_MENU = ["Power", "Stamina", "Agility"]

OPPONENT_ROSTER = {
    "town": {"id": "milo_vega", "name": "Milo Vega", "title": "Garage Prospect", "height": "5'10\"", "weight": "154 lb", "record": "6-1"},
    "city": {"id": "nyx_striker", "name": "Nyx Striker", "title": "Neon Runner", "height": "5'11\"", "weight": "160 lb", "record": "12-2"},
    "state": {"id": "dante_crest", "name": "Dante Crest", "title": "State Technician", "height": "6'0\"", "weight": "168 lb", "record": "19-4"},
    "national": {"id": "marcus_hale", "name": "Marcus Hale", "title": "Broadcast Champion", "height": "6'1\"", "weight": "172 lb", "record": "26-3"},
    "worldwide": {"id": "orion_voss", "name": "Orion Voss", "title": "World Summit", "height": "6'2\"", "weight": "178 lb", "record": "34-2"},
}
