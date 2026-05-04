import math
import random
import time
from collections import deque
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from boxing_game.audio import AudioManager
from boxing_game.career import BoxingCareer
from boxing_game.constants import (
    BG,
    BLUE_GLOW,
    CAREER_ARENAS,
    CYAN,
    DEFENSE_MOVES,
    GOLD,
    GREEN,
    HUB_MENU,
    LIME,
    MAGENTA,
    MAX_HP,
    MOVE_BY_ID,
    OFFENSE_MOVES,
    OPPONENT_ROSTER,
    ORANGE,
    PANEL,
    PUNCH_COOLDOWN,
    REACTION_TIME,
    RED,
    ROUNDS_TO_WIN,
    ROUND_FREEZE_TIME,
    SOFT,
    TRAINING_MENU,
    TUTORIAL_SEQUENCE,
    TUTORIAL_WINDOW,
    WHITE,
    WINDOW_NAME,
)
from boxing_game.motion import merge_motion_profile, profile_match, tutorial_rep_target
from boxing_game.storage import SaveStore

SAVE_SCHEMA_VERSION = 2
ASSET_ROOT = Path(__file__).resolve().parent / "boxing_game" / "assets"
ARENA_BACKGROUND_NAMES = {arena["id"]: f"{arena['id']}.png" for arena in CAREER_ARENAS}
TARGET_STYLE_BY_MOVE = {
    "left_straight": "jab_target",
    "right_straight": "jab_target",
    "left_hook": "hook_target",
    "right_hook": "hook_target",
    "left_uppercut": "uppercut_target",
    "right_uppercut": "uppercut_target",
}
TARGET_THEME = {
    "jab_target": {"color": CYAN, "label": "JAB TARGET", "shape": "circle"},
    "hook_target": {"color": GREEN, "label": "HOOK TARGET", "shape": "curve"},
    "uppercut_target": {"color": GOLD, "label": "UPPERCUT TARGET", "shape": "vertical"},
    "body_target": {"color": ORANGE, "label": "BODY SHIELD", "shape": "body"},
}
BLOCK_COUNTER_RULES = {
    "wide_gate": {
        "counter": "straight",
        "counter_moves": ["left_straight", "right_straight"],
        "label": "WIDE GATE",
        "hint": "Gloves are spread wide. Fire straight down the middle.",
    },
    "tight_shell": {
        "counter": "hook",
        "counter_moves": ["left_hook", "right_hook"],
        "label": "TIGHT SHELL",
        "hint": "Gloves are tight together. Wrap around with a hook.",
    },
    "left_post": {
        "counter": "left_straight",
        "counter_moves": ["left_straight", "right_hook"],
        "label": "LEFT POST",
        "hint": "Lead hand posts in front. Left straight or right hook can beat it.",
    },
    "elbows_high": {
        "counter": "straight",
        "counter_moves": ["left_straight", "right_straight"],
        "label": "ELBOWS HIGH",
        "hint": "Hands sit horizontal and lower. Snap a straight over the shelf.",
    },
}


class BoxingCommandArena:
    def __init__(self, camera_id=0):
        self.cap = cv2.VideoCapture(camera_id)
        self.pose = mp.solutions.pose.Pose(
            model_complexity=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.mp_drawing = mp.solutions.drawing_utils
        self.storage = SaveStore()
        self.assets = self.load_assets()
        self.audio = AudioManager()
        self.font_paths = {
            "display": "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf",
            "body": "/System/Library/Fonts/SFCompact.ttf",
            "mono": "/System/Library/Fonts/SFNSMono.ttf",
        }
        self.font_cache = {}
        saved = self.storage.load()
        self.career = BoxingCareer.from_dict(saved.get("career"))
        self.learned_profiles = self.load_learned_profiles(saved)
        self.tutorial_samples = {move_id: 0 for move_id in TUTORIAL_SEQUENCE}
        self.app_state = "name_entry" if not self.career.player_name else "hub"
        self.selected_hub_index = 0
        self.selected_training_index = 0
        self.selected_arena_index = 0
        self.active_arena = CAREER_ARENAS[0]
        self.name_input = self.career.player_name or ""
        self.menu_action_cooldown_until = 0.0
        self.match_settled = False
        self.last_payout = 0
        self.match_landed_hits = 0
        self.combo_peak = 0
        self.match_enemy_thrown_punches = 0
        self.match_enemy_landed_hits = 0
        self.rounds_needed_to_win = 2
        self.player_knockdowns = 0
        self.enemy_knockdowns = 0
        self.knockdown_state = None
        self.player_getup_meter = 0.0
        self.recent_player_moves = deque(maxlen=5)
        self.training_mode = None
        self.training_started_at = 0.0
        self.training_duration = 18.0
        self.training_score_accum = 0.0
        self.training_samples = 0
        self.training_hits = 0
        self.training_misses = 0
        self.training_prompt = None
        self.training_sequence = []
        self.training_streak = 0
        self.training_combo_label = ""
        self.last_training_report = []
        self.training_combo_moves = []
        self.training_combo_index = 0
        self.last_pose_data = None
        self.fight_player_max_hp = MAX_HP
        self.fight_enemy_max_hp = MAX_HP
        self.fight_player_display_max_hp = MAX_HP
        self.fight_enemy_display_max_hp = MAX_HP
        self.player_stamina = MAX_HP
        self.enemy_stamina = MAX_HP
        self.last_player_attack_at = 0.0
        self.last_enemy_attack_at = 0.0
        self.last_energy_tick_at = time.time()
        self.wrist_history = {"left": deque(maxlen=7), "right": deque(maxlen=7)}
        self.head_y_history = deque(maxlen=30)
        self.last_punch_at = 0.0
        self.hit_flash_until = 0.0
        self.damage_flash_until = 0.0
        self.message = "Move back a little so camera sees your head, both hands, and hips."
        self.message_until = 0.0
        self.match_over = False
        self.match_winner = None
        self.combo_count = 0
        self.combo_until = 0.0
        self.impact_until = 0.0
        self.impact_move_id = None
        self.power_level = "LIGHT"
        self.last_detected_motion = None
        self.last_action_feedback = None
        self.current_prompt_timing = 0.0
        self.round_index = 1
        self.player_rounds = 0
        self.enemy_rounds = 0
        self.actions_cleared = 0
        self.prompt = None
        self.prompt_queue = deque()
        self.enemy_block = None
        self.enemy_attack_pose = None
        self.enemy_combo_flash_until = 0.0
        self.current_audio_key = None
        self.fight_help_until = 0.0
        self.fight_intro_until = 0.0
        self.realtime_action_until = 0.0
        self.realtime_next_event_at = 0.0
        self.realtime_active_attack = None
        self.realtime_mode = False
        self.recent_offense_families = deque(maxlen=4)
        self.enemy_attack_flash_until = 0.0
        self.enemy_attack_flash_hand = None
        self.block_contact_until = 0.0
        self.block_contact_side = None
        self.enemy_hand_render = {"left": None, "right": None}
        self.paused = False
        self.player_recover_until = 0.0
        self.opponent_recover_until = 0.0
        self.next_prompt_at = 0.0
        self.phase = "tutorial"
        self.tutorial_step = 0
        self.target_prompt = None
        self.current_opponent = OPPONENT_ROSTER[self.active_arena["id"]]
        self.reset_match()

    def load_learned_profiles(self, saved):
        profiles = dict(saved.get("learned_profiles", {}))
        schema_version = int(saved.get("schema_version", 0))
        if schema_version < SAVE_SCHEMA_VERSION:
            profiles = self.swap_punch_profiles(profiles)
        return profiles

    def swap_punch_profiles(self, profiles):
        swapped = dict(profiles)
        for left_id, right_id in (
            ("left_straight", "right_straight"),
            ("left_hook", "right_hook"),
            ("left_uppercut", "right_uppercut"),
        ):
            left_profile = swapped.get(left_id)
            right_profile = swapped.get(right_id)
            if left_profile is not None or right_profile is not None:
                swapped[left_id], swapped[right_id] = right_profile, left_profile
        return swapped

    def save_progress(self):
        self.storage.save(
            {
                "schema_version": SAVE_SCHEMA_VERSION,
                "career": self.career.to_dict(),
                "learned_profiles": self.learned_profiles,
            }
        )

    def load_assets(self):
        assets = {
            "backgrounds": {},
            "targets": {},
            "gloves": {},
            "sheets": {},
            "opponents": {},
        }
        for arena_id, filename in ARENA_BACKGROUND_NAMES.items():
            path = ASSET_ROOT / "backgrounds" / filename
            if path.exists():
                assets["backgrounds"][arena_id] = cv2.imread(str(path), cv2.IMREAD_COLOR)
        for name in ("jab_target", "hook_target", "uppercut_target", "body_target"):
            path = ASSET_ROOT / "targets" / f"{name}.png"
            if path.exists():
                assets["targets"][name] = cv2.imread(str(path), cv2.IMREAD_COLOR)
        for path in (ASSET_ROOT / "gloves").glob("*_glove_rgba.png"):
            assets["gloves"][path.stem] = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        for name in ("gloves_sheet", "targets_sheet"):
            path = ASSET_ROOT / f"{name}.png"
            if path.exists():
                assets["sheets"][name] = cv2.imread(str(path), cv2.IMREAD_COLOR)
        for opponent in OPPONENT_ROSTER.values():
            path = ASSET_ROOT / "opponents" / f"{opponent['id']}_rgba.png"
            if path.exists():
                assets["opponents"][opponent["id"]] = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        return assets

    def resize_cover(self, image, frame_w, frame_h):
        if image is None:
            return None
        src_h, src_w = image.shape[:2]
        scale = max(frame_w / max(src_w, 1), frame_h / max(src_h, 1))
        resized = cv2.resize(image, (int(src_w * scale), int(src_h * scale)), interpolation=cv2.INTER_LINEAR)
        y1 = max(0, (resized.shape[0] - frame_h) // 2)
        x1 = max(0, (resized.shape[1] - frame_w) // 2)
        return resized[y1 : y1 + frame_h, x1 : x1 + frame_w].copy()

    def overlay_rgba(self, frame, sprite, center, scale=1.0, angle=0.0, alpha_scale=1.0):
        if sprite is None or sprite.shape[2] < 4:
            return
        src_h, src_w = sprite.shape[:2]
        scaled_w = max(1, int(src_w * scale))
        scaled_h = max(1, int(src_h * scale))
        resized = cv2.resize(sprite, (scaled_w, scaled_h), interpolation=cv2.INTER_LINEAR)
        matrix = cv2.getRotationMatrix2D((scaled_w / 2, scaled_h / 2), angle, 1.0)
        rotated = cv2.warpAffine(
            resized,
            matrix,
            (scaled_w, scaled_h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0, 0),
        )
        x1 = int(center[0] - scaled_w / 2)
        y1 = int(center[1] - scaled_h / 2)
        x2 = x1 + scaled_w
        y2 = y1 + scaled_h
        frame_h, frame_w = frame.shape[:2]
        clip_x1 = max(0, x1)
        clip_y1 = max(0, y1)
        clip_x2 = min(frame_w, x2)
        clip_y2 = min(frame_h, y2)
        if clip_x1 >= clip_x2 or clip_y1 >= clip_y2:
            return
        crop = rotated[clip_y1 - y1 : clip_y2 - y1, clip_x1 - x1 : clip_x2 - x1]
        alpha = (crop[:, :, 3:4].astype(np.float32) / 255.0) * alpha_scale
        frame_region = frame[clip_y1:clip_y2, clip_x1:clip_x2].astype(np.float32)
        sprite_rgb = crop[:, :, :3].astype(np.float32)
        blended = sprite_rgb * alpha + frame_region * (1.0 - alpha)
        frame[clip_y1:clip_y2, clip_x1:clip_x2] = blended.astype(np.uint8)

    def tech_panel(self, frame, rect, border_color, fill=(10, 14, 24), alpha=0.84, line=2):
        x1, y1, x2, y2 = rect
        overlay = frame.copy()
        cv2.rectangle(overlay, (x1, y1), (x2, y2), fill, -1)
        cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, frame)
        cv2.rectangle(frame, (x1, y1), (x2, y2), border_color, line, cv2.LINE_AA)
        notch = 18
        cv2.line(frame, (x1, y1 + notch), (x1 + notch, y1), border_color, line, cv2.LINE_AA)
        cv2.line(frame, (x2 - notch, y2), (x2, y2 - notch), border_color, line, cv2.LINE_AA)

    def get_font(self, family, size):
        key = (family, size)
        if key not in self.font_cache:
            self.font_cache[key] = ImageFont.truetype(self.font_paths[family], size=size)
        return self.font_cache[key]

    def draw_text(self, frame, text, position, color, size=28, family="body", anchor="la", stroke=0, stroke_fill=(0, 0, 0)):
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb_frame)
        draw = ImageDraw.Draw(image)
        font = self.get_font(family, size)
        fill = (int(color[2]), int(color[1]), int(color[0]))
        draw.text(position, text, font=font, fill=fill, anchor=anchor, stroke_width=stroke, stroke_fill=(stroke_fill[2], stroke_fill[1], stroke_fill[0]))
        frame[:] = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

    def draw_text_block(self, frame, lines, x, y, size=28, family="body", color=WHITE, line_gap=8, stroke=0):
        current_y = y
        font = self.get_font(family, size)
        for text in lines:
            self.draw_text(frame, text, (x, current_y), color, size=size, family=family, stroke=stroke)
            bbox = font.getbbox(text)
            current_y += (bbox[3] - bbox[1]) + line_gap

    def current_opponent_profile(self):
        arena = self.active_arena if self.app_state == "fight" else self.current_arena_for_ui()
        return OPPONENT_ROSTER[arena["id"]]

    def glove_sprite(self, side):
        arena_id = (self.active_arena if self.app_state == "fight" else self.current_arena_for_ui())["id"]
        arena_sprite = self.assets["gloves"].get(f"{arena_id}_{side}_glove_rgba")
        if arena_sprite is not None:
            return arena_sprite
        return self.assets["gloves"].get(f"{side}_glove_rgba")

    def current_arena_for_ui(self):
        if self.app_state == "fight":
            return self.active_arena
        return CAREER_ARENAS[self.selected_arena_index]

    def arena_background(self):
        arena = self.current_arena_for_ui()
        arena_bg = self.assets["backgrounds"].get(arena["id"])
        if arena_bg is not None:
            return arena_bg
        return self.assets["backgrounds"].get("worldwide")

    def draw_arena_background(self, frame):
        h, w = frame.shape[:2]
        bg = self.resize_cover(self.arena_background(), w, h)
        if bg is not None:
            cv2.addWeighted(bg, 0.88, frame, 0.12, 0, frame)
        self.draw_gradient(frame)
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, h), (8, 10, 22), -1)
        cv2.addWeighted(overlay, 0.18, frame, 0.82, 0, frame)

    def draw_holo_grid(self, frame, step=70, color=(45, 90, 150)):
        h, w = frame.shape[:2]
        overlay = frame.copy()
        for x in range(0, w, step):
            cv2.line(overlay, (x, 0), (x, h), color, 1, cv2.LINE_AA)
        for y in range(0, h, step):
            cv2.line(overlay, (0, y), (w, y), color, 1, cv2.LINE_AA)
        cv2.addWeighted(overlay, 0.08, frame, 0.92, 0, frame)

    def reset_match(self):
        self.player_rounds = 0
        self.enemy_rounds = 0
        self.round_index = 1
        self.actions_cleared = 0
        self.match_over = False
        self.match_winner = None
        self.phase = "tutorial"
        self.tutorial_step = 0
        self.prompt = None
        self.prompt_queue.clear()
        self.enemy_block = None
        self.enemy_attack_pose = None
        self.realtime_active_attack = None
        self.realtime_action_until = 0.0
        self.realtime_next_event_at = 0.0
        self.recent_offense_families.clear()
        self.enemy_attack_flash_until = 0.0
        self.enemy_attack_flash_hand = None
        self.block_contact_until = 0.0
        self.block_contact_side = None
        self.enemy_hand_render = {"left": None, "right": None}
        self.paused = False
        self.player_recover_until = 0.0
        self.opponent_recover_until = 0.0
        self.target_prompt = None
        self.player_hp = MAX_HP
        self.enemy_hp = MAX_HP
        self.fight_player_display_max_hp = max(self.fight_player_display_max_hp, self.fight_player_max_hp)
        self.fight_enemy_display_max_hp = max(self.fight_enemy_display_max_hp, self.fight_enemy_max_hp)
        self.player_stamina = float(MAX_HP)
        self.enemy_stamina = float(MAX_HP)
        self.combo_count = 0
        self.combo_until = 0.0
        self.impact_until = 0.0
        self.impact_move_id = None
        self.power_level = "LIGHT"
        self.wrist_history["left"].clear()
        self.wrist_history["right"].clear()
        self.head_y_history.clear()
        self.round_freeze_until = time.time() + 0.5
        self.next_prompt_at = 0.0
        self.fight_intro_until = 0.0
        self.set_message("Tutorial first: perform each move once so tracking can lock in.", 2.5)
        self.match_settled = False
        self.last_payout = 0
        self.match_landed_hits = 0
        self.combo_peak = 0
        self.match_thrown_punches = 0
        self.match_taken_hits = 0
        self.match_enemy_thrown_punches = 0
        self.match_enemy_landed_hits = 0
        self.player_knockdowns = 0
        self.enemy_knockdowns = 0
        self.knockdown_state = None
        self.player_getup_meter = 0.0
        self.recent_player_moves.clear()
        self.last_player_attack_at = 0.0
        self.last_enemy_attack_at = 0.0
        self.last_energy_tick_at = time.time()

    def start_round(self, round_index):
        now = time.time()
        self.paused = False
        self.round_index = round_index
        if round_index <= 1:
            self.player_hp = self.fight_player_max_hp
            self.enemy_hp = self.fight_enemy_max_hp
        else:
            self.player_hp = min(self.fight_player_max_hp, max(0, self.player_hp) + int(round(self.fight_player_max_hp * 0.20)))
            self.enemy_hp = min(self.fight_enemy_max_hp, max(0, self.enemy_hp) + int(round(self.fight_enemy_max_hp * 0.20)))
        self.player_stamina = float(self.player_hp)
        self.enemy_stamina = float(self.enemy_hp)
        self.prompt = None
        self.prompt_queue.clear()
        self.enemy_block = None
        self.enemy_attack_pose = None
        self.target_prompt = None
        self.enemy_hand_render = {"left": None, "right": None}
        self.last_punch_at = 0.0
        self.combo_count = 0
        self.combo_until = 0.0
        self.impact_until = 0.0
        self.impact_move_id = None
        self.knockdown_state = None
        self.player_getup_meter = 0.0
        self.recent_player_moves.clear()
        self.wrist_history["left"].clear()
        self.wrist_history["right"].clear()
        self.round_freeze_until = now + ROUND_FREEZE_TIME
        self.next_prompt_at = self.round_freeze_until + 0.8
        if self.realtime_mode:
            self.phase = "realtime_round"
            self.realtime_active_attack = None
            self.realtime_action_until = 0.0
            self.realtime_next_event_at = self.round_freeze_until + 0.8
            label = f"Round {round_index}: Live Fight"
            self.set_message(f"{label}. Read the rival and react in real time.", 2.2)
        else:
            self.phase = "command_round"
            label = f"Round {round_index}: Fight"
            self.set_message(f"{label}. Follow the prompts and read the rival's guard.", 2.0)
        if round_index == 1:
            self.show_fight_help(10.0)
        self.audio.play_sfx("sfx/bell.wav", throttle=0.2)

    def active_speed_scale(self):
        arena = self.active_arena or CAREER_ARENAS[0]
        agility_bonus = max(0.84, 1.0 - (self.career.stats["agility"] - 10.0) * 0.012)
        return arena["speed_scale"] * agility_bonus

    def has_learned_core_moves(self):
        required = ["left_hook", "right_hook", "left_straight", "right_straight", "left_uppercut", "right_uppercut"]
        return all(move_id in self.learned_profiles for move_id in required)

    def enter_fight(self):
        now = time.time()
        arena = CAREER_ARENAS[self.selected_arena_index]
        self.active_arena = arena
        self.current_opponent = OPPONENT_ROSTER[arena["id"]]
        if not self.career.is_unlocked(arena["id"]):
            self.set_message(f"{arena['name']} is locked: {arena['unlock_rule']}", 2.2)
            return
        if self.career.cash < arena["entry_fee"]:
            self.set_message("Not enough cash for the entry fee.", 2.0)
            return
        self.app_state = "fight"
        self.reset_match()
        rank = self.arena_rank(arena)
        self.fight_player_max_hp = MAX_HP + int(self.career.stats["stamina"] * 0.45) + rank
        self.fight_enemy_max_hp = MAX_HP + arena["enemy_hp_bonus"] + 6 + rank * 4
        self.fight_player_display_max_hp = self.fight_player_max_hp
        self.fight_enemy_display_max_hp = self.fight_enemy_max_hp
        self.player_hp = self.fight_player_max_hp
        self.enemy_hp = self.fight_enemy_max_hp
        self.player_stamina = float(self.player_hp)
        self.enemy_stamina = float(self.enemy_hp)
        self.rounds_needed_to_win = self.rounds_required_to_win()
        self.match_settled = False
        self.phase = "tutorial" if arena["id"] == "town" else "intro"
        self.realtime_mode = self.arena_rank(arena) >= 2
        self.realtime_active_attack = None
        self.realtime_action_until = 0.0
        self.realtime_next_event_at = 0.0
        self.tutorial_step = 0
        self.tutorial_samples = {move_id: 0 for move_id in TUTORIAL_SEQUENCE}
        self.fight_intro_until = 0.0 if self.phase == "tutorial" else time.time() + 3.0
        if self.phase == "tutorial":
            self.set_message(f"{self.career.player_name or 'PLAYER'} vs {self.current_opponent['name']}. Motion capture warmup first.", 2.6)
        else:
            self.set_message(f"{self.career.player_name or 'PLAYER'} vs {self.current_opponent['name']}. Tale of the tape.", 2.2)
        self.show_fight_help(10.0)

    def start_training(self, stat_name):
        cost = self.career.train_cost(stat_name)
        if self.career.cash < cost:
            self.set_message(f"Need ${cost} to train {stat_name.title()}.", 2.0)
            return
        self.app_state = "training"
        self.training_mode = stat_name
        self.training_started_at = time.time()
        self.training_score_accum = 0.0
        self.training_samples = 0
        self.training_hits = 0
        self.training_misses = 0
        self.training_streak = 0
        self.training_prompt = None
        self.training_sequence = self.build_training_sequence(stat_name)
        self.training_combo_label = ""
        self.training_combo_moves = []
        self.training_combo_index = 0
        self.prompt = None
        self.target_prompt = None
        self.enemy_block = None
        self.enemy_attack_pose = None
        self.set_message(f"{stat_name.title()} training started. Hit the live prompts cleanly for {int(self.training_duration)} seconds.", 2.5)
        self.audio.play_sfx("sfx/bell.wav", throttle=0.2)

    def finish_training(self):
        if self.training_mode is None:
            return
        avg_score = 0.0 if self.training_samples == 0 else self.training_score_accum / self.training_samples
        previous = float(self.career.stats[self.training_mode])
        success, gain, cost = self.career.apply_training(self.training_mode, avg_score)
        if success:
            current = float(self.career.stats[self.training_mode])
            self.last_training_report = [
                f"{self.training_mode.title()} +{gain:.2f}",
                f"Value {previous:.2f} -> {current:.2f}",
                f"Hits {self.training_hits}  Misses {self.training_misses}  Best streak x{self.training_streak}",
            ]
            self.set_message(f"Training complete: {self.training_mode.title()} +{gain:.2f}. Now {current:.2f}.", 3.2)
            self.save_progress()
        else:
            self.set_message(f"Training canceled. Need ${cost}.", 2.4)
        self.training_mode = None
        self.training_prompt = None
        self.training_sequence = []
        self.training_combo_label = ""
        self.training_combo_moves = []
        self.training_combo_index = 0
        self.app_state = "locker"

    def set_message(self, text, duration=1.0):
        self.message = text
        self.message_until = time.time() + duration

    def show_fight_help(self, duration=8.0):
        self.fight_help_until = time.time() + duration

    def commit_player_name(self):
        cleaned = self.name_input.strip()[:18]
        if not cleaned:
            return False
        self.career.player_name = cleaned
        self.save_progress()
        self.app_state = "hub"
        self.set_message(f"Welcome to the card, {cleaned}.", 2.2)
        return True

    def register_offense_feedback(self, move, now, blocked=False, broke_guard=False, chip_damage=0):
        motion = self.last_detected_motion or {}
        timing_bonus = self.current_prompt_timing
        technique_key = "jab" if move["id"].endswith("straight") else "hook" if move["id"].endswith("hook") else "uppercut"
        technique_value = self.career.techniques.get(technique_key, 10.0)
        pounds = int(
            95
            + max(0.0, motion.get("planar", 0.0)) * 220
            + max(0.0, motion.get("dz", 0.0)) * 330
            + max(0.0, -motion.get("dy", 0.0)) * 200
            + max(0.0, abs(motion.get("dx", 0.0))) * 140
            + self.career.stats["power"] * 7
            + technique_value * 2.5
            + timing_bonus * 90
        )
        critical = pounds >= 285 or timing_bonus > 0.82
        damage = 1 + int(pounds >= 195) + int(pounds >= 285) + int(critical)
        if blocked and not broke_guard:
            damage = chip_damage
            critical = False
        elif broke_guard:
            damage += 1
        combo_bonus = self.combo_chain_bonus(move["id"], now)
        damage += combo_bonus
        self.enemy_hp = max(0, self.enemy_hp - damage)
        self.hit_flash_until = now + 0.18
        self.combo_count += 1
        self.combo_peak = max(self.combo_peak, self.combo_count)
        self.match_landed_hits += 1
        self.combo_until = now + 1.8
        self.impact_until = now + 0.65
        self.impact_move_id = move["id"]
        self.power_level = "HEAVY" if critical or self.combo_count >= 6 else "MEDIUM" if pounds >= 180 or self.combo_count >= 3 else "LIGHT"
        crit_text = " CRIT!" if critical else " GUARD BREAK!" if broke_guard else " BLOCKED" if blocked and damage == 0 else ""
        if combo_bonus > 0:
            crit_text += f" COMBO+{combo_bonus}"
        self.last_action_feedback = {
            "text": f"{move['label']}  {pounds} lb  -{damage} HP{crit_text}",
            "until": now + 1.2,
            "color": GOLD if critical or damage >= 3 else ORANGE if damage >= 2 else CYAN,
        }
        if blocked and damage == 0:
            self.audio.play_sfx("sfx/block.wav", throttle=0.04)
        else:
            self.audio.play_sfx("sfx/impact_heavy.wav" if damage >= 3 or broke_guard else "sfx/impact_light.wav", throttle=0.04)
        if not blocked:
            self.career.progress_technique(technique_key, 0.10)
            if broke_guard or critical:
                self.career.progress_technique("body", 0.08)
        self.recent_player_moves.append((now, move["id"]))
        return {"damage": damage, "blocked": blocked, "broke_guard": broke_guard}

    def combo_chain_bonus(self, move_id, now):
        recent = [(t, mid) for t, mid in self.recent_player_moves if now - t <= 1.6]
        if not recent:
            return 0
        families = [self.offense_family(mid) for _, mid in recent]
        current_family = self.offense_family(move_id)
        bonus = 0
        if families and families[-1] != current_family:
            bonus += 1
        if len(families) >= 2 and len(set(families[-2:] + [current_family])) >= 2:
            bonus += 1
        return min(2, bonus)

    def current_gap(self):
        speedup = 0.06 * min(self.actions_cleared, 10) + 0.12 * max(self.round_index - 1, 0)
        base_gap = max(0.50, 1.40 - speedup)
        return base_gap * self.active_speed_scale()

    def rounds_required_to_win(self):
        return 2 if self.arena_rank() < 2 else 3

    def can_throw_punch(self, side):
        cost = 1.0 if side == "player" else 0.9
        current = self.player_stamina if side == "player" else self.enemy_stamina
        return current >= cost

    def spend_stamina(self, side, amount, now):
        if side == "player":
            self.player_stamina = max(0.0, self.player_stamina - amount)
            self.last_player_attack_at = now
        else:
            self.enemy_stamina = max(0.0, self.enemy_stamina - amount)
            self.last_enemy_attack_at = now

    def update_stamina(self, now):
        dt = max(0.0, now - self.last_energy_tick_at)
        self.last_energy_tick_at = now
        if dt <= 0.0:
            return
        player_cap = max(0.0, float(self.player_hp))
        enemy_cap = max(0.0, float(self.enemy_hp))
        if now - self.last_player_attack_at > 1.0:
            self.player_stamina = min(player_cap, self.player_stamina + dt * 0.80)
        self.player_stamina = min(self.player_stamina, player_cap)
        if now - self.last_enemy_attack_at > 1.0:
            self.enemy_stamina = min(enemy_cap, self.enemy_stamina + dt * 0.72)
        self.enemy_stamina = min(self.enemy_stamina, enemy_cap)

    def realtime_gap(self):
        rank = self.arena_rank()
        base_gap = max(0.34, 0.92 - rank * 0.12)
        return base_gap * max(0.82, self.active_speed_scale())

    def arena_rank(self, arena=None):
        arena = arena or self.active_arena or CAREER_ARENAS[0]
        order = {arena["id"]: idx for idx, arena in enumerate(CAREER_ARENAS)}
        return order.get(arena["id"], 0)

    def scene_audio_key(self):
        if self.app_state == "fight":
            return f"fight:{self.active_arena['id']}"
        if self.app_state == "training":
            return "training"
        arena = self.current_arena_for_ui()
        return f"menu:{arena['id']}"

    def sync_audio_scene(self):
        key = self.scene_audio_key()
        if key == self.current_audio_key:
            return
        self.current_audio_key = key
        self.audio.stop_loop()

    def target_key_for_move(self, move_id):
        return TARGET_STYLE_BY_MOVE.get(move_id, "body_target")

    def offense_family(self, move_id):
        if move_id.endswith("hook"):
            return "hook"
        if move_id.endswith("uppercut"):
            return "uppercut"
        return "straight"

    def choose_enemy_attack(self):
        rank = self.arena_rank()
        families = ["straight"]
        if random.random() < 0.45 + rank * 0.06:
            families.append("hook")
        if rank >= 2 and random.random() < 0.48 + max(0, rank - 2) * 0.08:
            families.append("uppercut")
        family = random.choice(families)
        if family == "straight":
            attack_move_id = random.choice(["left_straight", "right_straight"])
            response = "slip_right" if attack_move_id == "left_straight" else "slip_left"
            full_defenses = [response, "guard"]
            partial_defenses = {}
            full_damage = 1 if rank < 3 else 2
        elif family == "hook":
            response = "duck"
            attack_move_id = random.choice(["left_hook", "right_hook"])
            full_defenses = ["duck"]
            partial_defenses = {"guard": 0.30}
            full_damage = 2 if rank < 4 else 3
        else:
            response = "guard"
            attack_move_id = random.choice(["left_uppercut", "right_uppercut"])
            full_defenses = []
            partial_defenses = {"guard": 0.30}
            full_damage = 2 if rank < 4 else 3
        pose = f"prep_{attack_move_id}"
        return {
            "move": MOVE_BY_ID[response],
            "attack_move_id": attack_move_id,
            "pose": pose,
            "family": family,
            "full_defenses": full_defenses,
            "partial_defenses": partial_defenses,
            "full_damage": full_damage,
        }

    def choose_enemy_block(self):
        rank = self.arena_rank()
        if rank < 2:
            return None
        weighted_styles = [("wide_gate", 0.42), ("tight_shell", 0.38), ("elbows_high", 0.14)]
        if rank >= 4:
            weighted_styles.append(("left_post", 0.18))
        styles, weights = zip(*weighted_styles)
        style = random.choices(styles, weights=weights, k=1)[0]
        rule = BLOCK_COUNTER_RULES[style]
        return {
            "style": style,
            "counter": rule["counter"],
            "counter_moves": list(rule["counter_moves"]),
            "label": rule["label"],
            "hint": rule["hint"],
        }

    def choose_predictive_block(self):
        rank = self.arena_rank()
        if rank < 4 or len(self.recent_offense_families) < 2:
            return self.choose_enemy_block()
        last_two = list(self.recent_offense_families)[-2:]
        if last_two[0] != last_two[1]:
            return self.choose_enemy_block()
        repeated = last_two[-1]
        counter_style = {
            "straight": "tight_shell",
            "hook": "wide_gate",
            "uppercut": "elbows_high",
        }.get(repeated)
        if counter_style and random.random() < 0.72:
            rule = BLOCK_COUNTER_RULES[counter_style]
            return {
                "style": counter_style,
                "counter": rule["counter"],
                "counter_moves": list(rule["counter_moves"]),
                "label": rule["label"],
                "hint": f"Rival read your pattern. {rule['hint']}",
            }
        return self.choose_enemy_block()

    def move_for_family(self, family):
        if family == "hook":
            return random.choice([MOVE_BY_ID["left_hook"], MOVE_BY_ID["right_hook"]])
        if family == "uppercut":
            return random.choice([MOVE_BY_ID["left_uppercut"], MOVE_BY_ID["right_uppercut"]])
        return random.choice([MOVE_BY_ID["left_straight"], MOVE_BY_ID["right_straight"]])

    def move_for_block(self, enemy_block):
        if not enemy_block:
            return self.move_for_family(self.offense_family(random.choice(OFFENSE_MOVES)["id"]))
        return MOVE_BY_ID[random.choice(enemy_block["counter_moves"])]

    def maybe_queue_combo(self, base_type, now):
        rank = self.arena_rank()
        combo_chance = 0.0 if rank == 0 else 0.42 + rank * 0.09
        if random.random() > combo_chance:
            return
        combo_len = 2 if rank < 3 else 3
        queued = []
        for _ in range(combo_len - 1):
            if base_type == "defense":
                attack = self.choose_enemy_attack()
                queued.append(
                    {
                        "type": "defense",
                        "move": attack["move"],
                        "enemy_attack_id": attack["attack_move_id"],
                        "enemy_attack_pose": attack["pose"],
                        "family": attack["family"],
                        "full_defenses": list(attack["full_defenses"]),
                        "partial_defenses": dict(attack["partial_defenses"]),
                        "full_damage": attack["full_damage"],
                        "issued_at": now,
                        "expires_at": now + REACTION_TIME * max(0.72, 1.0 - rank * 0.05),
                    }
                )
            else:
                enemy_block = self.choose_enemy_block() if rank >= 2 and random.random() < 0.65 else None
                move = self.move_for_block(enemy_block)
                queued.append(
                    {
                        "type": "offense",
                        "move": move,
                        "issued_at": now,
                        "expires_at": now + REACTION_TIME * max(0.72, 1.0 - rank * 0.05),
                        "enemy_block": enemy_block,
                    }
                )
        for prompt in queued:
            self.prompt_queue.append(prompt)

    def apply_offense_outcome(self, move, now):
        family = self.offense_family(move["id"])
        blocked = False
        broke_guard = False
        chip = 0
        if self.enemy_block:
            counter_moves = self.enemy_block.get("counter_moves", [])
            if move["id"] in counter_moves or family == self.enemy_block["counter"]:
                self.current_prompt_timing = min(1.0, self.current_prompt_timing + 0.18)
                broke_guard = True
            else:
                blocked = True
                chip = 1 if self.arena_rank() >= 4 and family == "straight" else 0
        outcome = self.register_offense_feedback(move, now, blocked=blocked, broke_guard=broke_guard, chip_damage=chip)
        if blocked:
            self.register_block_contact(move["hand"], now)
        self.enemy_block = None
        self.enemy_attack_pose = None
        return outcome

    def spawn_prompt(self, now):
        if self.prompt or self.match_over or now < self.round_freeze_until or now < self.next_prompt_at:
            return
        if self.prompt_queue:
            self.prompt = self.prompt_queue.popleft()
            self.prompt["issued_at"] = now
            self.prompt["expires_at"] = now + REACTION_TIME * max(0.70, 1.0 - self.arena_rank() * 0.05)
            self.enemy_block = self.prompt.get("enemy_block")
            self.enemy_attack_pose = self.enemy_block["style"] if self.enemy_block else self.prompt.get("enemy_attack_pose", self.prompt.get("enemy_attack_id"))
            if self.prompt["type"] == "defense":
                self.enemy_attack_flash_until = self.prompt["expires_at"]
                self.enemy_attack_flash_hand = "left" if self.prompt["enemy_attack_id"].startswith("left") else "right"
            return

        offense_chance = 0.64 - self.arena_rank() * 0.09
        prompt_type = "offense" if random.random() < offense_chance else "defense"
        expires_at = now + REACTION_TIME * max(0.70, 1.0 - self.arena_rank() * 0.05)
        if prompt_type == "offense":
            enemy_block = self.choose_enemy_block() if random.random() < (0.18 + self.arena_rank() * 0.10) else None
            move = self.move_for_block(enemy_block)
            self.enemy_block = enemy_block
            self.enemy_attack_pose = enemy_block["style"] if enemy_block else None
            self.prompt = {
                "type": "offense",
                "move": move,
                "issued_at": now,
                "expires_at": expires_at,
                "enemy_block": enemy_block,
            }
        else:
            attack = self.choose_enemy_attack()
            self.match_enemy_thrown_punches += 1
            self.spend_stamina("enemy", 0.9, now)
            self.enemy_block = None
            self.enemy_attack_pose = attack["pose"]
            self.enemy_attack_flash_until = expires_at
            self.enemy_attack_flash_hand = "left" if attack["attack_move_id"].startswith("left") else "right"
            self.prompt = {
                "type": "defense",
                "move": attack["move"],
                "enemy_attack_id": attack["attack_move_id"],
                "enemy_attack_pose": attack["pose"],
                "family": attack["family"],
                "full_defenses": list(attack["full_defenses"]),
                "partial_defenses": dict(attack["partial_defenses"]),
                "full_damage": attack["full_damage"],
                "issued_at": now,
                "expires_at": expires_at,
            }
        self.maybe_queue_combo(prompt_type, now)

    def build_pose_data(self, pose_landmarks, frame_w, frame_h):
        def pt(idx):
            lm = pose_landmarks.landmark[idx]
            return np.array([lm.x * frame_w, lm.y * frame_h, lm.z], dtype=np.float32), lm.visibility

        nose, nose_vis = pt(0)
        mp_l_elbow, le_vis = pt(13)
        mp_r_elbow, re_vis = pt(14)
        mp_l_shoulder, ls_vis = pt(11)
        mp_r_shoulder, rs_vis = pt(12)
        mp_l_wrist, lw_vis = pt(15)
        mp_r_wrist, rw_vis = pt(16)
        l_hip, lh_vis = pt(23)
        r_hip, rh_vis = pt(24)

        # Treat "left" and "right" as screen-space sides. This keeps punch
        # prompts aligned with the mirrored webcam view even if MediaPipe's
        # anatomical labels flip under mirrored input.
        if mp_l_shoulder[0] <= mp_r_shoulder[0]:
            l_elbow, r_elbow = mp_l_elbow, mp_r_elbow
            l_shoulder, r_shoulder = mp_l_shoulder, mp_r_shoulder
            l_wrist, r_wrist = mp_l_wrist, mp_r_wrist
        else:
            l_elbow, r_elbow = mp_r_elbow, mp_l_elbow
            l_shoulder, r_shoulder = mp_r_shoulder, mp_l_shoulder
            l_wrist, r_wrist = mp_r_wrist, mp_l_wrist

        shoulder_mid = (l_shoulder + r_shoulder) / 2.0
        hip_mid = (l_hip + r_hip) / 2.0
        shoulder_width = max(np.linalg.norm(l_shoulder[:2] - r_shoulder[:2]), 1.0)
        torso_height = max(np.linalg.norm(shoulder_mid[:2] - hip_mid[:2]), 1.0)
        return {
            "nose": nose,
            "shoulder_mid": shoulder_mid,
            "hip_mid": hip_mid,
            "l_elbow": l_elbow,
            "r_elbow": r_elbow,
            "l_shoulder": l_shoulder,
            "r_shoulder": r_shoulder,
            "l_wrist": l_wrist,
            "r_wrist": r_wrist,
            "shoulder_width": shoulder_width,
            "torso_height": torso_height,
            "min_visibility": min(nose_vis, le_vis, re_vis, ls_vis, rs_vis, lw_vis, rw_vis, lh_vis, rh_vis),
        }

    def update_wrist_memory(self, pose_data):
        now = time.time()
        self.wrist_history["left"].append((now, pose_data["l_wrist"].copy()))
        self.wrist_history["right"].append((now, pose_data["r_wrist"].copy()))

    def summarize_wrist_motion(self, hand, pose_data):
        history = self.wrist_history[hand]
        if len(history) < 5:
            return None

        times = np.array([stamp for stamp, _ in history], dtype=np.float32)
        points = np.array([point for _, point in history], dtype=np.float32)
        smoothed = points.copy()
        if len(points) >= 5:
            kernel = np.array([1.0, 2.0, 3.0, 2.0, 1.0], dtype=np.float32)
            kernel /= kernel.sum()
            for idx in range(2, len(points) - 2):
                smoothed[idx] = np.tensordot(kernel, points[idx - 2 : idx + 3], axes=(0, 0))

        start = smoothed[0]
        end = smoothed[-1]
        mid = smoothed[len(smoothed) // 2]
        shoulder_width = pose_data["shoulder_width"]
        torso_height = pose_data["torso_height"]
        dt = np.maximum(np.diff(times), 1e-3)
        delta_xy = smoothed[1:, :2] - smoothed[:-1, :2]
        segment_xy = np.linalg.norm(delta_xy, axis=1)
        path_len = float(np.sum(segment_xy) / shoulder_width)
        net_displacement = float(np.linalg.norm(end[:2] - start[:2]) / shoulder_width)
        peak_speed = float(np.max(segment_xy / shoulder_width / dt)) if len(dt) else 0.0
        mean_speed = float(path_len / max(times[-1] - times[0], 1e-3))
        pre_dx = float((mid[0] - start[0]) / shoulder_width)
        pre_dy = float((mid[1] - start[1]) / torso_height)
        dx = float((end[0] - start[0]) / shoulder_width)
        dy = float((end[1] - start[1]) / torso_height)
        dz = float(start[2] - end[2])
        mid_dz = float(mid[2] - end[2])
        late_dx = float((end[0] - mid[0]) / shoulder_width)
        late_dy = float((end[1] - mid[1]) / torso_height)
        planar = float(np.linalg.norm(end[:2] - start[:2]) / shoulder_width)
        wrist = pose_data["l_wrist"] if hand == "left" else pose_data["r_wrist"]
        shoulder = pose_data["l_shoulder"] if hand == "left" else pose_data["r_shoulder"]
        elbow = pose_data["l_elbow"] if hand == "left" else pose_data["r_elbow"]
        reach_x = float((wrist[0] - shoulder[0]) / shoulder_width)
        start_reach_x = float((start[0] - shoulder[0]) / shoulder_width)
        end_reach_x = float((end[0] - shoulder[0]) / shoulder_width)
        reach_gain = end_reach_x - start_reach_x
        elbow_to_wrist_y = float((elbow[1] - wrist[1]) / torso_height)
        wrist_to_center_x = float((wrist[0] - pose_data["shoulder_mid"][0]) / shoulder_width)
        start_hand_height = float((shoulder[1] - start[1]) / torso_height)
        end_hand_height = float((shoulder[1] - end[1]) / torso_height)
        motion_energy = float(path_len + net_displacement + abs(dz) * 0.9 + abs(dy) * 0.55)
        return {
            "pre_dx": pre_dx,
            "pre_dy": pre_dy,
            "dx": dx,
            "dy": dy,
            "dz": dz,
            "mid_dz": mid_dz,
            "late_dx": late_dx,
            "late_dy": late_dy,
            "planar": planar,
            "reach_x": reach_x,
            "start_reach_x": start_reach_x,
            "end_reach_x": end_reach_x,
            "reach_gain": reach_gain,
            "elbow_to_wrist_y": elbow_to_wrist_y,
            "wrist_to_center_x": wrist_to_center_x,
            "start_hand_height": start_hand_height,
            "end_hand_height": end_hand_height,
            "path_len": path_len,
            "net_displacement": net_displacement,
            "peak_speed": peak_speed,
            "mean_speed": mean_speed,
            "motion_energy": motion_energy,
        }

    def motion_is_active(self, motion, strict=False):
        if not motion:
            return False
        min_path = 0.22 if strict else 0.16
        min_displacement = 0.17 if strict else 0.13
        min_peak_speed = 1.95 if strict else 1.34
        min_energy = 0.46 if strict else 0.31
        return (
            motion["path_len"] >= min_path
            and motion["net_displacement"] >= min_displacement
            and motion["peak_speed"] >= min_peak_speed
            and motion["motion_energy"] >= min_energy
        )

    def guard_lane_active(self, pose_data):
        shoulder_mid = pose_data["shoulder_mid"]
        shoulder_width = pose_data["shoulder_width"]
        torso_height = pose_data["torso_height"]
        left_dx = abs(float((pose_data["l_wrist"][0] - shoulder_mid[0]) / shoulder_width))
        right_dx = abs(float((pose_data["r_wrist"][0] - shoulder_mid[0]) / shoulder_width))
        left_dy = float((pose_data["l_wrist"][1] - shoulder_mid[1]) / torso_height)
        right_dy = float((pose_data["r_wrist"][1] - shoulder_mid[1]) / torso_height)
        return (
            left_dx < 0.34
            and right_dx < 0.34
            and -0.20 < left_dy < 0.42
            and -0.20 < right_dy < 0.42
        )

    def defense_state(self, pose_data):
        nose = pose_data["nose"]
        shoulder_mid = pose_data["shoulder_mid"]
        shoulder_width = pose_data["shoulder_width"]
        l_wrist = pose_data["l_wrist"]
        r_wrist = pose_data["r_wrist"]

        guard_radius = shoulder_width * 0.42
        left_near = np.linalg.norm(l_wrist[:2] - nose[:2]) < guard_radius
        right_near = np.linalg.norm(r_wrist[:2] - nose[:2]) < guard_radius
        hands_high = l_wrist[1] < shoulder_mid[1] + shoulder_width * 0.08 and r_wrist[1] < shoulder_mid[1] + shoulder_width * 0.08
        guard_active = left_near and right_near and hands_high

        lean_ratio = float((nose[0] - shoulder_mid[0]) / shoulder_width)
        baseline_y = min(self.head_y_history) if len(self.head_y_history) > 10 else nose[1]
        duck = (nose[1] - baseline_y) > shoulder_width * 0.35
        return {
            "guard": guard_active,
            "slip_left": lean_ratio < -0.18,
            "slip_right": lean_ratio > 0.18,
            "duck": duck,
            "lean_ratio": lean_ratio,
        }

    def detect_offense_move(self, move_id, pose_data, strict=False):
        move = MOVE_BY_ID[move_id]
        if strict:
            defense = self.defense_state(pose_data)
            if defense["guard"] or defense["slip_left"] or defense["slip_right"] or defense["duck"]:
                return False
        motion = self.summarize_wrist_motion(move["hand"], pose_data)
        if motion is None or not self.motion_is_active(motion, strict=strict):
            return False
        if strict and self.guard_lane_active(pose_data) and motion["reach_x"] < 0.14 and motion["planar"] < 0.40:
            return False

        wrist = pose_data["l_wrist"] if move["hand"] == "left" else pose_data["r_wrist"]
        shoulder = pose_data["l_shoulder"] if move["hand"] == "left" else pose_data["r_shoulder"]
        hook_dx = 0.22 if strict else 0.18
        hook_late_dx = 0.09 if strict else 0.07
        hook_planar = 0.28 if strict else 0.22
        straight_dz = 0.076 if strict else 0.060
        straight_mid_dz = 0.036 if strict else 0.027
        straight_reach = 0.10 if strict else 0.07
        uppercut_dy = -0.16 if strict else -0.12

        if move_id.endswith("hook"):
            direction_ok = motion["dx"] > hook_dx if move["hand"] == "left" else motion["dx"] < -hook_dx
            late_direction_ok = motion["late_dx"] > hook_late_dx if move["hand"] == "left" else motion["late_dx"] < -hook_late_dx
            recoil_ok = motion["pre_dx"] < -0.035 if move["hand"] == "left" else motion["pre_dx"] > 0.035
            matched = (
                direction_ok
                and late_direction_ok
                and abs(motion["dx"]) > abs(motion["dy"]) * 1.15
                and motion["planar"] > hook_planar
                and abs(motion["wrist_to_center_x"]) > (0.36 if strict else 0.28)
                and (recoil_ok or abs(motion["dx"]) > hook_dx * 1.35)
            )
            if matched:
                self.last_detected_motion = motion
            return matched

        if move_id.endswith("straight"):
            reach_ok = motion["reach_x"] > straight_reach if move["hand"] == "left" else motion["reach_x"] < -straight_reach
            reach_gain_ok = motion["reach_gain"] > 0.10 if move["hand"] == "left" else motion["reach_gain"] < -0.10
            straight_score = 0
            if motion["dz"] > straight_dz:
                straight_score += 1
            if motion["mid_dz"] > straight_mid_dz:
                straight_score += 1
            if reach_ok:
                straight_score += 1
            if reach_gain_ok:
                straight_score += 1
            if abs(motion["dx"]) < 0.24 and abs(motion["dy"]) < 0.28:
                straight_score += 1
            if motion["planar"] < 0.46:
                straight_score += 1
            if abs(motion["wrist_to_center_x"]) > (0.22 if strict else 0.18):
                straight_score += 1
            matched = straight_score >= 4 and (not strict or ((motion["dz"] > straight_dz) and reach_gain_ok and profile_match(move_id, motion, self.learned_profiles.get(move_id))))
            if matched:
                self.last_detected_motion = motion
            return matched

        if move_id.endswith("uppercut"):
            current_uppercut_dy = uppercut_dy
            current_height_gain = 0.08
            current_center_limit = 0.42
            if move_id == "left_uppercut":
                current_uppercut_dy += 0.035
                current_height_gain = 0.04
                current_center_limit = 0.54

            pre_dip_ok = motion["pre_dy"] > 0.035
            if motion["dy"] >= current_uppercut_dy:
                return False
            if motion["late_dy"] >= current_uppercut_dy * 0.72:
                return False
            if motion["end_hand_height"] <= motion["start_hand_height"] + current_height_gain:
                return False

            uppercut_score = 2 + int(pre_dip_ok)
            if abs(motion["dy"]) > abs(motion["dx"]) * 0.72:
                uppercut_score += 1
            if motion["elbow_to_wrist_y"] > 0.03:
                uppercut_score += 1
            if abs(motion["wrist_to_center_x"]) < current_center_limit:
                uppercut_score += 1
            if wrist[1] < shoulder[1] + pose_data["torso_height"] * 0.34:
                uppercut_score += 1
            if motion["planar"] > (0.18 if strict else 0.14):
                uppercut_score += 1
            matched = uppercut_score >= 4 and (not strict or profile_match(move_id, motion, self.learned_profiles.get(move_id)))
            if matched:
                self.last_detected_motion = motion
            return matched

        return False

    def detect_target_hit(self, pose_data, prompt):
        move_id = prompt["move_id"]
        if not self.detect_offense_move(move_id, pose_data, strict=True):
            return False

        hand = MOVE_BY_ID[move_id]["hand"]
        self.wrist_history[hand].clear()
        return True

    def detect_capture_motion(self, move_id, pose_data):
        move = MOVE_BY_ID[move_id]
        if move.get("hand") is None:
            return self.defense_success(self.defense_state(pose_data), move_id)
            
        motion = self.summarize_wrist_motion(move["hand"], pose_data)
        if motion is None or not self.motion_is_active(motion, strict=False):
            return False

        if move_id.endswith("hook"):
            direction_ok = motion["dx"] > 0.11 if move["hand"] == "left" else motion["dx"] < -0.11
            recoil_ok = motion["pre_dx"] < -0.02 if move["hand"] == "left" else motion["pre_dx"] > 0.02
            matched = direction_ok and motion["planar"] > 0.14 and (recoil_ok or abs(motion["dx"]) > 0.18)
            if matched:
                self.last_detected_motion = motion
            return matched

        if move_id.endswith("straight"):
            reach_ok = motion["reach_x"] > 0.05 if move["hand"] == "left" else motion["reach_x"] < -0.05
            matched = motion["dz"] > 0.04 and motion["mid_dz"] > 0.015 and reach_ok
            if matched:
                self.last_detected_motion = motion
            return matched

        if move_id.endswith("uppercut"):
            matched = (
                motion["pre_dy"] > 0.02
                and motion["dy"] < -0.07
                and motion["late_dy"] < -0.03
                and motion["end_hand_height"] > motion["start_hand_height"] + 0.02
            )
            if matched:
                self.last_detected_motion = motion
            return matched

        return self.defense_success(self.defense_state(pose_data), move_id)

    def detect_menu_move(self, move_id, pose_data):
        if move_id in ("left_hook", "right_hook", "left_uppercut", "right_uppercut"):
            return self.detect_capture_motion(move_id, pose_data) or self.detect_offense_move(move_id, pose_data, strict=False)
        return self.detect_offense_move(move_id, pose_data, strict=False)

    def defense_success(self, defense, move_id):
        return defense.get(move_id, False)

    def trigger_menu_feedback(self, text, color, now):
        self.last_action_feedback = {"text": text, "until": now + 0.8, "color": color}

    def handle_menu_gestures(self, pose_data, defense, now):
        if now < self.menu_action_cooldown_until:
            return

        if self.app_state == "fight" and self.match_over:
            if self.detect_menu_move("right_uppercut", pose_data):
                self.menu_action_cooldown_until = now + 0.85
                self.app_state = "arena_map"
                self.trigger_menu_feedback("BACK TO MAP", GOLD, now)
                return
            if self.detect_menu_move("left_uppercut", pose_data):
                self.menu_action_cooldown_until = now + 0.85
                self.enter_fight()
                self.trigger_menu_feedback("REMATCH", RED, now)
                return

        if defense["slip_left"]:
            if self.app_state == "hub":
                self.selected_hub_index = max(0, self.selected_hub_index - 1)
            elif self.app_state == "arena_map":
                self.selected_arena_index = max(0, self.selected_arena_index - 1)
            elif self.app_state == "training_menu":
                self.selected_training_index = max(0, self.selected_training_index - 1)
            self.menu_action_cooldown_until = now + 0.7
            self.trigger_menu_feedback("MOVE LEFT", CYAN, now)
            self.audio.play_sfx("sfx/menu.wav", throttle=0.05)
            return

        if defense["slip_right"]:
            if self.app_state == "hub":
                self.selected_hub_index = min(len(HUB_MENU) - 1, self.selected_hub_index + 1)
            elif self.app_state == "arena_map":
                self.selected_arena_index = min(len(CAREER_ARENAS) - 1, self.selected_arena_index + 1)
            elif self.app_state == "training_menu":
                self.selected_training_index = min(len(TRAINING_MENU) - 1, self.selected_training_index + 1)
            self.menu_action_cooldown_until = now + 0.7
            self.trigger_menu_feedback("MOVE RIGHT", CYAN, now)
            self.audio.play_sfx("sfx/menu.wav", throttle=0.05)
            return

        if self.detect_menu_move("left_uppercut", pose_data):
            self.menu_action_cooldown_until = now + 0.85
            self.trigger_menu_feedback("CONFIRM", GOLD, now)
            self.audio.play_sfx("sfx/menu.wav", throttle=0.05)
            self.handle_menu_confirm()
            return

        if self.detect_menu_move("right_uppercut", pose_data):
            self.menu_action_cooldown_until = now + 0.85
            self.trigger_menu_feedback("BACK", RED, now)
            self.audio.play_sfx("sfx/menu.wav", throttle=0.05)
            self.handle_menu_back()

    def handle_menu_confirm(self):
        if self.app_state == "hub":
            target = HUB_MENU[self.selected_hub_index]
            if target == "Fight":
                self.app_state = "arena_map"
            elif target == "Locker":
                self.app_state = "locker"
            elif target == "Training":
                self.app_state = "training_menu"
            return

        if self.app_state == "arena_map":
            self.enter_fight()
            return

        if self.app_state == "training_menu":
            selected = TRAINING_MENU[self.selected_training_index].lower()
            self.start_training(selected)

    def handle_menu_back(self):
        if self.app_state in ("arena_map", "locker", "training_menu"):
            self.app_state = "hub"
        elif self.app_state == "training":
            self.finish_training()

    def complete_tutorial_step(self):
        move_id = TUTORIAL_SEQUENCE[self.tutorial_step]
        target_reps = tutorial_rep_target(move_id)
        self.tutorial_samples[move_id] = self.tutorial_samples.get(move_id, 0) + 1
        if move_id not in ("guard", "slip_left", "slip_right") and self.last_detected_motion:
            self.learned_profiles[move_id] = merge_motion_profile(self.learned_profiles.get(move_id), self.last_detected_motion)
            self.save_progress()
        current_rep = self.tutorial_samples[move_id]
        if current_rep < target_reps:
            self.set_message(f"{MOVE_BY_ID[move_id]['label']} capture {current_rep}/{target_reps}. Hold the pattern and repeat.", 1.2)
            self.wrist_history["left"].clear()
            self.wrist_history["right"].clear()
            return
        self.set_message(f"{MOVE_BY_ID[move_id]['label']} profile locked in.", 1.0)
        self.tutorial_step += 1
        self.wrist_history["left"].clear()
        self.wrist_history["right"].clear()
        self.last_detected_motion = None
        if self.tutorial_step >= len(TUTORIAL_SEQUENCE):
            self.save_progress()
            self.phase = "intro"
            self.fight_intro_until = time.time() + 3.0
            self.set_message("Tutorial complete. Tale of the tape.", 1.6)

    def run_tutorial(self, pose_data, defense, now):
        if self.tutorial_step >= len(TUTORIAL_SEQUENCE):
            return
        move_id = TUTORIAL_SEQUENCE[self.tutorial_step]
        if move_id in ("guard", "slip_left", "slip_right"):
            if self.defense_success(defense, move_id):
                self.complete_tutorial_step()
            elif self.prompt is None:
                self.prompt = {"type": "tutorial", "move": MOVE_BY_ID[move_id], "issued_at": now, "expires_at": now + TUTORIAL_WINDOW}
        else:
            if self.detect_capture_motion(move_id, pose_data) and now - self.last_punch_at > PUNCH_COOLDOWN:
                self.last_punch_at = now
                self.complete_tutorial_step()
            elif self.prompt is None:
                self.prompt = {"type": "tutorial", "move": MOVE_BY_ID[move_id], "issued_at": now, "expires_at": now + TUTORIAL_WINDOW}

    def resolve_command_success(self, move, is_defense, now):
        if is_defense:
            chip = self.prompt.get("chip_on_block", 0) if self.prompt else 0
            if chip:
                self.player_hp = max(0, self.player_hp - chip)
                self.damage_flash_until = now + 0.12
                self.match_taken_hits += 1
                self.match_enemy_landed_hits += 1
                self.set_message(f"{move['label']} saved you, but the shot still pressured you for {chip} HP.", 1.0)
                self.audio.play_sfx("sfx/impact_light.wav", throttle=0.05)
            else:
                self.set_message(f"{move['label']} successful.", 0.85)
            self.audio.play_sfx("sfx/block.wav", throttle=0.05)
            self.enemy_attack_pose = None
            self.enemy_attack_flash_until = 0.0
            self.enemy_attack_flash_hand = None
        else:
            outcome = self.apply_offense_outcome(move, now)
            if outcome["broke_guard"]:
                self.set_message(f"{move['label']} broke the guard and landed clean.", 1.0)
            elif outcome["blocked"] and outcome["damage"] == 0:
                self.set_message("Wrong angle. The rival's guard absorbed that shot.", 1.0)
            else:
                self.set_message(f"{move['label']} landed. Rival loses {outcome['damage']} HP.", 0.9)
        self.actions_cleared += 1
        self.prompt = None
        self.next_prompt_at = now + self.current_gap()

    def evaluate_defense_prompt(self, defense, prompt):
        if not prompt or prompt.get("type") != "defense":
            return None
        family = prompt.get("family")
        if family is None:
            attack_id = prompt.get("enemy_attack_id", "")
            family = "uppercut" if attack_id.endswith("uppercut") else "hook" if attack_id.endswith("hook") else "straight"
        for move_id in prompt.get("full_defenses", []):
            if defense.get(move_id, False):
                return {"blocked": True, "chip": 0, "move_id": move_id}
        for move_id, reduction in prompt.get("partial_defenses", {}).items():
            if defense.get(move_id, False):
                damage = max(1, int(round(prompt.get("full_damage", 2) * (1.0 - reduction))))
                return {"blocked": True, "chip": damage, "move_id": move_id}
        return None

    def register_block_contact(self, side, now):
        self.block_contact_side = side
        self.block_contact_until = now + 0.22

    def start_knockdown(self, fighter, now):
        is_player = fighter == "player"
        if is_player:
            self.player_knockdowns += 1
            self.player_hp = 0
            self.player_stamina = 0.0
        else:
            self.enemy_knockdowns += 1
            self.enemy_hp = 0
            self.enemy_stamina = 0.0
        self.knockdown_state = {
            "fighter": fighter,
            "started_at": now,
            "countdown_end": now + 8.0,
            "combo_snapshot": self.combo_count,
            "rise_roll": random.random(),
        }
        self.prompt = None
        self.enemy_block = None
        self.enemy_attack_pose = None
        self.enemy_attack_flash_until = 0.0
        self.enemy_attack_flash_hand = None
        self.combo_count = 0
        self.set_message(f"{fighter.upper()} DOWN. Beat the count.", 1.2)

    def knockdown_rise_chance(self, fighter):
        if fighter == "opponent":
            kd_count = self.enemy_knockdowns
            stamina_ratio = self.enemy_stamina / max(1.0, float(self.fight_enemy_max_hp))
            combo_penalty = min(0.26, self.knockdown_state["combo_snapshot"] * 0.04)
            chance = 0.88 - kd_count * 0.18 - combo_penalty + stamina_ratio * 0.14
            return max(0.08, min(0.92, chance))
        kd_count = self.player_knockdowns
        meter_bonus = min(0.34, self.player_getup_meter * 0.40)
        chance = 0.76 - kd_count * 0.16 + meter_bonus
        return max(0.10, min(0.90, chance))

    def resolve_knockdown(self, now):
        if not self.knockdown_state or now < self.knockdown_state["countdown_end"]:
            return
        fighter = self.knockdown_state["fighter"]
        chance = self.knockdown_rise_chance(fighter)
        roll = self.knockdown_state["rise_roll"]
        down_count = self.player_knockdowns if fighter == "player" else self.enemy_knockdowns
        auto_fail = down_count >= 3
        if fighter == "player":
            auto_fail = auto_fail or (down_count >= 2 and self.player_getup_meter < 0.24)
        else:
            auto_fail = auto_fail or (down_count >= 2 and self.knockdown_state["combo_snapshot"] >= 5 and roll > chance * 0.92)

        if not auto_fail and roll <= chance:
            if fighter == "player":
                self.fight_player_max_hp = max(4, int(round(self.fight_player_max_hp * 0.8)))
                restore_cap = self.fight_player_max_hp
            else:
                self.fight_enemy_max_hp = max(4, int(round(self.fight_enemy_max_hp * 0.8)))
                restore_cap = self.fight_enemy_max_hp
            restore_hp = min(restore_cap, 5 + max(0, 2 - down_count))
            restore_stamina = 3 + max(0, 2 - down_count)
            if fighter == "player":
                self.player_hp = min(self.fight_player_max_hp, restore_hp)
                self.player_stamina = min(float(self.player_hp), float(restore_stamina))
                self.player_recover_until = now + 2.4
                self.set_message(f"{self.career.player_name or 'PLAYER'} beats the count at {down_count}.", 2.0)
            else:
                self.enemy_hp = min(self.fight_enemy_max_hp, restore_hp)
                self.enemy_stamina = min(float(self.enemy_hp), float(restore_stamina))
                self.opponent_recover_until = now + 2.4
                self.set_message(f"{self.current_opponent_profile()['name']} rises at {down_count}.", 2.0)
            self.round_freeze_until = now + 3.0 + down_count * 0.7
            self.prompt = None
            self.enemy_block = None
            self.enemy_attack_pose = None
            self.knockdown_state = None
            self.player_getup_meter = 0.0
            return

        if fighter == "player":
            self.player_rounds = self.player_rounds
            self.enemy_rounds += 1
            self.knockdown_state = None
            self.player_getup_meter = 0.0
            if self.enemy_rounds >= self.rounds_needed_to_win:
                self.match_over = True
                self.match_winner = "OPPONENT"
                self.last_payout = self.career.apply_match_result(
                    self.active_arena,
                    False,
                    self.match_landed_hits,
                    self.combo_peak,
                    0.0,
                    result_detail="TKO LOSS",
                    opponent_name=self.current_opponent_profile()["name"],
                )
                self.save_progress()
                self.match_settled = True
                self.set_message("Opponent wins after the count. Entry fee and upkeep charged.", 8.0)
                self.audio.play_sfx("sfx/cheer.wav", throttle=0.2)
            else:
                self.start_round(self.round_index + 1)
        else:
            self.player_rounds += 1
            self.knockdown_state = None
            if self.player_rounds >= self.rounds_needed_to_win:
                self.match_over = True
                self.match_winner = "PLAYER"
                self.last_payout = self.career.apply_match_result(
                    self.active_arena,
                    True,
                    self.match_landed_hits,
                    self.combo_peak,
                    max(self.player_hp, 0) / max(1, self.fight_player_max_hp),
                    result_detail="TKO WIN",
                    opponent_name=self.current_opponent_profile()["name"],
                )
                self.save_progress()
                self.match_settled = True
                self.set_message(f"You win after the count. Payout ${self.last_payout}.", 8.0)
                self.audio.play_sfx("sfx/cheer.wav", throttle=0.2)
            else:
                self.start_round(self.round_index + 1)

    def resolve_target_success(self, now):
        move = MOVE_BY_ID[self.target_prompt["move_id"]]
        outcome = self.register_offense_feedback(move, now)
        self.set_message(f"{move['label']} hit the target. Rival loses {outcome['damage']} HP.", 0.9)
        self.actions_cleared += 1
        self.target_prompt = None
        self.next_prompt_at = now + self.current_gap()

    def resolve_timeout(self, now):
        if self.phase == "command_round" and self.prompt:
            move = self.prompt["move"]
            if self.prompt["type"] == "defense":
                penalty = self.prompt.get("full_damage", 2 if self.prompt.get("enemy_attack_id", "").endswith("uppercut") or self.arena_rank() >= 3 else 1)
                self.player_hp = max(0, self.player_hp - penalty)
                self.damage_flash_until = now + 0.22
                self.match_taken_hits += 1
                self.match_enemy_landed_hits += 1
                attack_name = MOVE_BY_ID.get(self.prompt.get("enemy_attack_id", ""), {}).get("label", "RIVAL STRIKE")
                self.set_message(f"Too slow. {attack_name} cracked through for {penalty} HP.", 1.0)
                self.audio.play_sfx("sfx/impact_heavy.wav", throttle=0.05)
            else:
                if self.enemy_block:
                    self.set_message(f"Missed {move['label']}. {self.enemy_block['hint']}", 1.0)
                else:
                    self.set_message(f"Missed {move['label']}. Match the punch direction next time.", 1.0)
                self.audio.play_sfx("sfx/whoosh.wav", throttle=0.04)
            self.combo_count = 0
            self.enemy_attack_pose = None
            self.enemy_attack_flash_until = 0.0
            self.enemy_attack_flash_hand = None
            self.enemy_block = None
            self.prompt = None
            self.next_prompt_at = now + self.current_gap()
        elif self.phase == "target_round" and self.target_prompt:
            move = MOVE_BY_ID[self.target_prompt["move_id"]]
            self.set_message(f"Missed target for {move['label']}.", 1.0)
            self.audio.play_sfx("sfx/whoosh.wav", throttle=0.04)
            self.combo_count = 0
            self.target_prompt = None
            self.next_prompt_at = now + self.current_gap()

    def process_command_round(self, pose_data, defense, now):
        self.spawn_prompt(now)
        if not self.prompt:
            return
        move = self.prompt["move"]
        if self.prompt["type"] == "offense":
            prompt_strict = True
            if now - self.last_punch_at > PUNCH_COOLDOWN and self.can_throw_punch("player") and self.detect_offense_move(move["id"], pose_data, strict=prompt_strict):
                self.match_thrown_punches += 1
                self.spend_stamina("player", 1.0, now)
                duration = max(0.001, self.prompt["expires_at"] - self.prompt["issued_at"])
                self.current_prompt_timing = max(0.0, min(1.0, 1.0 - ((self.prompt["expires_at"] - now) / duration)))
                self.last_punch_at = now
                self.wrist_history[move["hand"]].clear()
                self.resolve_command_success(move, False, now)
                return
            if self.prompt.get("enemy_block") and now - self.last_punch_at > PUNCH_COOLDOWN and self.can_throw_punch("player"):
                for alt_move_id in self.prompt["enemy_block"].get("counter_moves", []):
                    if alt_move_id != move["id"] and self.detect_offense_move(alt_move_id, pose_data, strict=True):
                        self.match_thrown_punches += 1
                        self.spend_stamina("player", 1.0, now)
                        alt_move = MOVE_BY_ID[alt_move_id]
                        duration = max(0.001, self.prompt["expires_at"] - self.prompt["issued_at"])
                        self.current_prompt_timing = max(0.0, min(1.0, 1.0 - ((self.prompt["expires_at"] - now) / duration)))
                        self.last_punch_at = now
                        self.wrist_history[alt_move["hand"]].clear()
                        self.resolve_command_success(alt_move, False, now)
                        return
        else:
            defense_result = self.evaluate_defense_prompt(defense, self.prompt)
            if defense_result:
                blocked_move = MOVE_BY_ID[defense_result["move_id"]]
                duration = max(0.001, self.prompt["expires_at"] - self.prompt["issued_at"])
                timing = max(0.0, min(1.0, 1.0 - ((self.prompt["expires_at"] - now) / duration)))
                self.last_action_feedback = {
                    "text": f"{blocked_move['label']} vs {MOVE_BY_ID[self.prompt['enemy_attack_id']]['label']}  REACTION {int(100 + timing * 220)}",
                    "until": now + 1.0,
                    "color": GREEN if defense_result["chip"] == 0 else ORANGE,
                }
                self.prompt["chip_on_block"] = defense_result["chip"]
                self.register_block_contact("left" if self.prompt["enemy_attack_id"].startswith("left") else "right", now)
                self.resolve_command_success(blocked_move, True, now)
                return

        if now >= self.prompt["expires_at"]:
            self.resolve_timeout(now)

    def spawn_realtime_event(self, now):
        rank = self.arena_rank()
        attack_bias = 0.62 + max(0, rank - 2) * 0.10
        if self.enemy_block is None and self.realtime_active_attack is None and random.random() < attack_bias:
            attack = self.choose_enemy_attack()
            self.match_enemy_thrown_punches += 1
            self.spend_stamina("enemy", 0.9, now)
            expires_at = now + max(0.72, 1.08 - max(0, rank - 3) * 0.08)
            self.realtime_active_attack = {
                "move": attack["move"],
                "enemy_attack_id": attack["attack_move_id"],
                "pose": attack["pose"],
                "family": attack["family"],
                "full_defenses": list(attack["full_defenses"]),
                "partial_defenses": dict(attack["partial_defenses"]),
                "full_damage": attack["full_damage"],
                "issued_at": now,
                "expires_at": expires_at,
            }
            self.enemy_attack_pose = attack["pose"]
            self.enemy_attack_flash_until = expires_at
            self.enemy_attack_flash_hand = "left" if attack["attack_move_id"].startswith("left") else "right"
            self.prompt = {
                "type": "defense",
                "move": attack["move"],
                "enemy_attack_id": attack["attack_move_id"],
                "family": attack["family"],
                "full_defenses": list(attack["full_defenses"]),
                "partial_defenses": dict(attack["partial_defenses"]),
                "full_damage": attack["full_damage"],
                "issued_at": now,
                "expires_at": expires_at,
            }
        else:
            enemy_block = self.choose_predictive_block() or self.choose_enemy_block()
            if enemy_block is None:
                return
            expires_at = now + max(0.82, 1.20 - max(0, rank - 3) * 0.08)
            self.enemy_block = enemy_block
            self.enemy_attack_pose = enemy_block["style"]
            self.prompt = {
                "type": "offense",
                "move": self.move_for_block(enemy_block),
                "issued_at": now,
                "expires_at": expires_at,
                "enemy_block": enemy_block,
            }
        self.realtime_next_event_at = now + self.realtime_gap()

    def process_realtime_round(self, pose_data, defense, now):
        if now < self.round_freeze_until:
            return

        defense_result = self.evaluate_defense_prompt(defense, self.realtime_active_attack)
        if self.realtime_active_attack and defense_result:
            move = MOVE_BY_ID[defense_result["move_id"]]
            self.last_action_feedback = {
                "text": f"{move['label']} read clean on {MOVE_BY_ID[self.realtime_active_attack['enemy_attack_id']]['label']}",
                "until": now + 1.0,
                "color": GREEN if defense_result["chip"] == 0 else ORANGE,
            }
            self.prompt["chip_on_block"] = defense_result["chip"]
            self.register_block_contact("left" if self.realtime_active_attack["enemy_attack_id"].startswith("left") else "right", now)
            self.resolve_command_success(move, True, now)
            self.realtime_active_attack = None
            self.realtime_next_event_at = now + 0.34
            return

        if self.enemy_block and self.prompt and self.prompt["type"] == "offense" and now - self.last_punch_at > PUNCH_COOLDOWN and self.can_throw_punch("player"):
            valid_moves = list(self.enemy_block.get("counter_moves", []))
            for move_id in valid_moves:
                if self.detect_offense_move(move_id, pose_data, strict=True):
                    move = MOVE_BY_ID[move_id]
                    self.match_thrown_punches += 1
                    self.spend_stamina("player", 1.0, now)
                    self.current_prompt_timing = 0.74
                    self.last_punch_at = now
                    self.wrist_history[move["hand"]].clear()
                    self.recent_offense_families.append(self.offense_family(move_id))
                    self.resolve_command_success(move, False, now)
                    self.realtime_next_event_at = now + 0.26
                    return

        if self.enemy_block is None and self.realtime_active_attack is None and now - self.last_punch_at > PUNCH_COOLDOWN and self.can_throw_punch("player"):
            for move in OFFENSE_MOVES:
                if self.detect_offense_move(move["id"], pose_data, strict=True):
                    self.match_thrown_punches += 1
                    self.spend_stamina("player", 1.0, now)
                    self.current_prompt_timing = 0.58
                    self.last_punch_at = now
                    self.wrist_history[move["hand"]].clear()
                    self.recent_offense_families.append(self.offense_family(move["id"]))
                    outcome = self.register_offense_feedback(move, now, blocked=False, broke_guard=False, chip_damage=0)
                    self.set_message(f"{move['label']} snapped through for {outcome['damage']} HP.", 0.7)
                    self.last_action_feedback = {
                        "text": f"{move['label']} found space in live flow",
                        "until": now + 0.9,
                        "color": CYAN,
                    }
                    self.realtime_next_event_at = now + 0.18
                    return

        if self.realtime_active_attack and now >= self.realtime_active_attack["expires_at"]:
            attack_prompt = self.realtime_active_attack
            penalty = attack_prompt.get("full_damage", 2)
            self.player_hp = max(0, self.player_hp - penalty)
            self.damage_flash_until = now + 0.22
            self.match_taken_hits += 1
            self.match_enemy_landed_hits += 1
            attack_name = MOVE_BY_ID.get(attack_prompt.get("enemy_attack_id", ""), {}).get("label", "RIVAL STRIKE")
            self.set_message(f"{attack_name} landed clean for {penalty} HP.", 0.9)
            self.audio.play_sfx("sfx/impact_heavy.wav", throttle=0.05)
            self.combo_count = 0
            self.realtime_active_attack = None
            self.enemy_attack_pose = None
            self.enemy_attack_flash_until = 0.0
            self.enemy_attack_flash_hand = None
            self.prompt = None
            self.realtime_next_event_at = now + 0.32
            return

        if self.enemy_block and self.prompt and now >= self.prompt["expires_at"]:
            self.set_message(f"Opening closed. {self.enemy_block['hint']}", 0.8)
            self.enemy_block = None
            self.enemy_attack_pose = None
            self.prompt = None
            self.realtime_next_event_at = now + 0.24
            return

        if self.enemy_block is None and self.realtime_active_attack is None and now >= self.realtime_next_event_at:
            self.spawn_realtime_event(now)

    def build_target_prompt(self, frame_w, frame_h):
        move = random.choice(OFFENSE_MOVES)
        target_key = self.target_key_for_move(move["id"])
        if move["id"].endswith("straight"):
            size = int(min(frame_w, frame_h) * 0.18)
            margin_x = int(frame_w * 0.30)
            margin_y = int(frame_h * 0.34)
            cx = random.choice([margin_x, frame_w - margin_x])
            cy = random.choice([margin_y, frame_h - margin_y])
            rect = (cx - size // 2, cy - size // 2, cx + size // 2, cy + size // 2)
            shape = "circle"
        elif move["id"].endswith("hook"):
            grid_x = [int(frame_w * 0.30), int(frame_w * 0.50), int(frame_w * 0.70)]
            grid_y = [int(frame_h * 0.34), int(frame_h * 0.52), int(frame_h * 0.70)]
            cx = random.choice(grid_x)
            cy = random.choice(grid_y)
            rect = (cx - 125, cy - 36, cx + 125, cy + 36)
            shape = "horizontal"
        else:
            cx = int(frame_w * 0.34) if move["hand"] == "left" else int(frame_w * 0.66)
            cy = random.choice([int(frame_h * 0.40), int(frame_h * 0.56), int(frame_h * 0.70)])
            rect = (cx - 42, cy - 120, cx + 42, cy + 120)
            shape = "vertical"
        return {
            "move_id": move["id"],
            "shape": shape,
            "target_key": target_key,
            "rect": rect,
            "expires_at": time.time() + REACTION_TIME,
        }

    def process_target_round(self, pose_data, now, frame_w, frame_h):
        if self.target_prompt is None and now >= self.next_prompt_at and now >= self.round_freeze_until:
            self.target_prompt = self.build_target_prompt(frame_w, frame_h)

        if self.target_prompt is None:
            return

        if now - self.last_punch_at > PUNCH_COOLDOWN and self.can_throw_punch("player") and self.detect_target_hit(pose_data, self.target_prompt):
            self.current_prompt_timing = 0.5
            self.spend_stamina("player", 1.0, now)
            self.last_punch_at = now
            self.resolve_target_success(now)
            return

        if now >= self.target_prompt["expires_at"]:
            self.resolve_timeout(now)

    def build_training_sequence(self, stat_name):
        if stat_name == "power":
            return [
                {"type": "combo", "moves": ["left_straight", "right_hook", "left_uppercut"], "label": "LEFT STRAIGHT > RIGHT HOOK > LEFT UPPERCUT"},
                {"type": "combo", "moves": ["right_straight", "left_hook", "right_uppercut"], "label": "RIGHT STRAIGHT > LEFT HOOK > RIGHT UPPERCUT"},
                {"type": "combo", "moves": ["left_straight", "right_straight", "left_hook"], "label": "LEFT STRAIGHT > RIGHT STRAIGHT > LEFT HOOK"},
            ]
        if stat_name == "stamina":
            return [
                {"type": "offense", "move_id": "left_straight"},
                {"type": "offense", "move_id": "right_straight"},
                {"type": "offense", "move_id": "left_hook"},
                {"type": "offense", "move_id": "right_hook"},
                {"type": "offense", "move_id": "left_uppercut"},
                {"type": "offense", "move_id": "right_uppercut"},
            ]
        return [
            {"type": "defense", "move_id": "slip_left", "enemy_attack_id": "right_straight"},
            {"type": "defense", "move_id": "slip_right", "enemy_attack_id": "left_straight"},
            {"type": "defense", "move_id": "guard", "enemy_attack_id": "left_hook"},
            {"type": "defense", "move_id": "guard", "enemy_attack_id": "right_uppercut"},
            {"type": "defense", "move_id": "duck", "enemy_attack_id": "left_hook"},
        ]

    def spawn_training_prompt(self, now, frame_w, frame_h):
        if not self.training_sequence:
            self.training_sequence = self.build_training_sequence(self.training_mode)
        template = self.training_sequence[(self.training_hits + self.training_misses) % len(self.training_sequence)]
        expires_at = now + (1.45 if self.training_mode == "agility" else 3.20 if self.training_mode == "power" else 1.15)
        if template.get("type") == "combo":
            prompt = {
                "type": "combo",
                "combo_moves": list(template["moves"]),
                "combo_index": 0,
                "combo_label": template["label"],
                "move_id": template["moves"][0],
            }
            self.training_combo_moves = list(template["moves"])
            self.training_combo_index = 0
        else:
            prompt = dict(template)
            self.training_combo_moves = []
            self.training_combo_index = 0
        prompt["issued_at"] = now
        prompt["expires_at"] = expires_at
        if prompt["type"] in ("offense", "combo"):
            move = MOVE_BY_ID[prompt["move_id"]]
            prompt["move"] = move
            self.training_combo_label = prompt.get("combo_label", "")
            target_key = self.target_key_for_move(move["id"])
            size = int(min(frame_w, frame_h) * 0.17)
            lane = (self.training_hits + self.training_misses + random.randint(0, 2)) % 3
            lanes_x = [int(frame_w * 0.26), int(frame_w * 0.50), int(frame_w * 0.74)]
            rows_y = [int(frame_h * 0.33), int(frame_h * 0.50), int(frame_h * 0.66)]
            cx = lanes_x[lane]
            cy = rows_y[(self.training_hits + self.training_misses) % len(rows_y)]
            if move["id"].endswith("hook"):
                prompt["rect"] = (cx - 130, cy - 46, cx + 130, cy + 46)
                prompt["shape"] = "horizontal"
            elif move["id"].endswith("uppercut"):
                prompt["rect"] = (cx - 48, cy - 122, cx + 48, cy + 122)
                prompt["shape"] = "vertical"
            else:
                prompt["rect"] = (cx - size // 2, cy - size // 2, cx + size // 2, cy + size // 2)
                prompt["shape"] = "circle"
            prompt["target_key"] = target_key
        else:
            prompt["move"] = MOVE_BY_ID[prompt["move_id"]]
            self.enemy_attack_pose = prompt["enemy_attack_id"]
            self.training_combo_label = "React to every prompt fast. Agility now affects all action timing."
        self.training_prompt = prompt

    def process_training(self, pose_data, defense, frame_w, frame_h):
        if self.training_mode is None:
            return
        now = time.time()
        if self.training_prompt is None:
            self.spawn_training_prompt(now, frame_w, frame_h)
        prompt = self.training_prompt
        if prompt is None:
            return

        if prompt["type"] in ("offense", "combo"):
            if now - self.last_punch_at > PUNCH_COOLDOWN and self.can_throw_punch("player") and self.detect_target_hit(pose_data, prompt):
                self.spend_stamina("player", 0.8, now)
                self.last_punch_at = now
                if prompt["type"] == "combo":
                    move_id = prompt["move_id"]
                    technique_key = "jab" if move_id.endswith("straight") else "hook" if move_id.endswith("hook") else "uppercut"
                    self.career.progress_technique(technique_key, 0.18)
                    prompt["combo_index"] += 1
                    self.training_combo_index = prompt["combo_index"]
                    self.audio.play_sfx("sfx/training_hit.wav", throttle=0.04)
                    if prompt["combo_index"] >= len(prompt["combo_moves"]):
                        duration = max(0.001, prompt["expires_at"] - prompt["issued_at"])
                        timing = max(0.0, min(1.0, (prompt["expires_at"] - now) / duration))
                        score = 1.2 + timing * 1.0
                        self.training_score_accum += score
                        self.training_samples += 1
                        self.training_hits += 1
                        self.training_streak += 1
                        self.set_message(f"Combo cleared: {prompt['combo_label']}  streak x{self.training_streak}", 0.8)
                        self.training_prompt = None
                        self.training_combo_moves = []
                        self.training_combo_index = 0
                    else:
                        prompt["move_id"] = prompt["combo_moves"][prompt["combo_index"]]
                        prompt["move"] = MOVE_BY_ID[prompt["move_id"]]
                        self.training_prompt = prompt
                        self.set_message(f"Combo step {prompt['combo_index'] + 1}/{len(prompt['combo_moves'])}: {prompt['move']['label']}", 0.6)
                else:
                    duration = max(0.001, prompt["expires_at"] - prompt["issued_at"])
                    timing = max(0.0, min(1.0, (prompt["expires_at"] - now) / duration))
                    weight = 1.2 if prompt["move_id"].endswith("hook") or prompt["move_id"].endswith("uppercut") else 1.0
                    score = (0.9 + timing * 0.6) * weight
                    self.training_score_accum += score
                    self.training_samples += 1
                    self.training_hits += 1
                    self.training_streak += 1
                    technique_key = "jab" if prompt["move_id"].endswith("straight") else "hook" if prompt["move_id"].endswith("hook") else "uppercut"
                    self.career.progress_technique(technique_key, 0.12 if weight > 1.0 else 0.08)
                    self.audio.play_sfx("sfx/training_hit.wav", throttle=0.04)
                    self.set_message(f"Training hit: {prompt['move']['label']}  streak x{self.training_streak}", 0.7)
                    self.training_prompt = None
        else:
            if self.defense_success(defense, prompt["move_id"]):
                duration = max(0.001, prompt["expires_at"] - prompt["issued_at"])
                timing = max(0.0, min(1.0, (prompt["expires_at"] - now) / duration))
                score = 0.9 + timing * 0.7
                self.training_score_accum += score
                self.training_samples += 1
                self.training_hits += 1
                self.training_streak += 1
                self.audio.play_sfx("sfx/block.wav", throttle=0.04)
                self.set_message(f"Clean defense: {prompt['move']['label']}  streak x{self.training_streak}", 0.7)
                self.career.progress_technique("body", 0.06)
                self.enemy_attack_pose = None
                self.training_prompt = None

        if self.training_prompt and now >= self.training_prompt["expires_at"]:
            self.training_misses += 1
            self.training_streak = 0
            self.training_samples += 1
            self.training_combo_moves = []
            self.training_combo_index = 0
            self.set_message("Training miss. Reset and hit the next prompt cleanly.", 0.8)
            self.audio.play_sfx("sfx/whoosh.wav", throttle=0.04)
            self.enemy_attack_pose = None
            self.training_prompt = None
        if time.time() - self.training_started_at >= self.training_duration:
            self.finish_training()

    def update_round_state(self):
        if self.app_state != "fight" or self.phase == "tutorial" or self.match_over:
            return

        if self.knockdown_state:
            self.resolve_knockdown(time.time())
            return

        if self.enemy_hp <= 0:
            self.start_knockdown("opponent", time.time())
            return

        if self.player_hp <= 0:
            self.start_knockdown("player", time.time())

    def draw_gradient(self, frame):
        h, w = frame.shape[:2]
        overlay = np.zeros_like(frame)
        for y in range(h):
            t = y / max(h - 1, 1)
            b = int(BG[0] * (1 - t) + 40 * t)
            g = int(BG[1] * (1 - t) + 20 * t)
            r = int(BG[2] * (1 - t) + 70 * t)
            overlay[y, :] = (b, g, r)
        cv2.addWeighted(overlay, 0.34, frame, 0.66, 0, frame)
        vignette = frame.copy()
        cv2.rectangle(vignette, (0, 0), (w, h), (8, 6, 18), 28)
        cv2.addWeighted(vignette, 0.08, frame, 0.92, 0, frame)

    def draw_bar(self, frame, label, x, y, hp, max_hp, color, display_max_hp=None):
        bar_w = 260
        bar_h = 24
        self.draw_text(frame, label, (x, y - 22), WHITE, size=18, family="display")
        cv2.rectangle(frame, (x, y), (x + bar_w, y + bar_h), (40, 40, 55), -1)
        display_cap = max(display_max_hp or max_hp, 1)
        fill = int(bar_w * (hp / display_cap))
        cv2.rectangle(frame, (x, y), (x + fill, y + bar_h), color, -1)
        if 0 < max_hp < display_cap:
            limit_x = x + int(bar_w * (max_hp / display_cap))
            cv2.line(frame, (limit_x, y - 2), (limit_x, y + bar_h + 2), GOLD, 2, cv2.LINE_AA)
        cv2.rectangle(frame, (x, y), (x + bar_w, y + bar_h), WHITE, 1)

    def draw_stamina_bar(self, frame, x, y, value, cap, accent):
        bar_w = 260
        bar_h = 8
        cv2.rectangle(frame, (x, y), (x + bar_w, y + bar_h), (34, 36, 48), -1)
        fill = int(bar_w * (value / max(cap, 1.0)))
        cv2.rectangle(frame, (x, y), (x + fill, y + bar_h), accent, -1)

    def draw_circle_icon(self, frame, center, radius, color):
        cv2.circle(frame, center, radius, color, 3, cv2.LINE_AA)
        cv2.circle(frame, center, max(6, radius // 4), color, -1, cv2.LINE_AA)

    def draw_arrow_icon(self, frame, start, end, color):
        cv2.arrowedLine(frame, start, end, color, 6, cv2.LINE_AA, tipLength=0.25)

    def draw_guard_icon(self, frame, center, color):
        cx, cy = center
        cv2.rectangle(frame, (cx - 54, cy - 60), (cx - 20, cy + 45), color, 4)
        cv2.rectangle(frame, (cx + 20, cy - 60), (cx + 54, cy + 45), color, 4)

    def draw_slip_icon(self, frame, center, direction, color):
        cx, cy = center
        cv2.circle(frame, (cx, cy - 28), 18, color, 4, cv2.LINE_AA)
        cv2.line(frame, (cx, cy - 2), (cx, cy + 55), color, 5, cv2.LINE_AA)
        offset = 70 if direction == "right" else -70
        cv2.line(frame, (cx, cy + 10), (cx + offset // 2, cy + 10), color, 4, cv2.LINE_AA)
        cv2.arrowedLine(frame, (cx, cy + 72), (cx + offset, cy + 72), color, 6, cv2.LINE_AA, tipLength=0.25)

    def draw_move_icon(self, frame, move_id, center):
        if move_id == "left_straight":
            self.draw_circle_icon(frame, (center[0] - 85, center[1]), 24, CYAN)
        elif move_id == "right_straight":
            self.draw_circle_icon(frame, (center[0] + 85, center[1]), 24, CYAN)
        elif move_id == "left_hook":
            self.draw_arrow_icon(frame, (center[0] - 125, center[1]), (center[0] - 20, center[1]), CYAN)
        elif move_id == "right_hook":
            self.draw_arrow_icon(frame, (center[0] + 125, center[1]), (center[0] + 20, center[1]), CYAN)
        elif move_id == "left_uppercut":
            self.draw_arrow_icon(frame, (center[0] - 85, center[1] + 45), (center[0] - 85, center[1] - 40), CYAN)
        elif move_id == "right_uppercut":
            self.draw_arrow_icon(frame, (center[0] + 85, center[1] + 45), (center[0] + 85, center[1] - 40), CYAN)
        elif move_id == "guard":
            self.draw_guard_icon(frame, center, ORANGE)
        elif move_id == "slip_left":
            self.draw_slip_icon(frame, center, "left", RED)
        elif move_id == "slip_right":
            self.draw_slip_icon(frame, center, "right", RED)

    def draw_move_demo(self, frame, move_id, rect, t):
        x1, y1, x2, y2 = rect
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        body_color = (166, 178, 196)
        ghost_color = (88, 100, 120)
        left_color = CYAN
        right_color = LIME
        accent = GOLD if "uppercut" in move_id else GREEN if "hook" in move_id else RED if move_id == "duck" else CYAN
        glow = frame.copy()
        cv2.rectangle(glow, (x1, y1), (x2, y2), (18, 26, 46), -1)
        cv2.addWeighted(glow, 0.22, frame, 0.78, 0, frame)
        progress = 0.5 + 0.5 * math.sin(t * 3.6)

        def bezier_points(points, samples=26):
            pts = []
            raw = [np.array(p, dtype=np.float32) for p in points]
            for idx in range(samples):
                u = idx / max(samples - 1, 1)
                if len(raw) == 3:
                    p = (1 - u) ** 2 * raw[0] + 2 * (1 - u) * u * raw[1] + u ** 2 * raw[2]
                else:
                    p = (1 - u) ** 3 * raw[0] + 3 * (1 - u) ** 2 * u * raw[1] + 3 * (1 - u) * u ** 2 * raw[2] + u ** 3 * raw[3]
                pts.append(tuple(p.astype(int)))
            return pts

        def panel_label(view_name):
            self.draw_text(frame, view_name, (x1 + 18, y1 + 18), SOFT, size=15, family="mono")
            self.draw_text(frame, "PATH", (x2 - 62, y1 + 18), accent, size=15, family="mono")

        def draw_side_straight(hand="left"):
            shoulder = np.array([cx - 12, cy - 12], dtype=np.int32)
            hip = np.array([cx - 6, cy + 58], dtype=np.int32)
            head = np.array([cx - 6, cy - 62], dtype=np.int32)
            rear_hand = np.array([cx - 16, cy - 20], dtype=np.int32)
            elbow_start = np.array([cx + 18, cy - 14], dtype=np.int32)
            hand_start = np.array([cx + 6, cy - 8], dtype=np.int32)
            elbow_end = np.array([cx + 54, cy - 18], dtype=np.int32)
            hand_end = np.array([cx + 96, cy - 18], dtype=np.int32)
            if hand == "right":
                elbow_start = np.array([cx + 10, cy - 4], dtype=np.int32)
                hand_start = np.array([cx + 0, cy + 4], dtype=np.int32)
                elbow_end = np.array([cx + 60, cy - 10], dtype=np.int32)
                hand_end = np.array([cx + 112, cy - 10], dtype=np.int32)
            hand_now = (hand_start * (1.0 - progress) + hand_end * progress).astype(int)
            elbow_now = (elbow_start * (1.0 - progress) + elbow_end * progress).astype(int)
            cv2.circle(frame, tuple(head), 18, body_color, 3, cv2.LINE_AA)
            cv2.line(frame, tuple(head + np.array([0, 18])), tuple(shoulder), body_color, 5, cv2.LINE_AA)
            cv2.line(frame, tuple(shoulder), tuple(hip), body_color, 6, cv2.LINE_AA)
            cv2.line(frame, tuple(hip), tuple(hip + np.array([-24, 54])), body_color, 5, cv2.LINE_AA)
            cv2.line(frame, tuple(hip), tuple(hip + np.array([26, 48])), body_color, 5, cv2.LINE_AA)
            cv2.line(frame, tuple(shoulder), tuple(rear_hand + np.array([-24, 18])), ghost_color, 5, cv2.LINE_AA)
            cv2.line(frame, tuple(rear_hand + np.array([-24, 18])), tuple(rear_hand), ghost_color, 5, cv2.LINE_AA)
            cv2.line(frame, tuple(shoulder), tuple(elbow_start), ghost_color, 4, cv2.LINE_AA)
            cv2.line(frame, tuple(elbow_start), tuple(hand_start), ghost_color, 4, cv2.LINE_AA)
            cv2.line(frame, tuple(shoulder), tuple(elbow_now), body_color, 6, cv2.LINE_AA)
            cv2.line(frame, tuple(elbow_now), tuple(hand_now), accent, 7, cv2.LINE_AA)
            curve = bezier_points([hand_start, hand_start + np.array([30, -8]), hand_end], samples=22)
            cv2.polylines(frame, [np.array(curve, dtype=np.int32)], False, accent, 4, cv2.LINE_AA)
            cv2.arrowedLine(frame, curve[-3], curve[-1], accent, 3, cv2.LINE_AA, tipLength=0.18)

        def draw_front_hook(hand="left"):
            head = (cx, cy - 60)
            shoulders_y = cy - 6
            hips_y = cy + 68
            cv2.circle(frame, head, 18, body_color, 3, cv2.LINE_AA)
            cv2.line(frame, (cx, cy - 42), (cx, hips_y), body_color, 6, cv2.LINE_AA)
            cv2.line(frame, (cx - 36, shoulders_y), (cx + 36, shoulders_y), body_color, 6, cv2.LINE_AA)
            cv2.line(frame, (cx - 20, hips_y), (cx - 42, hips_y + 50), body_color, 5, cv2.LINE_AA)
            cv2.line(frame, (cx + 20, hips_y), (cx + 42, hips_y + 50), body_color, 5, cv2.LINE_AA)
            if hand == "left":
                shoulder = (cx - 36, shoulders_y)
                start = np.array([cx - 18, cy - 4], dtype=np.int32)
                control1 = np.array([cx - 90, cy + 2], dtype=np.int32)
                control2 = np.array([cx - 70, cy - 52], dtype=np.int32)
                end = np.array([cx - 12, cy - 34], dtype=np.int32)
                guard_hand = (cx + 20, cy - 14)
            else:
                shoulder = (cx + 36, shoulders_y)
                start = np.array([cx + 18, cy - 4], dtype=np.int32)
                control1 = np.array([cx + 90, cy + 2], dtype=np.int32)
                control2 = np.array([cx + 70, cy - 52], dtype=np.int32)
                end = np.array([cx + 12, cy - 34], dtype=np.int32)
                guard_hand = (cx - 20, cy - 14)
            hand_now = ((1 - progress) ** 3 * start + 3 * (1 - progress) ** 2 * progress * control1 + 3 * (1 - progress) * progress ** 2 * control2 + progress ** 3 * end).astype(int)
            elbow_now = ((shoulder[0] * 0.25 + hand_now[0] * 0.75), (shoulders_y * 0.55 + hand_now[1] * 0.45))
            elbow_now = np.array(elbow_now, dtype=np.int32)
            cv2.line(frame, shoulder, tuple(elbow_now), body_color, 6, cv2.LINE_AA)
            cv2.line(frame, tuple(elbow_now), tuple(hand_now), accent, 7, cv2.LINE_AA)
            curve = bezier_points([start, control1, control2, end], samples=24)
            cv2.polylines(frame, [np.array(curve, dtype=np.int32)], False, accent, 4, cv2.LINE_AA)
            cv2.arrowedLine(frame, curve[-4], curve[-1], accent, 3, cv2.LINE_AA, tipLength=0.24)
            cv2.circle(frame, guard_hand, 10, WHITE, 2, cv2.LINE_AA)

        def draw_front_uppercut(hand="left"):
            head = (cx, cy - 58)
            shoulders_y = cy - 8
            hips_y = cy + 66
            cv2.circle(frame, head, 18, body_color, 3, cv2.LINE_AA)
            cv2.line(frame, (cx, cy - 40), (cx, hips_y), body_color, 6, cv2.LINE_AA)
            cv2.line(frame, (cx - 34, shoulders_y), (cx + 34, shoulders_y), body_color, 6, cv2.LINE_AA)
            cv2.line(frame, (cx - 20, hips_y), (cx - 40, hips_y + 52), body_color, 5, cv2.LINE_AA)
            cv2.line(frame, (cx + 20, hips_y), (cx + 40, hips_y + 52), body_color, 5, cv2.LINE_AA)
            if hand == "left":
                start = np.array([cx - 22, cy + 16], dtype=np.int32)
                control = np.array([cx - 32, cy - 16], dtype=np.int32)
                end = np.array([cx - 4, cy - 46], dtype=np.int32)
                shoulder = (cx - 34, shoulders_y)
                elbow_base = np.array([cx - 40, cy + 8], dtype=np.int32)
            else:
                start = np.array([cx + 22, cy + 16], dtype=np.int32)
                control = np.array([cx + 32, cy - 16], dtype=np.int32)
                end = np.array([cx + 4, cy - 46], dtype=np.int32)
                shoulder = (cx + 34, shoulders_y)
                elbow_base = np.array([cx + 40, cy + 8], dtype=np.int32)
            hand_now = ((1 - progress) ** 2 * start + 2 * (1 - progress) * progress * control + progress ** 2 * end).astype(int)
            elbow_now = (elbow_base * (1.0 - progress) + np.array([(start[0] + control[0]) // 2, (start[1] + control[1]) // 2]) * progress).astype(int)
            cv2.line(frame, shoulder, tuple(elbow_base), ghost_color, 4, cv2.LINE_AA)
            cv2.line(frame, tuple(elbow_base), tuple(start), ghost_color, 4, cv2.LINE_AA)
            cv2.line(frame, shoulder, tuple(elbow_now), body_color, 6, cv2.LINE_AA)
            cv2.line(frame, tuple(elbow_now), tuple(hand_now), accent, 7, cv2.LINE_AA)
            curve = bezier_points([start, control, end], samples=22)
            cv2.polylines(frame, [np.array(curve, dtype=np.int32)], False, accent, 4, cv2.LINE_AA)
            cv2.arrowedLine(frame, curve[-4], curve[-1], accent, 3, cv2.LINE_AA, tipLength=0.20)

        def draw_duck():
            head_start = np.array([cx, cy - 54], dtype=np.int32)
            head_end = np.array([cx, cy - 4], dtype=np.int32)
            torso_start = np.array([cx, cy + 30], dtype=np.int32)
            torso_end = np.array([cx, cy + 48], dtype=np.int32)
            head_now = (head_start * (1.0 - progress) + head_end * progress).astype(int)
            torso_now = (torso_start * (1.0 - progress) + torso_end * progress).astype(int)
            knee_bend = int(16 * progress)
            cv2.circle(frame, tuple(head_start), 18, ghost_color, 2, cv2.LINE_AA)
            cv2.line(frame, (cx, cy - 36), tuple(torso_start), ghost_color, 4, cv2.LINE_AA)
            cv2.circle(frame, tuple(head_now), 18, body_color, 3, cv2.LINE_AA)
            cv2.line(frame, (cx, head_now[1] + 18), tuple(torso_now), body_color, 6, cv2.LINE_AA)
            cv2.line(frame, (cx - 34, cy - 6), (cx - 8, cy - 22), body_color, 6, cv2.LINE_AA)
            cv2.line(frame, (cx + 34, cy - 6), (cx + 8, cy - 22), body_color, 6, cv2.LINE_AA)
            cv2.line(frame, tuple(torso_now), (cx - 34, cy + 92 - knee_bend), body_color, 6, cv2.LINE_AA)
            cv2.line(frame, tuple(torso_now), (cx + 34, cy + 92 - knee_bend), body_color, 6, cv2.LINE_AA)
            cv2.arrowedLine(frame, tuple(head_start + np.array([0, 26])), tuple(head_end + np.array([0, 22])), RED, 4, cv2.LINE_AA, tipLength=0.22)

        def draw_guard():
            head = (cx, cy - 54)
            cv2.circle(frame, head, 18, body_color, 3, cv2.LINE_AA)
            cv2.line(frame, (cx, cy - 36), (cx, cy + 42), body_color, 6, cv2.LINE_AA)
            cv2.line(frame, (cx - 30, cy - 6), (cx + 30, cy - 6), body_color, 6, cv2.LINE_AA)
            left_rect = (cx - 34, cy - 44, cx - 6, cy + 18)
            right_rect = (cx + 6, cy - 44, cx + 34, cy + 18)
            cv2.rectangle(frame, (left_rect[0], left_rect[1]), (left_rect[2], left_rect[3]), ORANGE, 3, cv2.LINE_AA)
            cv2.rectangle(frame, (right_rect[0], right_rect[1]), (right_rect[2], right_rect[3]), ORANGE, 3, cv2.LINE_AA)
            cv2.line(frame, (cx, cy + 42), (cx - 28, cy + 98), body_color, 5, cv2.LINE_AA)
            cv2.line(frame, (cx, cy + 42), (cx + 28, cy + 98), body_color, 5, cv2.LINE_AA)

        def draw_slip(direction):
            shift = -18 if direction == "left" else 18
            head_start = np.array([cx, cy - 54], dtype=np.int32)
            head_end = np.array([cx + shift, cy - 40], dtype=np.int32)
            torso_start = np.array([cx, cy + 40], dtype=np.int32)
            torso_end = np.array([cx + shift, cy + 46], dtype=np.int32)
            head_now = (head_start * (1.0 - progress) + head_end * progress).astype(int)
            torso_now = (torso_start * (1.0 - progress) + torso_end * progress).astype(int)
            cv2.circle(frame, tuple(head_start), 18, ghost_color, 2, cv2.LINE_AA)
            ghost_curve = bezier_points([head_start + np.array([0, 18]), head_start + np.array([shift * 0.18, 48]), torso_start], samples=16)
            cv2.polylines(frame, [np.array(ghost_curve, dtype=np.int32)], False, ghost_color, 4, cv2.LINE_AA)
            cv2.circle(frame, tuple(head_now), 18, body_color, 3, cv2.LINE_AA)
            spine_curve = bezier_points([head_now + np.array([0, 18]), head_now + np.array([shift * 0.36, 52]), torso_now], samples=18)
            cv2.polylines(frame, [np.array(spine_curve, dtype=np.int32)], False, body_color, 6, cv2.LINE_AA)
            cv2.line(frame, tuple(torso_now), tuple(torso_now + np.array([-28, 58])), body_color, 5, cv2.LINE_AA)
            cv2.line(frame, tuple(torso_now), tuple(torso_now + np.array([28, 58])), body_color, 5, cv2.LINE_AA)
            lead_dir = -1 if direction == "left" else 1
            cv2.line(frame, tuple(head_now + np.array([-18 + lead_dir * 8, 24])), tuple(head_now + np.array([-38 + lead_dir * 12, 54])), body_color, 5, cv2.LINE_AA)
            cv2.line(frame, tuple(head_now + np.array([18 + lead_dir * 8, 24])), tuple(head_now + np.array([38 + lead_dir * 12, 54])), body_color, 5, cv2.LINE_AA)
            curve = bezier_points([head_start + np.array([0, 44]), head_start + np.array([shift * 0.35, 52]), head_end + np.array([0, 44])], samples=18)
            cv2.polylines(frame, [np.array(curve, dtype=np.int32)], False, RED, 4, cv2.LINE_AA)
            cv2.arrowedLine(frame, curve[-4], curve[-1], RED, 3, cv2.LINE_AA, tipLength=0.22)

        panel_label("SIDE VIEW" if "straight" in move_id else "FRONT VIEW" if ("hook" in move_id or "uppercut" in move_id or move_id == "duck") else "DEFENSE VIEW")
        if move_id == "left_straight":
            draw_side_straight("left")
        elif move_id == "right_straight":
            draw_side_straight("right")
        elif move_id == "left_hook":
            draw_front_hook("left")
        elif move_id == "right_hook":
            draw_front_hook("right")
        elif move_id == "left_uppercut":
            draw_front_uppercut("left")
        elif move_id == "right_uppercut":
            draw_front_uppercut("right")
        elif move_id == "duck":
            draw_duck()
        elif move_id == "guard":
            self.draw_text(frame, "DEFENSE VIEW", (x1 + 18, y1 + 18), SOFT, size=15, family="mono")
            draw_guard()
        elif move_id == "slip_left":
            self.draw_text(frame, "DEFENSE VIEW", (x1 + 18, y1 + 18), SOFT, size=15, family="mono")
            draw_slip("left")
        elif move_id == "slip_right":
            self.draw_text(frame, "DEFENSE VIEW", (x1 + 18, y1 + 18), SOFT, size=15, family="mono")
            draw_slip("right")

    def opponent_anchor(self, frame):
        h, w = frame.shape[:2]
        return int(w * 0.50), int(h * 0.41)

    def gray_frame(self, frame, amount):
        if amount <= 0.0:
            return
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        cv2.addWeighted(gray_bgr, amount, frame, 1.0 - amount, 0, frame)

    def gray_rgba(self, sprite, amount):
        if sprite is None or amount <= 0.0:
            return sprite
        out = sprite.copy()
        gray = cv2.cvtColor(out[:, :, :3], cv2.COLOR_BGR2GRAY)
        gray_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        out[:, :, :3] = cv2.addWeighted(gray_bgr, amount, out[:, :, :3], 1.0 - amount, 0)
        return out

    def opponent_sprite_pose(self, now):
        pose_name = self.enemy_attack_pose or ""
        sway_x = math.sin(now * 2.6) * 8
        sway_y = math.sin(now * 3.0) * 5
        punch_drive = 0
        lift = 0
        if pose_name.endswith("straight"):
            punch_drive = 22 if pose_name.startswith("right") else -22
        elif pose_name.endswith("hook"):
            punch_drive = 16 if pose_name.startswith("right") else -16
            sway_y -= 8
        elif pose_name.endswith("uppercut"):
            sway_y -= 18
            lift = -14
        elif pose_name == "wide_gate":
            sway_x *= 0.6
        elif pose_name == "tight_shell":
            lift = -10
        elif pose_name == "left_post":
            sway_x -= 10
        elif pose_name == "elbows_high":
            lift = -16
        if now < self.impact_until:
            sway_x += math.sin((self.impact_until - now) * 18.0) * 12
        return punch_drive + sway_x, sway_y + lift

    def smooth_point(self, previous, current, alpha=0.34):
        if previous is None:
            return current
        return (
            int(previous[0] * (1.0 - alpha) + current[0] * alpha),
            int(previous[1] * (1.0 - alpha) + current[1] * alpha),
        )

    def bezier_points(self, points, samples=26):
        pts = []
        raw = [np.array(p, dtype=np.float32) for p in points]
        for idx in range(samples):
            u = idx / max(samples - 1, 1)
            if len(raw) == 3:
                p = (1 - u) ** 2 * raw[0] + 2 * (1 - u) * u * raw[1] + u ** 2 * raw[2]
            else:
                p = (1 - u) ** 3 * raw[0] + 3 * (1 - u) ** 2 * u * raw[1] + 3 * (1 - u) * u ** 2 * raw[2] + u ** 3 * raw[3]
            pts.append(tuple(p.astype(int)))
        return pts

    def blur_rgba(self, sprite, ksize=17):
        if sprite is None:
            return None
        blurred = sprite.copy()
        blurred[:, :, :3] = cv2.GaussianBlur(sprite[:, :, :3], (ksize, ksize), 0)
        return blurred

    def mask_opponent_sprite_gloves(self, frame, cx, cy, scale):
        overlay = frame.copy()
        left_center = (int(cx - 86 * scale), int(cy - 8 * scale))
        right_center = (int(cx + 86 * scale), int(cy - 8 * scale))
        left_axes = (max(28, int(52 * scale)), max(18, int(36 * scale)))
        right_axes = (max(28, int(52 * scale)), max(18, int(36 * scale)))
        forearm_axes = (max(24, int(74 * scale)), max(16, int(26 * scale)))
        cv2.ellipse(overlay, left_center, left_axes, -26, 0, 360, (6, 8, 18), -1, cv2.LINE_AA)
        cv2.ellipse(overlay, right_center, right_axes, 26, 0, 360, (6, 8, 18), -1, cv2.LINE_AA)
        cv2.ellipse(overlay, (int(cx - 60 * scale), int(cy + 16 * scale)), forearm_axes, -22, 0, 360, (8, 10, 22), -1, cv2.LINE_AA)
        cv2.ellipse(overlay, (int(cx + 60 * scale), int(cy + 16 * scale)), forearm_axes, 22, 0, 360, (8, 10, 22), -1, cv2.LINE_AA)
        blur = cv2.GaussianBlur(overlay, (31, 31), 0)
        cv2.addWeighted(blur, 0.97, frame, 0.03, 0, frame)

    def draw_opponent_arm(self, frame, shoulder, elbow, hand, glove_color, glow_color):
        overlay = frame.copy()
        cv2.line(overlay, shoulder, elbow, (196, 214, 236), 16, cv2.LINE_AA)
        cv2.line(overlay, elbow, hand, (208, 224, 244), 18, cv2.LINE_AA)
        cv2.circle(overlay, elbow, 9, (224, 236, 250), -1, cv2.LINE_AA)
        cv2.circle(overlay, hand, 14, (220, 230, 246), -1, cv2.LINE_AA)
        cv2.addWeighted(overlay, 0.72, frame, 0.28, 0, frame)
        glow = frame.copy()
        cv2.line(glow, elbow, hand, glow_color, 26, cv2.LINE_AA)
        cv2.circle(glow, hand, 28, glow_color, -1, cv2.LINE_AA)
        cv2.addWeighted(glow, 0.16, frame, 0.84, 0, frame)
        cv2.line(frame, shoulder, elbow, (200, 218, 240), 9, cv2.LINE_AA)
        cv2.line(frame, elbow, hand, (212, 228, 246), 12, cv2.LINE_AA)
        cv2.circle(frame, elbow, 7, (238, 244, 255), -1, cv2.LINE_AA)
        cv2.circle(frame, hand, 16, glove_color, 3, cv2.LINE_AA)

    def draw_guard_markers(self, frame, left_arm, right_arm, pose_name):
        if pose_name is None:
            return
        if pose_name == "wide_gate":
            for point in (left_arm, right_arm):
                cv2.circle(frame, point, 22, CYAN, 2, cv2.LINE_AA)
            cv2.line(frame, (left_arm[0] + 26, left_arm[1]), (right_arm[0] - 26, right_arm[1]), GOLD, 3, cv2.LINE_AA)
        elif pose_name == "tight_shell":
            for point in (left_arm, right_arm):
                cv2.circle(frame, point, 24, ORANGE, 3, cv2.LINE_AA)
            cv2.circle(frame, ((left_arm[0] + right_arm[0]) // 2, (left_arm[1] + right_arm[1]) // 2), 18, ORANGE, 2, cv2.LINE_AA)
        elif pose_name == "left_post":
            cv2.circle(frame, left_arm, 26, CYAN, 3, cv2.LINE_AA)
            cv2.line(frame, (left_arm[0] - 12, left_arm[1]), (left_arm[0] + 12, left_arm[1]), CYAN, 3, cv2.LINE_AA)
            cv2.circle(frame, right_arm, 18, ORANGE, 2, cv2.LINE_AA)
        elif pose_name == "elbows_high":
            cv2.circle(frame, left_arm, 22, GOLD, 3, cv2.LINE_AA)
            cv2.circle(frame, right_arm, 22, GOLD, 3, cv2.LINE_AA)
            cv2.line(frame, (left_arm[0] + 18, left_arm[1] - 8), (right_arm[0] - 18, right_arm[1] - 8), GOLD, 3, cv2.LINE_AA)

    def draw_attack_telegraph(self, frame, hand_point, now):
        pulse = 1.0 + 0.18 * math.sin(now * 12.0)
        cv2.circle(frame, hand_point, int(36 * pulse), RED, 4, cv2.LINE_AA)
        cv2.circle(frame, hand_point, int(24 * pulse), ORANGE, 3, cv2.LINE_AA)
        cv2.line(frame, (hand_point[0] - 28, hand_point[1]), (hand_point[0] + 28, hand_point[1]), RED, 2, cv2.LINE_AA)
        cv2.line(frame, (hand_point[0], hand_point[1] - 28), (hand_point[0], hand_point[1] + 28), RED, 2, cv2.LINE_AA)

    def draw_block_contact(self, frame, now, left_arm, right_arm):
        if now >= self.block_contact_until or not self.block_contact_side:
            return
        hand_point = left_arm if self.block_contact_side == "left" else right_arm
        player_anchor = (int(frame.shape[1] * 0.33), int(frame.shape[0] * 0.77)) if self.block_contact_side == "left" else (int(frame.shape[1] * 0.67), int(frame.shape[0] * 0.77))
        spark = frame.copy()
        cv2.line(spark, player_anchor, hand_point, ORANGE, 8, cv2.LINE_AA)
        cv2.addWeighted(spark, 0.10, frame, 0.90, 0, frame)
        cv2.line(frame, player_anchor, hand_point, WHITE, 3, cv2.LINE_AA)
        cv2.circle(frame, hand_point, 16, ORANGE, 3, cv2.LINE_AA)

    def draw_opponent_intro_card(self, frame):
        if self.app_state != "fight":
            return
        if self.phase != "intro":
            return
        h, w = frame.shape[:2]
        opponent = self.current_opponent_profile()
        sprite = self.assets["opponents"].get(opponent["id"])
        x1, y1, x2, y2 = w // 2 - 220, 112, w // 2 + 220, h - 112
        self.tech_panel(frame, (x1, y1, x2, y2), MAGENTA, fill=(10, 14, 24), alpha=0.84, line=3)
        if sprite is not None:
            scale = min((x2 - x1 - 28) / max(sprite.shape[1], 1), (y2 - y1 - 180) / max(sprite.shape[0], 1))
            self.overlay_rgba(frame, sprite, ((x1 + x2) // 2, y1 + 182), scale=scale, angle=0.0, alpha_scale=0.98)
        self.draw_text(frame, opponent["name"].upper(), ((x1 + x2) // 2, y2 - 108), WHITE, size=30, family="display", anchor="ma", stroke=1)
        self.draw_text(frame, opponent["title"].upper(), ((x1 + x2) // 2, y2 - 82), SOFT, size=18, family="body", anchor="ma")
        self.draw_text(frame, f"HEIGHT {opponent.get('height', '--')}   WEIGHT {opponent.get('weight', '--')}", ((x1 + x2) // 2, y2 - 54), CYAN, size=18, family="body", anchor="ma")
        self.draw_text(frame, f"RECORD {opponent.get('record', '--')}", ((x1 + x2) // 2, y2 - 28), GOLD, size=18, family="body", anchor="ma")

    def draw_opponent(self, frame, now):
        cx, cy = self.opponent_anchor(frame)
        drift_x, drift_y = self.opponent_sprite_pose(now)
        cx += int(drift_x)
        cy += int(drift_y)
        recoil = 0
        if now < self.impact_until:
            recoil = int(18 * math.sin((self.impact_until - now) * 20))

        opponent = self.current_opponent_profile()
        sprite = self.assets["opponents"].get(opponent["id"])
        ring_focus_mode = self.app_state == "fight" and self.phase not in ("tutorial", "intro") and now >= self.round_freeze_until
        calm_photo_mode = (self.app_state == "fight" and self.phase in ("tutorial", "intro")) or self.app_state == "training"
        if sprite is not None:
            sprite_for_ring = sprite
            if self.knockdown_state and self.knockdown_state["fighter"] == "opponent":
                remaining = max(0.0, self.knockdown_state["countdown_end"] - now)
                gray_amount = min(1.0, 0.35 + remaining / 8.0 * 0.65)
                sprite_for_ring = self.gray_rgba(sprite_for_ring, gray_amount)
            elif now < self.opponent_recover_until:
                blend = (self.opponent_recover_until - now) / max(0.001, 2.4)
                sprite_for_ring = self.gray_rgba(sprite_for_ring, min(0.8, blend))
            if ring_focus_mode:
                sprite_for_ring = self.blur_rgba(sprite_for_ring, ksize=19)
            sprite_scale = min(frame.shape[1] / max(sprite.shape[1], 1) * 0.34, frame.shape[0] / max(sprite.shape[0], 1) * 0.62)
            sprite_center = (cx + recoil, cy - 20)
            self.overlay_rgba(frame, sprite_for_ring, sprite_center, scale=sprite_scale, angle=0.0, alpha_scale=0.86)
            if ring_focus_mode:
                self.mask_opponent_sprite_gloves(frame, sprite_center[0], sprite_center[1], sprite_scale * 2.5)
            if calm_photo_mode:
                return

        l_shoulder = (cx - 62 + recoil, cy - 52)
        r_shoulder = (cx + 62 + recoil, cy - 52)
        l_elbow = (l_shoulder[0] - 18, cy - 18)
        r_elbow = (r_shoulder[0] + 18, cy - 18)
        left_arm = (l_shoulder[0] - 12, cy - 34)
        right_arm = (r_shoulder[0] + 12, cy - 34)
        hand_wave = int(math.sin(now * 7.2) * 5)
        guard_wave = int(math.cos(now * 5.1) * 4)
        
        pose_name = self.enemy_attack_pose
        if pose_name == "wide_gate":
            l_elbow = (l_shoulder[0] - 54 - guard_wave, cy - 44)
            r_elbow = (r_shoulder[0] + 54 + guard_wave, cy - 44)
            left_arm = (l_shoulder[0] - 112 - hand_wave, cy - 104)
            right_arm = (r_shoulder[0] + 112 + hand_wave, cy - 104)
        elif pose_name == "tight_shell":
            l_elbow = (l_shoulder[0] + 14 - guard_wave, cy - 34)
            r_elbow = (r_shoulder[0] - 14 + guard_wave, cy - 34)
            left_arm = (cx - 18 - hand_wave, cy - 148)
            right_arm = (cx + 18 + hand_wave, cy - 148)
        elif pose_name == "left_post":
            l_elbow = (l_shoulder[0] + 10 - guard_wave, cy - 58)
            r_elbow = (r_shoulder[0] + 26 + guard_wave, cy - 12)
            left_arm = (cx + 6 - hand_wave, cy - 132)
            right_arm = (r_shoulder[0] + 46 + hand_wave, cy - 58)
        elif pose_name == "elbows_high":
            l_elbow = (l_shoulder[0] + 10 - guard_wave, cy + 10)
            r_elbow = (r_shoulder[0] - 10 + guard_wave, cy + 10)
            left_arm = (cx - 28 - hand_wave, cy - 18)
            right_arm = (cx + 28 + hand_wave, cy - 18)
        elif pose_name == "left_straight":
            l_elbow = (l_shoulder[0] - 34 - guard_wave, cy - 44)
            left_arm = (l_shoulder[0] - 98 - hand_wave, cy - 42)
            r_elbow = (r_shoulder[0] - 6, cy - 18)
            right_arm = (r_shoulder[0] - 12, cy - 12)
        elif pose_name == "right_straight":
            r_elbow = (r_shoulder[0] + 34 + guard_wave, cy - 44)
            right_arm = (r_shoulder[0] + 98 + hand_wave, cy - 42)
            l_elbow = (l_shoulder[0] + 6, cy - 18)
            left_arm = (l_shoulder[0] + 12, cy - 12)
        elif pose_name == "left_hook":
            l_elbow = (l_shoulder[0] - 58 - guard_wave, cy - 10)
            left_arm = (l_shoulder[0] - 84 - hand_wave, cy - 94)
            r_elbow = (r_shoulder[0] - 4, cy - 18)
            right_arm = (r_shoulder[0] - 18, cy - 14)
        elif pose_name == "right_hook":
            r_elbow = (r_shoulder[0] + 58 + guard_wave, cy - 10)
            right_arm = (r_shoulder[0] + 84 + hand_wave, cy - 94)
            l_elbow = (l_shoulder[0] + 4, cy - 18)
            left_arm = (l_shoulder[0] + 18, cy - 14)
        elif pose_name == "left_uppercut":
            l_elbow = (l_shoulder[0] + 20 - guard_wave, cy + 34)
            left_arm = (l_shoulder[0] + 44 - hand_wave, cy - 4)
            r_elbow = (r_shoulder[0] - 8, cy - 12)
            right_arm = (r_shoulder[0] - 18, cy - 8)
        elif pose_name == "right_uppercut":
            r_elbow = (r_shoulder[0] - 20 + guard_wave, cy + 34)
            right_arm = (r_shoulder[0] - 44 + hand_wave, cy - 4)
            l_elbow = (l_shoulder[0] + 8, cy - 12)
            left_arm = (l_shoulder[0] + 18, cy - 8)
        elif pose_name == "prep_left_straight":
            l_elbow = (l_shoulder[0] + 10, cy - 22)
            r_elbow = (r_shoulder[0] - 2, cy - 26)
            left_arm = (l_shoulder[0] + 18, cy - 96)
            right_arm = (r_shoulder[0] - 4, cy - 108)
        elif pose_name == "prep_right_straight":
            l_elbow = (l_shoulder[0] + 2, cy - 26)
            r_elbow = (r_shoulder[0] - 10, cy - 22)
            left_arm = (l_shoulder[0] + 4, cy - 108)
            right_arm = (r_shoulder[0] - 18, cy - 96)
        elif pose_name == "prep_left_hook":
            l_elbow = (l_shoulder[0] - 58 - guard_wave, cy - 40)
            r_elbow = (r_shoulder[0] + 42 + guard_wave, cy - 48)
            left_arm = (l_shoulder[0] - 116 - hand_wave, cy - 102)
            right_arm = (r_shoulder[0] + 92 + hand_wave, cy - 106)
        elif pose_name == "prep_right_hook":
            l_elbow = (l_shoulder[0] - 42 - guard_wave, cy - 48)
            r_elbow = (r_shoulder[0] + 58 + guard_wave, cy - 40)
            left_arm = (l_shoulder[0] - 92 - hand_wave, cy - 106)
            right_arm = (r_shoulder[0] + 116 + hand_wave, cy - 102)
        elif pose_name == "prep_left_uppercut":
            l_elbow = (l_shoulder[0] + 24, cy + 32)
            r_elbow = (r_shoulder[0] - 8, cy + 2)
            left_arm = (l_shoulder[0] + 36, cy + 4)
            right_arm = (r_shoulder[0] - 28, cy - 28)
        elif pose_name == "prep_right_uppercut":
            l_elbow = (l_shoulder[0] + 8, cy + 2)
            r_elbow = (r_shoulder[0] - 24, cy + 32)
            left_arm = (l_shoulder[0] + 28, cy - 28)
            right_arm = (r_shoulder[0] - 36, cy + 4)
            
        left_arm = self.smooth_point(self.enemy_hand_render["left"], left_arm, alpha=0.28)
        right_arm = self.smooth_point(self.enemy_hand_render["right"], right_arm, alpha=0.28)
        self.enemy_hand_render["left"] = left_arm
        self.enemy_hand_render["right"] = right_arm

        self.draw_opponent_arm(frame, l_shoulder, l_elbow, left_arm, CYAN, (34, 130, 220))
        self.draw_opponent_arm(frame, r_shoulder, r_elbow, right_arm, RED, (170, 54, 48))
        self.draw_guard_markers(frame, left_arm, right_arm, pose_name)
        self.draw_block_contact(frame, now, left_arm, right_arm)

        enemy_glove = self.glove_sprite("enemy")
        if enemy_glove is not None:
            mirrored = cv2.flip(enemy_glove, 1)
            left_sprite = enemy_glove
            right_sprite = mirrored
            left_scale = 0.28
            right_scale = 0.28
            left_angle = -16
            right_angle = 16
            if pose_name in ("left_straight", "right_straight"):
                left_angle = -90 if pose_name == "left_straight" else -12
                right_angle = 90 if pose_name == "right_straight" else 12
            elif pose_name in ("left_hook", "right_hook"):
                left_angle = -48 if pose_name == "left_hook" else -12
                right_angle = 48 if pose_name == "right_hook" else 12
            elif pose_name in ("left_uppercut", "right_uppercut"):
                left_angle = -130 if pose_name == "left_uppercut" else -20
                right_angle = 130 if pose_name == "right_uppercut" else 20
            elif pose_name == "wide_gate":
                left_angle = -90
                right_angle = 90
            elif pose_name == "tight_shell":
                left_angle = -15
                right_angle = 15
            elif pose_name == "left_post":
                left_angle = -20
                right_angle = 45
            elif pose_name == "elbows_high":
                left_angle = -92
                right_angle = 92
            elif pose_name == "prep_left_straight":
                left_angle = -8
                right_angle = 8
            elif pose_name == "prep_right_straight":
                left_angle = -8
                right_angle = 8
            elif pose_name == "prep_left_hook":
                left_angle = -90
                right_angle = 90
            elif pose_name == "prep_right_hook":
                left_angle = -90
                right_angle = 90
            elif pose_name == "prep_left_uppercut":
                left_angle = -134
                right_angle = 12
            elif pose_name == "prep_right_uppercut":
                left_angle = -12
                right_angle = 134
            # Opponent gloves face toward the player, so use the opposite
            # perspective from the local first-person gloves.
            left_angle *= -1
            right_angle *= -1
            if now < self.enemy_attack_flash_until and self.enemy_attack_flash_hand:
                pulse = 1.0 + 0.16 * (0.5 + 0.5 * math.sin(now * 16.0))
                if self.enemy_attack_flash_hand == "left":
                    left_scale *= pulse + 0.12
                else:
                    right_scale *= pulse + 0.12
            self.overlay_rgba(frame, left_sprite, left_arm, scale=left_scale, angle=left_angle, alpha_scale=0.94)
            self.overlay_rgba(frame, right_sprite, right_arm, scale=right_scale, angle=right_angle, alpha_scale=0.94)
        if now < self.enemy_attack_flash_until and self.enemy_attack_flash_hand:
            flash_point = left_arm if self.enemy_attack_flash_hand == "left" else right_arm
            self.draw_attack_telegraph(frame, flash_point, now)

        target = (cx + recoil, cy - 28)
        pulse = 1.0 + 0.08 * math.sin(now * 9.0)
        cv2.circle(frame, target, int(34 * pulse), GOLD, 2, cv2.LINE_AA)
        cv2.circle(frame, target, int(18 * pulse), RED, 2, cv2.LINE_AA)
        cv2.line(frame, (target[0] - 48, target[1]), (target[0] + 48, target[1]), GOLD, 1, cv2.LINE_AA)
        cv2.line(frame, (target[0], target[1] - 48), (target[0], target[1] + 48), GOLD, 1, cv2.LINE_AA)

        if now < self.impact_until:
            t = self.impact_until - now
            for angle in range(0, 360, 30):
                radians = math.radians(angle)
                radius = int(85 * (1.0 - t / 0.65) + 18)
                px = int(target[0] + math.cos(radians) * radius)
                py = int(target[1] + math.sin(radians) * radius)
                color = GOLD if angle % 60 == 0 else ORANGE if angle % 90 == 0 else RED
                cv2.circle(frame, (px, py), 5, color, -1, cv2.LINE_AA)
            self.draw_text(frame, f"POWER LEVEL: {self.power_level}", (cx - 122, cy - 96), GOLD, size=24, family="display", stroke=1)
        elif self.enemy_block:
            self.draw_text(frame, self.enemy_block["label"], (cx - 88, cy - 100), ORANGE, size=24, family="display", stroke=1)

        name_y = min(frame.shape[0] - 126, cy + 164)
        self.draw_text(frame, opponent["name"].upper(), (cx, name_y), WHITE, size=28, family="display", anchor="ma", stroke=1)
        self.draw_text(frame, opponent["title"].upper(), (cx, name_y + 26), SOFT, size=17, family="body", anchor="ma")
        self.draw_text(frame, f"THROWN {self.match_enemy_thrown_punches}   LANDED {self.match_enemy_landed_hits}", (cx, name_y + 50), ORANGE, size=16, family="display", anchor="ma", stroke=1)

    def draw_player_gloves(self, frame):
        sprite = self.glove_sprite("player")
        if sprite is None:
            return

        left_sprite = sprite
        right_sprite = cv2.flip(sprite, 1)
        left_center = (int(frame.shape[1] * 0.29), int(frame.shape[0] * 0.82))
        right_center = (int(frame.shape[1] * 0.71), int(frame.shape[0] * 0.82))
        scale = 0.34
        l_scale = scale
        r_scale = scale
        left_angle = -10
        right_angle = 10

        if self.last_pose_data is not None:
            pose = self.last_pose_data
            shoulder_width = max(pose["shoulder_width"], 1.0)
            scale = min(0.44, max(0.20, shoulder_width / max(frame.shape[1], 1) * 1.28))
            
            l_z = pose["l_wrist"][2]
            r_z = pose["r_wrist"][2]
            l_shrink = max(0.65, 1.0 + (l_z / shoulder_width) * 0.4)
            r_shrink = max(0.65, 1.0 + (r_z / shoulder_width) * 0.4)
            l_scale = scale * l_shrink
            r_scale = scale * r_shrink
            
            left_center = (
                int(np.clip(pose["l_wrist"][0], frame.shape[1] * 0.12, frame.shape[1] * 0.88)),
                int(np.clip(pose["l_wrist"][1], frame.shape[0] * 0.20, frame.shape[0] * 0.92)),
            )
            right_center = (
                int(np.clip(pose["r_wrist"][0], frame.shape[1] * 0.12, frame.shape[1] * 0.88)),
                int(np.clip(pose["r_wrist"][1], frame.shape[0] * 0.20, frame.shape[0] * 0.92)),
            )
            lift = max(12, int(frame.shape[0] * 0.018))
            left_center = (left_center[0], left_center[1] - lift)
            right_center = (right_center[0], right_center[1] - lift)

        self.overlay_rgba(frame, left_sprite, left_center, scale=l_scale, angle=left_angle, alpha_scale=0.92)
        self.overlay_rgba(frame, right_sprite, right_center, scale=r_scale, angle=right_angle, alpha_scale=0.92)

    def draw_target_preview_card(self, frame, image, rect, title, accent):
        x1, y1, x2, y2 = rect
        self.tech_panel(frame, rect, accent, fill=(9, 12, 22), alpha=0.78)
        preview = self.resize_cover(image, x2 - x1 - 18, y2 - y1 - 44)
        if preview is not None:
            frame[y1 + 14 : y2 - 30, x1 + 9 : x2 - 9] = preview
        cv2.putText(frame, title, (x1 + 14, y2 - 10), cv2.FONT_HERSHEY_DUPLEX, 0.50, WHITE, 1, cv2.LINE_AA)

    def draw_technique_cards(self, frame, start_x, start_y, card_w=210, card_h=126, gap=18):
        cards = [
            ("jab_target", "JAB", "jab", CYAN),
            ("hook_target", "HOOK", "hook", GREEN),
            ("uppercut_target", "UPPERCUT", "uppercut", GOLD),
            ("body_target", "BODY", "body", ORANGE),
        ]
        for idx, (asset_key, label, stat_key, accent) in enumerate(cards):
            x1 = start_x + idx * (card_w + gap)
            x2 = x1 + card_w
            y1 = start_y
            y2 = y1 + card_h
            self.tech_panel(frame, (x1, y1, x2, y2), accent, fill=(9, 12, 22), alpha=0.76)
            image = self.assets["targets"].get(asset_key)
            preview = self.resize_cover(image, 88, 66)
            if preview is not None:
                frame[y1 + 16 : y1 + 82, x1 + 10 : x1 + 98] = preview
            self.draw_text(frame, label, (x1 + 112, y1 + 34), WHITE, size=18, family="display")
            self.draw_text(frame, f"{self.career.techniques[stat_key]:.2f}", (x1 + 112, y1 + 62), accent, size=18, family="body")
            self.draw_text(frame, "More clean reps = faster growth", (x1 + 112, y1 + 88), SOFT, size=13, family="body")

    def draw_training_targets(self, frame):
        h, w = frame.shape[:2]
        placements = [
            ("jab_target", (w // 2 - 320, 170, w // 2 - 70, 330), "JAB TARGET", CYAN),
            ("hook_target", (w // 2 + 70, 170, w // 2 + 320, 330), "HOOK TARGET", GREEN),
            ("uppercut_target", (w // 2 - 320, 360, w // 2 - 70, 520), "UPPERCUT", GOLD),
            ("body_target", (w // 2 + 70, 360, w // 2 + 320, 520), "BODY SHIELD", ORANGE),
        ]
        for key, rect, label, accent in placements:
            self.draw_target_preview_card(frame, self.assets["targets"].get(key), rect, label, accent)

    def draw_training_prompt(self, frame):
        if self.training_prompt is None:
            return
        prompt = self.training_prompt
        if prompt["type"] in ("offense", "combo"):
            self.target_prompt = {
                "move_id": prompt["move_id"],
                "shape": prompt["shape"],
                "target_key": prompt["target_key"],
                "rect": prompt["rect"],
            }
            self.draw_target_prompt(frame)
            self.target_prompt = None
            self.tech_panel(frame, (frame.shape[1] // 2 - 240, 122, frame.shape[1] // 2 + 240, 250), ORANGE, fill=(12, 12, 24), alpha=0.84)
            self.draw_move_icon(frame, prompt["move_id"], (frame.shape[1] // 2, 168))
            label = prompt["move"]["label"]
            if prompt["type"] == "combo" and self.training_combo_moves:
                label = f"{label}  {prompt.get('combo_index', 0) + 1}/{len(self.training_combo_moves)}"
            cv2.putText(frame, label, (frame.shape[1] // 2 - 180, 216), cv2.FONT_HERSHEY_DUPLEX, 0.76, WHITE, 2, cv2.LINE_AA)
            if prompt["type"] == "combo" and prompt.get("combo_label"):
                cv2.putText(frame, prompt["combo_label"], (frame.shape[1] // 2 - 214, 242), cv2.FONT_HERSHEY_SIMPLEX, 0.52, GOLD, 2, cv2.LINE_AA)
        else:
            self.tech_panel(frame, (frame.shape[1] // 2 - 240, 122, frame.shape[1] // 2 + 240, 250), ORANGE, fill=(12, 12, 24), alpha=0.84)
            self.draw_move_icon(frame, prompt["move_id"], (frame.shape[1] // 2, 168))
            attack = MOVE_BY_ID[prompt["enemy_attack_id"]]
            cv2.putText(frame, f"DEFEND: {prompt['move']['label']}", (frame.shape[1] // 2 - 176, 210), cv2.FONT_HERSHEY_DUPLEX, 0.78, WHITE, 2, cv2.LINE_AA)
            cv2.putText(frame, f"Vs {attack['label']}", (frame.shape[1] // 2 - 84, 238), cv2.FONT_HERSHEY_SIMPLEX, 0.60, GOLD, 2, cv2.LINE_AA)

    def draw_fight_instruction_card(self, frame):
        if self.app_state != "fight":
            return
        now = time.time()
        if now >= self.fight_help_until and not (self.prompt and (self.prompt.get("enemy_block") or self.prompt.get("enemy_attack_id"))):
            return
        x1, y1, x2, y2 = 34, frame.shape[0] - 168, 520, frame.shape[0] - 68
        self.tech_panel(frame, (x1, y1, x2, y2), ORANGE, fill=(10, 14, 24), alpha=0.78)
        line1 = "Straight: slip away from the punch or high guard."
        line2 = "Hook: duck is best. Guard cuts damage. Uppercut: guard cuts damage."
        line3 = "Wide gate -> straight   Tight shell -> hook   Elbows high -> straight."
        if self.prompt and self.prompt.get("enemy_block"):
            block = self.prompt["enemy_block"]
            line1 = f"Rival shows {block['label']}."
            line2 = block["hint"]
            line3 = "Follow the center prompt and match the opening."
        elif self.prompt and self.prompt.get("enemy_attack_id"):
            attack = MOVE_BY_ID[self.prompt["enemy_attack_id"]]
            line1 = f"Incoming {attack['label']}."
            if self.prompt.get("family") == "straight":
                line2 = "Slip to the opposite side or use a tight high guard."
                line3 = "Guard blocks all. Wrong slip gets clipped."
            elif self.prompt.get("family") == "hook":
                line2 = "Duck under it. Guard works but only cuts damage."
                line3 = "Wide wind-up + red ring means hook is loading."
            else:
                line2 = "Read the low red ring. Guard cuts most of the damage."
                line3 = "Uppercut starts from low hand position."
        cv2.putText(frame, line1, (x1 + 16, y1 + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.58, WHITE, 2, cv2.LINE_AA)
        cv2.putText(frame, line2, (x1 + 16, y1 + 54), cv2.FONT_HERSHEY_SIMPLEX, 0.54, GOLD, 2, cv2.LINE_AA)
        cv2.putText(frame, line3, (x1 + 16, y1 + 80), cv2.FONT_HERSHEY_SIMPLEX, 0.48, SOFT, 1, cv2.LINE_AA)

    def draw_trails(self, frame):
        trail_specs = [("left", CYAN), ("right", LIME)]
        for hand, color in trail_specs:
            history = self.wrist_history[hand]
            if len(history) < 2:
                continue
            points = [pt[:2].astype(int) for _, pt in history]
            for idx in range(1, len(points)):
                alpha = idx / len(points)
                thickness = max(1, int(2 + alpha * 4))
                cv2.line(frame, tuple(points[idx - 1]), tuple(points[idx]), color, thickness, cv2.LINE_AA)

    def draw_ghost_guides(self, frame):
        h, w = frame.shape[:2]
        self.tech_panel(frame, (22, 132, 198, 278), MAGENTA, fill=(20, 24, 40), alpha=0.56)
        self.draw_move_icon(frame, "left_straight", (106, 176))
        cv2.putText(frame, "GHOST JAB", (44, 226), cv2.FONT_HERSHEY_DUPLEX, 0.55, WHITE, 1, cv2.LINE_AA)

        dodge_center = (w - 120, 190)
        self.draw_slip_icon(frame, dodge_center, "left", SOFT)
        cv2.putText(frame, "DODGE", (w - 162, 272), cv2.FONT_HERSHEY_DUPLEX, 0.58, WHITE, 1, cv2.LINE_AA)
        duck_center = (w - 120, 330)
        cv2.circle(frame, (duck_center[0], duck_center[1] - 10), 16, SOFT, 3, cv2.LINE_AA)
        cv2.line(frame, (duck_center[0], duck_center[1] + 4), (duck_center[0], duck_center[1] + 36), SOFT, 4, cv2.LINE_AA)
        cv2.line(frame, (duck_center[0], duck_center[1] + 36), (duck_center[0] - 20, duck_center[1] + 52), SOFT, 4, cv2.LINE_AA)
        cv2.line(frame, (duck_center[0], duck_center[1] + 36), (duck_center[0] + 20, duck_center[1] + 52), SOFT, 4, cv2.LINE_AA)
        cv2.putText(frame, "DUCK", (w - 148, 392), cv2.FONT_HERSHEY_DUPLEX, 0.58, WHITE, 1, cv2.LINE_AA)

    def draw_monitor_widget(self, frame):
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = w - 214, 18, w - 26, 112
        self.tech_panel(frame, (x1, y1, x2, y2), CYAN, fill=(18, 20, 36), alpha=0.78)
        cv2.rectangle(frame, (x1 + 16, y1 + 18), (x2 - 16, y2 - 24), (30, 34, 56), -1)
        cv2.circle(frame, (x1 + 54, y1 + 42), 12, CYAN, 2, cv2.LINE_AA)
        cv2.rectangle(frame, (x1 + 92, y1 + 30), (x2 - 32, y1 + 50), MAGENTA, 2)
        cv2.line(frame, (x1 + 54, y1 + 58), (x1 + 54, y2 - 32), CYAN, 2, cv2.LINE_AA)
        cv2.putText(frame, "LIVE FEED", (x1 + 44, y2 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, SOFT, 1, cv2.LINE_AA)

    def draw_command_panel(self, frame, move, expires_at):
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = w // 2 - 280, 104, w // 2 + 280, 318
        self.tech_panel(frame, (x1, y1, x2, y2), MAGENTA, fill=(12, 12, 24), alpha=0.86)
        self.draw_move_icon(frame, move["id"], (w // 2, y1 + 72))
        self.draw_text(frame, move["label"], (w // 2, y1 + 128), WHITE, size=40, family="display", anchor="ma", stroke=1)
        self.draw_text(frame, move["hint"], (w // 2, y1 + 164), SOFT, size=22, family="body", anchor="ma")
        if self.prompt:
            if self.prompt["type"] == "defense" and self.prompt.get("enemy_attack_id"):
                attack = MOVE_BY_ID[self.prompt["enemy_attack_id"]]
                self.draw_text(frame, f"INCOMING: {attack['label']}", (w // 2, y1 + 198), GOLD, size=24, family="body", anchor="ma")
            elif self.prompt["type"] == "offense" and self.prompt.get("enemy_block"):
                block = self.prompt["enemy_block"]
                self.draw_text(frame, block["label"], (w // 2, y1 + 198), ORANGE, size=24, family="display", anchor="ma")
                self.draw_text(frame, block["hint"], (w // 2, y1 + 226), SOFT, size=18, family="body", anchor="ma")
        remain = max(0.0, expires_at - time.time())
        fill_w = int((x2 - x1 - 24) * (remain / REACTION_TIME))
        timer_color = GREEN if remain > 0.9 else GOLD if remain > 0.4 else RED
        cv2.rectangle(frame, (x1 + 12, y2 - 26), (x2 - 12, y2 - 10), (45, 45, 60), -1)
        cv2.rectangle(frame, (x1 + 12, y2 - 26), (x1 + 12 + fill_w, y2 - 10), timer_color, -1)

    def draw_realtime_panel(self, frame):
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = w // 2 - 260, 106, w // 2 + 260, 248
        self.tech_panel(frame, (x1, y1, x2, y2), CYAN, fill=(10, 14, 26), alpha=0.84)
        if self.prompt and self.prompt.get("type") == "defense":
            attack = MOVE_BY_ID[self.prompt["enemy_attack_id"]]
            self.draw_text(frame, "LIVE DEFENSE", (w // 2, y1 + 28), RED, size=24, family="display", anchor="ma")
            self.draw_text(frame, attack["label"], (w // 2, y1 + 72), WHITE, size=36, family="display", anchor="ma", stroke=1)
            self.draw_text(frame, f"Answer with {self.prompt['move']['label']}", (w // 2, y1 + 110), GOLD, size=22, family="body", anchor="ma")
        elif self.prompt and self.prompt.get("type") == "offense":
            block = self.prompt.get("enemy_block")
            self.draw_text(frame, "LIVE OPENING", (w // 2, y1 + 28), CYAN, size=24, family="display", anchor="ma")
            if block:
                self.draw_text(frame, block["label"], (w // 2, y1 + 72), WHITE, size=34, family="display", anchor="ma", stroke=1)
                self.draw_text(frame, block["hint"], (w // 2, y1 + 110), GOLD, size=20, family="body", anchor="ma")
        else:
            self.draw_text(frame, "LIVE FLOW", (w // 2, y1 + 34), CYAN, size=24, family="display", anchor="ma")
            self.draw_text(frame, "Read the guard. Punch when the lane opens.", (w // 2, y1 + 80), WHITE, size=22, family="body", anchor="ma")
            self.draw_text(frame, "Defend instantly when the rival fires back.", (w // 2, y1 + 112), SOFT, size=20, family="body", anchor="ma")

    def draw_target_prompt(self, frame):
        if not self.target_prompt:
            return
        x1, y1, x2, y2 = self.target_prompt["rect"]
        move = MOVE_BY_ID[self.target_prompt["move_id"]]
        target_key = self.target_prompt.get("target_key", self.target_key_for_move(move["id"]))
        theme = TARGET_THEME[target_key]
        accent = theme["color"]
        glow = frame.copy()
        cv2.rectangle(glow, (x1 - 10, y1 - 10), (x2 + 10, y2 + 10), accent, -1)
        cv2.addWeighted(glow, 0.08, frame, 0.92, 0, frame)
        if self.target_prompt["shape"] == "circle":
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            radius = (x2 - x1) // 2
            cv2.circle(frame, (cx, cy), radius, accent, 4, cv2.LINE_AA)
            cv2.circle(frame, (cx, cy), max(10, radius // 3), accent, 2, cv2.LINE_AA)
        elif self.target_prompt["shape"] == "horizontal":
            cv2.ellipse(frame, ((x1 + x2) // 2, (y1 + y2) // 2), ((x2 - x1) // 2, max(20, (y2 - y1) // 2)), 0, 210, 330, accent, 4, cv2.LINE_AA)
            cv2.line(frame, (x1 + 26, y1 + 14), (x2 - 26, y2 - 14), accent, 2, cv2.LINE_AA)
        else:
            cv2.rectangle(frame, (x1, y1), (x2, y2), accent, 4)
            cv2.arrowedLine(frame, ((x1 + x2) // 2, y2 - 16), ((x1 + x2) // 2, y1 + 16), accent, 3, cv2.LINE_AA, tipLength=0.25)
        cv2.putText(frame, theme["label"], (x1 - 10, max(40, y1 - 36)), cv2.FONT_HERSHEY_DUPLEX, 0.62, accent, 2, cv2.LINE_AA)
        cv2.putText(frame, move["label"], (x1 - 10, max(56, y1 - 10)), cv2.FONT_HERSHEY_DUPLEX, 0.7, WHITE, 2, cv2.LINE_AA)

    def draw_hud(self, frame, defense):
        h, w = frame.shape[:2]
        self.tech_panel(frame, (20, 18, w - 20, 108), CYAN, fill=(10, 10, 20), alpha=0.74)
        player_name = self.career.player_name or "PLAYER"
        opponent_name = self.current_opponent_profile()["name"].upper()
        self.draw_bar(frame, player_name.upper(), 40, 50, self.player_hp, self.fight_player_max_hp, GREEN, self.fight_player_display_max_hp)
        self.draw_bar(frame, opponent_name, w - 360, 50, self.enemy_hp, self.fight_enemy_max_hp, MAGENTA, self.fight_enemy_display_max_hp)
        self.draw_stamina_bar(frame, 40, 78, self.player_stamina, max(1.0, float(self.player_hp)), CYAN)
        self.draw_stamina_bar(frame, w - 360, 78, self.enemy_stamina, max(1.0, float(self.enemy_hp)), ORANGE)
        rounds_text = f"ROUND {self.round_index}   {player_name.upper()} {self.player_rounds} - {self.enemy_rounds} {opponent_name}"
        self.draw_text(frame, rounds_text, (w // 2, 48), WHITE, size=26, family="display", anchor="ma")
        phase_label = "Tutorial" if self.phase == "tutorial" else "Command Mode" if self.phase == "command_round" else "Live Fight" if self.phase == "realtime_round" else "Target Mode"
        gap_value = self.realtime_gap() if self.phase == "realtime_round" else self.current_gap()
        pace_text = f"{phase_label}   Tempo {gap_value:.2f}s   Guard {'ON' if defense['guard'] else 'OFF'}"
        self.draw_text(frame, pace_text, (w // 2, 80), SOFT, size=19, family="body", anchor="ma")
        arena = self.active_arena if self.app_state == "fight" else self.current_arena_for_ui()
        self.draw_text(frame, f"{arena['name'].upper()}  |  {arena['scene']}", (34, 118), CYAN, size=19, family="body")
        self.draw_text(frame, f"YOU THROWN {self.match_thrown_punches}  LANDED {self.match_landed_hits}", (34, 144), WHITE, size=20, family="display", stroke=1)
        self.draw_text(frame, f"YOU KD {self.player_knockdowns}  |  RIVAL KD {self.enemy_knockdowns}", (34, 168), SOFT, size=18, family="display")
        if self.last_action_feedback and time.time() < self.last_action_feedback["until"]:
            self.draw_text(frame, self.last_action_feedback["text"], (34, 194), self.last_action_feedback["color"], size=22, family="display", stroke=1)
        if time.time() < self.message_until:
            self.draw_text(frame, self.message, (34, h - 30), GOLD, size=24, family="body", stroke=1)

        if self.match_over:
            label = "YOU WIN" if self.match_winner == "PLAYER" else "YOU LOSE"
            color = GREEN if self.match_winner == "PLAYER" else RED
            cv2.rectangle(frame, (w // 2 - 240, h // 2 - 150), (w // 2 + 240, h // 2 + 150), (15, 15, 28), -1)
            cv2.rectangle(frame, (w // 2 - 240, h // 2 - 150), (w // 2 + 240, h // 2 + 150), color, 3)
            cv2.putText(frame, "MATCH SUMMARY", (w // 2 - 130, h // 2 - 110), cv2.FONT_HERSHEY_DUPLEX, 1.0, WHITE, 2, cv2.LINE_AA)
            cv2.putText(frame, label, (w // 2 - 95, h // 2 - 60), cv2.FONT_HERSHEY_DUPLEX, 1.4, color, 3, cv2.LINE_AA)
            cv2.putText(frame, f"Punches Landed: {self.match_landed_hits} / {max(1, self.match_thrown_punches)}", (w // 2 - 170, h // 2 - 10), cv2.FONT_HERSHEY_DUPLEX, 0.7, WHITE, 1, cv2.LINE_AA)
            cv2.putText(frame, f"Hits Taken: {self.match_taken_hits}", (w // 2 - 170, h // 2 + 30), cv2.FONT_HERSHEY_DUPLEX, 0.7, WHITE, 1, cv2.LINE_AA)
            cv2.putText(frame, f"Highest Combo: {self.combo_peak}", (w // 2 - 170, h // 2 + 70), cv2.FONT_HERSHEY_DUPLEX, 0.7, WHITE, 1, cv2.LINE_AA)
            cv2.putText(frame, f"Payout: ${self.last_payout}", (w // 2 - 170, h // 2 + 110), cv2.FONT_HERSHEY_DUPLEX, 0.7, GOLD, 1, cv2.LINE_AA)
            cv2.putText(frame, "Right Uppercut back to map  |  Left Uppercut rematch", (w // 2 - 260, h // 2 + 190), cv2.FONT_HERSHEY_SIMPLEX, 0.68, WHITE, 3, cv2.LINE_AA)
        elif self.phase in ("command_round", "realtime_round") and time.time() < self.round_freeze_until:
            pulse = 1.0 + 0.06 * math.sin(time.time() * 6.0)
            self.draw_text(frame, f"ROUND {self.round_index}", (w // 2, h // 2 - 16), GOLD, size=int(72 * pulse), family="display", anchor="ma", stroke=2)
            self.draw_text(frame, f"FIRST TO {self.rounds_needed_to_win}", (w // 2, h // 2 + 26), CYAN, size=22, family="display", anchor="ma", stroke=1)
            self.draw_text(frame, "GET READY", (w // 2, h // 2 + 58), WHITE, size=30, family="display", anchor="ma", stroke=1)
        if self.knockdown_state:
            fighter = self.knockdown_state["fighter"]
            seconds_left = max(0.0, self.knockdown_state["countdown_end"] - time.time())
            title = "GET UP" if fighter == "player" else "COUNT"
            self.draw_text(frame, title, (w // 2, h // 2 - 24), RED if fighter == "player" else GOLD, size=56, family="display", anchor="ma", stroke=2)
            self.draw_text(frame, f"{seconds_left:0.1f}", (w // 2, h // 2 + 24), WHITE, size=38, family="display", anchor="ma", stroke=1)
            if fighter == "player":
                self.draw_text(frame, "Swing both hands hard to improve your get-up chance", (w // 2, h // 2 + 62), CYAN, size=20, family="body", anchor="ma")

    def draw_pose(self, frame, landmarks):
        if landmarks is None:
            return
        self.mp_drawing.draw_landmarks(
            frame,
            landmarks,
            mp.solutions.pose.POSE_CONNECTIONS,
            landmark_drawing_spec=self.mp_drawing.DrawingSpec(color=(182, 190, 202), thickness=1, circle_radius=1),
            connection_drawing_spec=self.mp_drawing.DrawingSpec(color=(102, 118, 140), thickness=1),
        )

    def draw_tutorial_panel(self, frame):
        if self.phase != "tutorial" or self.tutorial_step >= len(TUTORIAL_SEQUENCE):
            return
        move_id = TUTORIAL_SEQUENCE[self.tutorial_step]
        move = MOVE_BY_ID[move_id]
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = w // 2 - 360, 92, w // 2 + 360, 372
        self.tech_panel(frame, (x1, y1, x2, y2), ORANGE, fill=(12, 12, 24), alpha=0.88)
        demo_rect = (x1 + 20, y1 + 28, x1 + 270, y2 - 26)
        self.tech_panel(frame, demo_rect, CYAN, fill=(18, 22, 34), alpha=0.52)
        self.draw_move_demo(frame, move_id, demo_rect, time.time())
        self.draw_move_icon(frame, move_id, (x1 + 392, y1 + 74))
        self.draw_text(frame, f"CAPTURE {move['label']}", (x1 + 300, y1 + 58), WHITE, size=42, family="display", stroke=1)
        self.draw_text(frame, move["hint"], (x1 + 300, y1 + 110), GOLD, size=24, family="body")
        current_rep = self.tutorial_samples.get(move_id, 0)
        needed = tutorial_rep_target(move_id)
        progress = f"Capture {current_rep}/{needed}"
        self.draw_text(frame, progress, (x1 + 300, y1 + 154), CYAN, size=26, family="display")
        self.draw_text_block(
            frame,
            [
                "Watch the demo silhouette on the left.",
                "Match the path and finish cleanly to lock your profile.",
                "Use mirrored webcam movement: your left hand is the left-side prompt.",
            ],
            x1 + 300,
            y1 + 196,
            size=20,
            family="body",
            color=SOFT,
            line_gap=10,
        )

    def draw_name_entry(self, frame):
        h, w = frame.shape[:2]
        hero = self.assets["backgrounds"].get("national")
        if hero is None:
            hero = self.assets["backgrounds"].get("city")
        preview = self.resize_cover(hero, w, h)
        if preview is not None:
            cv2.addWeighted(preview, 0.38, frame, 0.62, 0, frame)
        self.draw_gradient(frame)
        self.tech_panel(frame, (w // 2 - 350, 92, w // 2 + 350, h - 94), CYAN, fill=(8, 12, 24), alpha=0.86, line=3)
        self.draw_text(frame, "ENTER FIGHTER NAME", (w // 2, 152), WHITE, size=46, family="display", anchor="ma", stroke=1)
        self.draw_text(frame, "This name will appear on your fight card and match HUD.", (w // 2, 200), SOFT, size=22, family="body", anchor="ma")
        self.tech_panel(frame, (w // 2 - 250, 246, w // 2 + 250, 330), MAGENTA, fill=(16, 20, 32), alpha=0.90, line=2)
        shown = self.name_input if self.name_input else "TYPE YOUR NAME"
        shown_color = WHITE if self.name_input else SOFT
        self.draw_text(frame, shown, (w // 2, 290), shown_color, size=34, family="display", anchor="ma")
        self.draw_text_block(
            frame,
            [
                "Keys: letters, numbers, space, backspace.",
                "Press Enter to continue into the career mode.",
                "Suggested style: short, strong, easy to read in the ring.",
            ],
            w // 2 - 220,
            376,
            size=22,
            family="body",
            color=WHITE,
            line_gap=16,
        )
        self.draw_text(frame, "Examples: Zaha / Blue Circuit / Voss Breaker", (w // 2, h - 134), GOLD, size=22, family="body", anchor="ma")
        self.draw_text(frame, "Press Q anytime to quit.", (w // 2, h - 96), CYAN, size=18, family="body", anchor="ma")

    def draw_hub(self, frame):
        h, w = frame.shape[:2]
        self.draw_text(frame, "CAREER MAP", (40, 64), WHITE, size=42, family="display", stroke=1)
        self.draw_text(frame, f"FIGHTER: {self.career.player_name or 'PLAYER'}", (40, 98), CYAN, size=20, family="body")
        self.draw_text(frame, f"Cash ${self.career.cash}   Points {self.career.points}   W-L {self.career.record['wins']}-{self.career.record['losses']}   Rank #{self.career.current_world_rank()}", (40, 124), GOLD, size=20, family="body")
        menu_y = h // 2
        card_w = 210
        starts = [w // 2 - 350, w // 2 - 105, w // 2 + 140]
        for idx, label in enumerate(HUB_MENU):
            x1 = starts[idx]
            x2 = x1 + card_w
            y1 = menu_y - 70
            y2 = menu_y + 70
            selected = idx == self.selected_hub_index
            border = GOLD if selected else CYAN
            self.tech_panel(frame, (x1, y1, x2, y2), border, fill=(14, 18, 28), alpha=0.82, line=3 if selected else 2)
            self.draw_text(frame, label.upper(), ((x1 + x2) // 2, y1 + 82), WHITE, size=32, family="display", anchor="ma", stroke=1)
        arena = self.current_arena_for_ui()
        self.tech_panel(frame, (40, h - 176, 540, h - 76), CYAN, fill=(10, 14, 24), alpha=0.76)
        self.draw_text(frame, f"UP NEXT: {arena['name'].upper()}", (56, h - 140), WHITE, size=28, family="display")
        self.draw_text(frame, arena["challenge"], (56, h - 104), SOFT, size=18, family="body")
        self.draw_text(frame, "Slip Left / Right to move. Left Uppercut confirm. Right Uppercut back.", (40, h - 46), WHITE, size=20, family="body", stroke=1)

    def draw_arena_map(self, frame):
        h, w = frame.shape[:2]
        self.draw_text(frame, "FIGHT MAP", (40, 64), WHITE, size=42, family="display", stroke=1)
        self.draw_text(frame, "Move through the full ladder one arena at a time.", (40, 98), SOFT, size=20, family="body")
        arena = CAREER_ARENAS[self.selected_arena_index]
        top_card = (40, 120, w - 40, 308)
        self.tech_panel(frame, top_card, GOLD, fill=(10, 14, 24), alpha=0.84, line=2)
        bg_preview = self.assets["backgrounds"].get(arena["id"])
        opp = self.current_opponent_profile() if self.active_arena == arena else OPPONENT_ROSTER[arena["id"]]
        opp_sprite = self.assets["opponents"].get(opp["id"])
        if bg_preview is not None:
            bg_resized = self.resize_cover(bg_preview, 250, 148)
            frame[top_card[1] + 18 : top_card[1] + 18 + bg_resized.shape[0], top_card[0] + 18 : top_card[0] + 18 + bg_resized.shape[1]] = bg_resized
        if opp_sprite is not None:
            opp_h, opp_w = opp_sprite.shape[:2]
            scale = min(132 / max(opp_h, 1), 168 / max(opp_w, 1))
            self.overlay_rgba(frame, opp_sprite, (top_card[0] + 336, top_card[1] + 98), scale=scale, alpha_scale=0.96)
        self.draw_text(frame, f"{arena['name'].upper()}  |  {arena['scene'].upper()}", (top_card[0] + 418, top_card[1] + 42), WHITE, size=28, family="display")
        self.draw_text(frame, opp["name"].upper(), (top_card[0] + 418, top_card[1] + 82), CYAN, size=22, family="display")
        self.draw_text(frame, f"{opp['title']}   {opp['height']}   {opp['weight']}   {opp['record']}", (top_card[0] + 418, top_card[1] + 108), SOFT, size=17, family="body")
        self.draw_text(frame, arena["unlock_rule"], (top_card[0] + 418, top_card[1] + 136), GOLD, size=18, family="body")
        self.draw_text_block(frame, [arena["challenge"], f"Entry Fee: ${arena['entry_fee']}    Upkeep: ${arena['upkeep']}"], top_card[0] + 418, top_card[1] + 160, size=18, family="body", color=WHITE, line_gap=8)

        track_panel = (40, 336, w - 40, h - 86)
        self.tech_panel(frame, track_panel, CYAN, fill=(10, 14, 24), alpha=0.48, line=2)
        x_positions = np.linspace(track_panel[0] + 140, track_panel[2] - 140, num=len(CAREER_ARENAS)).astype(int)
        y_track = [track_panel[1] + 250, track_panel[1] + 230, track_panel[1] + 184, track_panel[1] + 232, track_panel[1] + 206]
        node_points = [(int(x_positions[idx]), int(y_track[idx])) for idx in range(len(CAREER_ARENAS))]
        for idx, arena in enumerate(CAREER_ARENAS):
            x, y = node_points[idx]
            unlocked = self.career.is_unlocked(arena["id"])
            selected = idx == self.selected_arena_index
            color = GOLD if selected else GREEN if unlocked else SOFT
            radius = 32 if selected else 23
            glow = frame.copy()
            cv2.circle(glow, (x, y), radius + 10, color, -1, cv2.LINE_AA)
            cv2.addWeighted(glow, 0.08, frame, 0.92, 0, frame)
            cv2.circle(frame, (x, y), radius, color, 3, cv2.LINE_AA)
            cv2.circle(frame, (x, y), 8 if selected else 6, WHITE, -1, cv2.LINE_AA)
            self.draw_text(frame, arena["name"].upper(), (x, y + 56), WHITE, size=18, family="display", anchor="ma", stroke=1)
            self.draw_text(frame, arena["scene"], (x, y + 80), SOFT, size=14, family="body", anchor="ma")
            status = "READY" if self.career.can_enter(arena) else "LOCKED" if not unlocked else f"Need ${arena['entry_fee']}"
            self.draw_text(frame, status, (x, y - 42), color, size=14, family="mono", anchor="ma")
            if idx < len(CAREER_ARENAS) - 1:
                nx, ny = node_points[idx + 1]
                curve = self.bezier_points(
                    [(x, y), ((x + nx) // 2, min(y, ny) - 42), (nx, ny)],
                    samples=20,
                )
                cv2.polylines(frame, [np.array(curve, dtype=np.int32)], False, CYAN, 2, cv2.LINE_AA)
        self.draw_text(frame, "Slip Left / Right to choose arena. Left Uppercut enter fight. Right Uppercut back.", (40, h - 46), WHITE, size=20, family="body", stroke=1)

    def draw_locker_room(self, frame):
        h, w = frame.shape[:2]
        self.draw_text(frame, "LOCKER ROOM", (40, 64), WHITE, size=42, family="display", stroke=1)
        belt_text = "STATE BELT: OWNED" if self.career.state_belt_won else "STATE BELT: LOCKED"
        self.draw_text(frame, f"Cash ${self.career.cash}   Sponsor bonuses {self.career.completed_tasks}   {belt_text}", (40, 98), GOLD, size=20, family="body")
        panel_x1, panel_y1 = 40, 140
        self.tech_panel(frame, (panel_x1, panel_y1, w - 40, h - 70), CYAN, fill=(16, 18, 28), alpha=0.82)
        self.draw_technique_cards(frame, 78, 154, card_w=254, card_h=86, gap=18)
        stats = self.career.stats
        summary_lines = [
            f"Power {stats['power']:.1f}   Stamina {stats['stamina']:.1f}   Agility {stats['agility']:.1f}",
            f"Active Sponsor Goal: {self.career.sponsor_tasks[self.career.completed_tasks % len(self.career.sponsor_tasks)]}",
            f"Selected Arena: {CAREER_ARENAS[self.selected_arena_index]['name']}  Entry ${CAREER_ARENAS[self.selected_arena_index]['entry_fee']}  Upkeep ${CAREER_ARENAS[self.selected_arena_index]['upkeep']}",
            f"World Rank Estimate: #{self.career.current_world_rank()}",
        ]
        for idx, text in enumerate(summary_lines):
            self.draw_text(frame, text, (68, 254 + idx * 36), WHITE if idx == 0 else SOFT, size=22 if idx == 0 else 18, family="body")
        card_gap = 30
        card_w = (w - 120 - card_gap) // 2
        left_card = (60, 404, 60 + card_w, h - 96)
        right_card = (left_card[2] + card_gap, 404, left_card[2] + card_gap + card_w, h - 96)
        self.tech_panel(frame, left_card, GOLD, fill=(10, 14, 24), alpha=0.72)
        self.tech_panel(frame, right_card, CYAN, fill=(10, 14, 24), alpha=0.72)
        self.draw_text(frame, "RECENT RESULTS", (left_card[0] + 16, left_card[1] + 30), WHITE, size=26, family="display")
        history = self.career.match_history[:5]
        if history:
            for idx, item in enumerate(history):
                y = left_card[1] + 66 + idx * 44
                result_color = GREEN if item["result"] == "WIN" else RED
                self.draw_text(frame, f"{item['result']}  {item['detail']}", (left_card[0] + 18, y), result_color, size=18, family="display")
                self.draw_text(frame, f"{item['arena']} vs {item['opponent']}   Landed {item['landed_hits']}   Combo {item['combo_peak']}", (left_card[0] + 118, y), WHITE, size=16, family="body")
        else:
            self.draw_text(frame, "No completed fights logged yet.", (left_card[0] + 18, left_card[1] + 82), SOFT, size=18, family="body")
        self.draw_text(frame, "LATEST TRAINING", (right_card[0] + 16, right_card[1] + 30), WHITE, size=26, family="display")
        if self.last_training_report:
            for idx, text in enumerate(self.last_training_report):
                self.draw_text(frame, text, (right_card[0] + 18, right_card[1] + 72 + idx * 34), GOLD if idx == 0 else WHITE, size=18, family="body")
        else:
            self.draw_text(frame, "No recent training summary yet.", (right_card[0] + 18, right_card[1] + 82), SOFT, size=18, family="body")
        glove_sheet = self.assets["sheets"].get("gloves_sheet")
        if glove_sheet is not None:
            preview = self.resize_cover(glove_sheet, 220, 126)
            ph, pw = preview.shape[:2]
            frame[panel_y1 + 26 : panel_y1 + 26 + ph, w - 280 : w - 280 + pw] = preview
        self.draw_text(frame, "Right Hook to go back. Open Training from the hub to start drills.", (50, h - 34), WHITE, size=20, family="body", stroke=1)

    def draw_training_menu(self, frame):
        h, w = frame.shape[:2]
        self.draw_text(frame, "TRAINING GYM", (40, 64), WHITE, size=42, family="display", stroke=1)
        self.draw_text(frame, f"Cash ${self.career.cash}", (40, 98), GOLD, size=20, family="body")
        card_w = 320
        gap = 26
        total_w = card_w * 3 + gap * 2
        start_x = (w - total_w) // 2
        y1 = 176
        y2 = 364
        descriptions = {
            "power": "Learn random 3-punch combinations and hit them clean.",
            "stamina": "Throw as many clean punches as possible before time runs out.",
            "agility": "React faster to every action prompt: slips, guards, ducks, and counters.",
        }
        for idx, label in enumerate(TRAINING_MENU):
            x1 = start_x + idx * (card_w + gap)
            x2 = x1 + card_w
            selected = idx == self.selected_training_index
            border = GOLD if selected else CYAN
            stat_key = label.lower()
            cost = self.career.train_cost(stat_key)
            self.tech_panel(frame, (x1, y1, x2, y2), border, fill=(16, 18, 28), alpha=0.82, line=3 if selected else 2)
            self.draw_text(frame, label.upper(), (x1 + 20, y1 + 34), WHITE, size=28, family="display")
            self.draw_text(frame, f"Value {self.career.stats[stat_key]:.2f}", (x1 + 20, y1 + 68), GOLD, size=20, family="body")
            self.draw_text(frame, f"Cost ${cost}", (x1 + 20, y1 + 96), CYAN, size=18, family="body")
            self.draw_text_block(frame, [descriptions[stat_key]], x1 + 20, y1 + 126, size=17, family="body", color=SOFT, line_gap=8)
        self.draw_technique_cards(frame, start_x, 420, card_w=220, card_h=128, gap=24)
        self.draw_text(frame, "Slip Left / Right to select. Left Hook start drill. Right Hook back.", (40, h - 46), WHITE, size=20, family="body", stroke=1)

    def draw_training_overlay(self, frame):
        if self.app_state != "training" or self.training_mode is None:
            return
        h, w = frame.shape[:2]
        remaining = max(0.0, self.training_duration - (time.time() - self.training_started_at))
        title = f"{self.training_mode.upper()} DRILL"
        hint = {
            "power": "Follow the printed combo and drive each punch cleanly.",
            "stamina": "Throw nonstop volume. More clean punches means better stamina gain.",
            "agility": "React faster to every prompt: slips, guards, ducks, and counters.",
        }[self.training_mode]
        combo_goal = {
            "power": self.training_combo_label or "Combo Goal: Left Straight > Right Hook > Left Uppercut",
            "stamina": "Goal: build the biggest clean punch count before time runs out",
            "agility": "Goal: beat every reaction prompt before the timer closes",
        }[self.training_mode]
        self.tech_panel(frame, (w // 2 - 250, 24, w // 2 + 250, 112), ORANGE, fill=(12, 12, 24), alpha=0.86)
        cv2.putText(frame, title, (w // 2 - 120, 54), cv2.FONT_HERSHEY_DUPLEX, 0.96, WHITE, 3, cv2.LINE_AA)
        cv2.putText(frame, hint, (w // 2 - 205, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.62, GOLD, 3, cv2.LINE_AA)
        cv2.putText(frame, combo_goal, (w // 2 - 214, 108), cv2.FONT_HERSHEY_SIMPLEX, 0.56, CYAN, 2, cv2.LINE_AA)
        cv2.putText(frame, f"{remaining:0.1f}s", (w // 2 - 36, 132), cv2.FONT_HERSHEY_DUPLEX, 0.8, WHITE, 2, cv2.LINE_AA)
        stat_now = self.career.stats[self.training_mode]
        cv2.putText(frame, f"Hits {self.training_hits}   Misses {self.training_misses}   Streak x{self.training_streak}   {self.training_mode.title()} {stat_now:.2f}", (42, 124), cv2.FONT_HERSHEY_SIMPLEX, 0.62, WHITE, 2, cv2.LINE_AA)
        if self.training_mode == "power" and self.training_combo_moves:
            combo_text = " > ".join(MOVE_BY_ID[mid]["label"] for mid in self.training_combo_moves)
            self.draw_text(frame, combo_text, (42, 154), ORANGE, size=18, family="display")
            self.draw_text(frame, f"Current Step {self.training_combo_index + 1}/{len(self.training_combo_moves)}", (42, 178), CYAN, size=18, family="body")

    def run(self):
        while self.cap.isOpened():
            ok, frame = self.cap.read()
            if not ok:
                break

            now = time.time()
            if not self.paused:
                self.update_stamina(now)
            frame = cv2.flip(frame, 1)
            frame_h, frame_w = frame.shape[:2]
            results = self.pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            pose_landmarks = results.pose_landmarks if results.pose_landmarks else None
            defense = {"guard": False, "slip_left": False, "slip_right": False, "lean_ratio": 0.0}

            if pose_landmarks is not None:
                pose_data = self.build_pose_data(pose_landmarks, frame_w, frame_h)
                self.last_pose_data = pose_data
                self.update_wrist_memory(pose_data)
                self.head_y_history.append(pose_data["nose"][1])
                if pose_data["min_visibility"] > 0.45:
                    defense = self.defense_state(pose_data)
                    if self.knockdown_state and self.knockdown_state["fighter"] == "player":
                        left_motion = self.summarize_wrist_motion("left", pose_data)
                        right_motion = self.summarize_wrist_motion("right", pose_data)
                        if self.motion_is_active(left_motion, strict=False) or self.motion_is_active(right_motion, strict=False):
                            self.player_getup_meter = min(1.0, self.player_getup_meter + 0.035)
                    if self.app_state in ("hub", "arena_map", "locker", "training_menu") or (self.app_state == "fight" and self.match_over):
                        self.handle_menu_gestures(pose_data, defense, now)
                    if self.app_state == "fight" and not self.paused:
                        if self.knockdown_state:
                            self.update_round_state()
                        elif self.phase == "intro":
                            if now >= self.fight_intro_until:
                                self.start_round(1)
                        elif self.phase == "tutorial":
                            self.run_tutorial(pose_data, defense, now)
                        elif self.phase == "command_round":
                            self.process_command_round(pose_data, defense, now)
                        elif self.phase == "realtime_round":
                            self.process_realtime_round(pose_data, defense, now)
                        elif self.phase == "target_round":
                            self.process_target_round(pose_data, now, frame_w, frame_h)
                    elif self.app_state == "training" and not self.paused:
                        self.process_training(pose_data, defense, frame_w, frame_h)
                else:
                    self.last_pose_data = None
                    self.set_message("Move back a little: show head, both hands, and hips in camera.", 0.35)
            else:
                self.last_pose_data = None
                self.set_message("Camera cannot see your body yet. Step into the center.", 0.35)

            if self.app_state == "fight" and not self.paused:
                self.update_round_state()

            self.sync_audio_scene()
            self.draw_arena_background(frame)
            self.draw_holo_grid(frame, step=74)
            if self.app_state == "name_entry":
                self.draw_name_entry(frame)
            elif self.app_state == "hub":
                self.draw_hub(frame)
            elif self.app_state == "arena_map":
                self.draw_arena_map(frame)
            elif self.app_state == "locker":
                self.draw_locker_room(frame)
            elif self.app_state == "training_menu":
                self.draw_training_menu(frame)
            else:
                if self.app_state == "fight":
                    self.draw_opponent(frame, now)
                elif self.training_mode == "agility":
                    self.draw_opponent(frame, now)
                else:
                    self.draw_training_targets(frame)
                self.draw_player_gloves(frame)
                self.draw_trails(frame)
                self.draw_monitor_widget(frame)
                if self.app_state == "fight":
                    self.draw_target_prompt(frame)
                elif self.app_state == "training":
                    self.draw_training_prompt(frame)
                if self.app_state == "fight":
                    if self.phase == "intro":
                        self.draw_opponent_intro_card(frame)
                    if self.phase == "tutorial":
                        self.draw_tutorial_panel(frame)
                    elif self.phase == "command_round" and self.prompt:
                        self.draw_command_panel(frame, self.prompt["move"], self.prompt["expires_at"])
                    elif self.phase == "realtime_round":
                        self.draw_realtime_panel(frame)
                    self.draw_fight_instruction_card(frame)
                self.draw_pose(frame, pose_landmarks)
                self.draw_hud(frame, defense)
                self.draw_training_overlay(frame)

            if now < self.hit_flash_until:
                flash = frame.copy()
                cv2.rectangle(flash, (0, 0), (frame_w, frame_h), GOLD, -1)
                cv2.addWeighted(flash, 0.08, frame, 0.92, 0, frame)
            if now < self.damage_flash_until:
                flash = frame.copy()
                cv2.rectangle(flash, (0, 0), (frame_w, frame_h), RED, -1)
                cv2.addWeighted(flash, 0.12, frame, 0.88, 0, frame)
                shake = int(10 * max(0.0, self.damage_flash_until - now) / 0.22)
                dx = int(math.sin(now * 58.0) * shake)
                dy = int(math.cos(now * 45.0) * max(2, shake // 2))
                matrix = np.float32([[1, 0, dx], [0, 1, dy]])
                frame = cv2.warpAffine(frame, matrix, (frame_w, frame_h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            if self.knockdown_state and self.knockdown_state["fighter"] == "player":
                remaining = max(0.0, self.knockdown_state["countdown_end"] - now)
                self.gray_frame(frame, min(1.0, 0.40 + remaining / 8.0 * 0.55))
            elif now < self.player_recover_until:
                self.gray_frame(frame, min(0.75, (self.player_recover_until - now) / 2.4))
            if self.paused:
                self.tech_panel(frame, (frame_w // 2 - 220, frame_h // 2 - 90, frame_w // 2 + 220, frame_h // 2 + 90), MAGENTA, fill=(8, 12, 22), alpha=0.86, line=3)
                self.draw_text(frame, "PAUSED", (frame_w // 2, frame_h // 2 - 10), WHITE, size=44, family="display", anchor="ma", stroke=1)
                self.draw_text(frame, "Press P to resume", (frame_w // 2, frame_h // 2 + 28), SOFT, size=20, family="body", anchor="ma")

            cv2.imshow(WINDOW_NAME, frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("p") and self.app_state in ("fight", "training"):
                self.paused = not self.paused
            if key == ord("q") and self.app_state in ("hub", "arena_map", "locker", "training_menu", "name_entry"):
                break
            if key == ord("q") and self.app_state == "fight":
                self.reset_match()
                self.app_state = "arena_map"
                continue
            if key == ord("q") and self.app_state == "training":
                self.finish_training()
                self.app_state = "training_menu"
                continue
            if key == ord("r"):
                self.reset_match()
                self.app_state = "hub"
            if self.app_state == "name_entry":
                if key in (8, 127):
                    self.name_input = self.name_input[:-1]
                elif key in (10, 13):
                    self.commit_player_name()
                elif key == 32 and len(self.name_input) < 18:
                    self.name_input += " "
                elif 32 <= key <= 126 and chr(key).isalnum() and len(self.name_input) < 18:
                    self.name_input += chr(key)
                elif key in (ord("-"), ord("_")) and len(self.name_input) < 18:
                    self.name_input += chr(key)
            if key == ord(" "):
                if self.app_state == "fight" and self.match_over:
                    self.app_state = "hub"

        self.cap.release()
        self.audio.stop_all()
        cv2.destroyAllWindows()


def main():
    BoxingCommandArena().run()


if __name__ == "__main__":
    main()
