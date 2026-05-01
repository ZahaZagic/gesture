import math
import random
import time
from collections import deque
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

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
        "counter": "uppercut",
        "counter_moves": ["left_uppercut", "right_uppercut"],
        "label": "ELBOWS HIGH",
        "hint": "Head is covered high. Rip an uppercut up the middle.",
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
        saved = self.storage.load()
        self.career = BoxingCareer.from_dict(saved.get("career"))
        self.learned_profiles = self.load_learned_profiles(saved)
        self.tutorial_samples = {move_id: 0 for move_id in TUTORIAL_SEQUENCE}
        self.app_state = "hub"
        self.selected_hub_index = 0
        self.selected_training_index = 0
        self.selected_arena_index = 0
        self.active_arena = CAREER_ARENAS[0]
        self.menu_action_cooldown_until = 0.0
        self.match_settled = False
        self.last_payout = 0
        self.match_landed_hits = 0
        self.combo_peak = 0
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
        self.last_pose_data = None
        self.fight_player_max_hp = MAX_HP
        self.fight_enemy_max_hp = MAX_HP
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
        self.next_prompt_at = 0.0
        self.phase = "tutorial"
        self.tutorial_step = 0
        self.target_prompt = None
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
        }
        for arena_id, filename in ARENA_BACKGROUND_NAMES.items():
            path = ASSET_ROOT / "backgrounds" / filename
            if path.exists():
                assets["backgrounds"][arena_id] = cv2.imread(str(path), cv2.IMREAD_COLOR)
        for name in ("jab_target", "hook_target", "uppercut_target", "body_target"):
            path = ASSET_ROOT / "targets" / f"{name}.png"
            if path.exists():
                assets["targets"][name] = cv2.imread(str(path), cv2.IMREAD_COLOR)
        for name in ("player_glove_rgba", "enemy_glove_rgba"):
            path = ASSET_ROOT / "gloves" / f"{name}.png"
            if path.exists():
                assets["gloves"][name] = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        for name in ("gloves_sheet", "targets_sheet"):
            path = ASSET_ROOT / f"{name}.png"
            if path.exists():
                assets["sheets"][name] = cv2.imread(str(path), cv2.IMREAD_COLOR)
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

    def current_arena_for_ui(self):
        if self.app_state == "fight":
            return self.active_arena
        return CAREER_ARENAS[self.selected_arena_index]

    def arena_background(self):
        arena = self.current_arena_for_ui()
        return self.assets["backgrounds"].get(arena["id"])

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
        self.target_prompt = None
        self.player_hp = MAX_HP
        self.enemy_hp = MAX_HP
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
        self.set_message("Tutorial first: perform each move once so tracking can lock in.", 2.5)
        self.match_settled = False
        self.last_payout = 0
        self.match_landed_hits = 0
        self.combo_peak = 0
        self.match_thrown_punches = 0
        self.match_taken_hits = 0

    def start_round(self, round_index):
        now = time.time()
        self.round_index = round_index
        self.player_hp = self.fight_player_max_hp
        self.enemy_hp = self.fight_enemy_max_hp
        self.prompt = None
        self.prompt_queue.clear()
        self.enemy_block = None
        self.enemy_attack_pose = None
        self.target_prompt = None
        self.last_punch_at = 0.0
        self.combo_count = 0
        self.combo_until = 0.0
        self.impact_until = 0.0
        self.impact_move_id = None
        self.wrist_history["left"].clear()
        self.wrist_history["right"].clear()
        self.round_freeze_until = now + ROUND_FREEZE_TIME
        self.next_prompt_at = self.round_freeze_until + 0.8
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
        arena = CAREER_ARENAS[self.selected_arena_index]
        self.active_arena = arena
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
        self.fight_enemy_max_hp = MAX_HP + arena["enemy_hp_bonus"] + rank * 2
        self.player_hp = self.fight_player_max_hp
        self.enemy_hp = self.fight_enemy_max_hp
        self.match_settled = False
        self.phase = "tutorial"
        self.tutorial_step = 0
        self.tutorial_samples = {move_id: 0 for move_id in TUTORIAL_SEQUENCE}
        self.set_message(f"{arena['name']} fight night. Motion capture warmup first.", 2.4)
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
        success, gain, cost = self.career.apply_training(self.training_mode, avg_score)
        if success:
            self.set_message(f"{self.training_mode.title()} +{gain:.2f}. Cost ${cost}.", 2.4)
            self.save_progress()
        else:
            self.set_message(f"Training canceled. Need ${cost}.", 2.4)
        self.training_mode = None
        self.training_prompt = None
        self.training_sequence = []
        self.app_state = "locker"

    def set_message(self, text, duration=1.0):
        self.message = text
        self.message_until = time.time() + duration

    def show_fight_help(self, duration=8.0):
        self.fight_help_until = time.time() + duration

    def register_offense_feedback(self, move, now, blocked=False, broke_guard=False, chip_damage=0):
        motion = self.last_detected_motion or {}
        timing_bonus = self.current_prompt_timing
        pounds = int(
            95
            + max(0.0, motion.get("planar", 0.0)) * 220
            + max(0.0, motion.get("dz", 0.0)) * 330
            + max(0.0, -motion.get("dy", 0.0)) * 200
            + max(0.0, abs(motion.get("dx", 0.0))) * 140
            + self.career.stats["power"] * 7
            + timing_bonus * 90
        )
        critical = pounds >= 285 or timing_bonus > 0.82
        damage = 1 + int(pounds >= 170) + int(pounds >= 245) + int(critical)
        if blocked and not broke_guard:
            damage = chip_damage
            critical = False
        elif broke_guard:
            damage += 1
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
        self.last_action_feedback = {
            "text": f"{move['label']}  {pounds} lb  -{damage} HP{crit_text}",
            "until": now + 1.2,
            "color": GOLD if critical or damage >= 3 else ORANGE if damage >= 2 else CYAN,
        }
        if blocked and damage == 0:
            self.audio.play_sfx("sfx/block.wav", throttle=0.04)
        else:
            self.audio.play_sfx("sfx/impact_heavy.wav" if damage >= 3 or broke_guard else "sfx/impact_light.wav", throttle=0.04)
        return {"damage": damage, "blocked": blocked, "broke_guard": broke_guard}

    def current_gap(self):
        speedup = 0.06 * min(self.actions_cleared, 10) + 0.12 * max(self.round_index - 1, 0)
        base_gap = max(0.50, 1.40 - speedup)
        return base_gap * self.active_speed_scale()

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
        if rank >= 1 and random.random() < 0.35:
            families.append("hook")
        if rank >= 3 and random.random() < 0.55:
            families.append("uppercut")
        family = random.choice(families)
        if family == "straight":
            response = random.choice(["slip_left", "slip_right"])
            attack_move_id = random.choice(["left_straight", "right_straight"])
        elif family == "hook":
            response = "duck"
            attack_move_id = random.choice(["left_hook", "right_hook"])
        else:
            response = "guard"
            attack_move_id = random.choice(["left_uppercut", "right_uppercut"])
        chip = 0
        if family == "uppercut" and rank >= 3:
            chip = 1
        return {
            "move": MOVE_BY_ID[response],
            "attack_move_id": attack_move_id,
            "family": family,
            "chip_on_block": chip,
        }

    def choose_enemy_block(self):
        rank = self.arena_rank()
        if rank < 2:
            return None
        styles = ["wide_gate", "tight_shell"]
        if rank >= 3:
            styles.append("elbows_high")
        if rank >= 4:
            styles.append("left_post")
        style = random.choice(styles)
        rule = BLOCK_COUNTER_RULES[style]
        return {
            "style": style,
            "counter": rule["counter"],
            "counter_moves": list(rule["counter_moves"]),
            "label": rule["label"],
            "hint": rule["hint"],
        }

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
        combo_chance = 0.0 if rank == 0 else 0.28 + rank * 0.08
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
                        "issued_at": now,
                        "expires_at": now + REACTION_TIME * max(0.72, 1.0 - rank * 0.05),
                        "chip_on_block": attack["chip_on_block"],
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
            self.enemy_attack_pose = self.enemy_block["style"] if self.enemy_block else self.prompt.get("enemy_attack_id")
            return

        offense_chance = 0.75 - self.arena_rank() * 0.08
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
            self.enemy_block = None
            self.enemy_attack_pose = attack["attack_move_id"]
            self.prompt = {
                "type": "defense",
                "move": attack["move"],
                "enemy_attack_id": attack["attack_move_id"],
                "issued_at": now,
                "expires_at": expires_at,
                "chip_on_block": attack["chip_on_block"],
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
        min_path = 0.17 if strict else 0.13
        min_displacement = 0.13 if strict else 0.10
        min_peak_speed = 1.55 if strict else 1.15
        min_energy = 0.34 if strict else 0.25
        return (
            motion["path_len"] >= min_path
            and motion["net_displacement"] >= min_displacement
            and motion["peak_speed"] >= min_peak_speed
            and motion["motion_energy"] >= min_energy
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
        motion = self.summarize_wrist_motion(move["hand"], pose_data)
        if motion is None or not self.motion_is_active(motion, strict=strict):
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
                and (recoil_ok or abs(motion["dx"]) > hook_dx * 1.35)
            )
            if matched:
                self.last_detected_motion = motion
            return matched

        if move_id.endswith("straight"):
            reach_ok = motion["reach_x"] > straight_reach if move["hand"] == "left" else motion["reach_x"] < -straight_reach
            straight_score = 0
            if motion["dz"] > straight_dz:
                straight_score += 1
            if motion["mid_dz"] > straight_mid_dz:
                straight_score += 1
            if reach_ok:
                straight_score += 1
            if abs(motion["dx"]) < 0.24 and abs(motion["dy"]) < 0.28:
                straight_score += 1
            if motion["planar"] < 0.46:
                straight_score += 1
            matched = straight_score >= 3 and (not strict or profile_match(move_id, motion, self.learned_profiles.get(move_id)))
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
            matched = uppercut_score >= 4 and (not strict or profile_match(move_id, motion, self.learned_profiles.get(move_id)))
            if matched:
                self.last_detected_motion = motion
            return matched

        return False

    def detect_target_hit(self, pose_data, prompt):
        move_id = prompt["move_id"]
        if not self.detect_offense_move(move_id, pose_data, strict=False):
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
        if move_id in ("left_hook", "right_hook"):
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
            if self.detect_menu_move("right_hook", pose_data):
                self.menu_action_cooldown_until = now + 0.85
                self.app_state = "arena_map"
                self.trigger_menu_feedback("BACK TO MAP", GOLD, now)
                return
            if self.detect_menu_move("left_hook", pose_data):
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

        if self.detect_menu_move("left_hook", pose_data):
            self.menu_action_cooldown_until = now + 0.85
            self.trigger_menu_feedback("CONFIRM", GOLD, now)
            self.audio.play_sfx("sfx/menu.wav", throttle=0.05)
            self.handle_menu_confirm()
            return

        if self.detect_menu_move("right_hook", pose_data):
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
            self.set_message("Tutorial complete. Fight starts now.", 1.6)
            self.start_round(1)

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
                self.set_message(f"{move['label']} saved you, but the shot still pressured you for {chip} HP.", 1.0)
                self.audio.play_sfx("sfx/impact_light.wav", throttle=0.05)
            else:
                self.set_message(f"{move['label']} successful.", 0.85)
            self.audio.play_sfx("sfx/block.wav", throttle=0.05)
            self.enemy_attack_pose = None
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
                penalty = 2 if self.prompt.get("enemy_attack_id", "").endswith("uppercut") or self.arena_rank() >= 3 else 1
                self.player_hp = max(0, self.player_hp - penalty)
                self.damage_flash_until = now + 0.22
                self.match_taken_hits += 1
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
            prompt_strict = False
            if now - self.last_punch_at > PUNCH_COOLDOWN and self.detect_offense_move(move["id"], pose_data, strict=prompt_strict):
                self.match_thrown_punches += 1
                duration = max(0.001, self.prompt["expires_at"] - self.prompt["issued_at"])
                self.current_prompt_timing = max(0.0, min(1.0, 1.0 - ((self.prompt["expires_at"] - now) / duration)))
                self.last_punch_at = now
                self.wrist_history[move["hand"]].clear()
                self.resolve_command_success(move, False, now)
                return
            if self.prompt.get("enemy_block") and now - self.last_punch_at > PUNCH_COOLDOWN:
                for alt_move_id in self.prompt["enemy_block"].get("counter_moves", []):
                    if alt_move_id != move["id"] and self.detect_offense_move(alt_move_id, pose_data, strict=False):
                        self.match_thrown_punches += 1
                        alt_move = MOVE_BY_ID[alt_move_id]
                        duration = max(0.001, self.prompt["expires_at"] - self.prompt["issued_at"])
                        self.current_prompt_timing = max(0.0, min(1.0, 1.0 - ((self.prompt["expires_at"] - now) / duration)))
                        self.last_punch_at = now
                        self.wrist_history[alt_move["hand"]].clear()
                        self.resolve_command_success(alt_move, False, now)
                        return
        else:
            if self.defense_success(defense, move["id"]):
                duration = max(0.001, self.prompt["expires_at"] - self.prompt["issued_at"])
                timing = max(0.0, min(1.0, 1.0 - ((self.prompt["expires_at"] - now) / duration)))
                self.last_action_feedback = {
                    "text": f"{move['label']} vs {MOVE_BY_ID[self.prompt['enemy_attack_id']]['label']}  REACTION {int(100 + timing * 220)}",
                    "until": now + 1.0,
                    "color": GREEN,
                }
                self.resolve_command_success(move, True, now)
                return

        if now >= self.prompt["expires_at"]:
            self.resolve_timeout(now)

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

        if now - self.last_punch_at > PUNCH_COOLDOWN and self.detect_target_hit(pose_data, self.target_prompt):
            self.current_prompt_timing = 0.5
            self.last_punch_at = now
            self.resolve_target_success(now)
            return

        if now >= self.target_prompt["expires_at"]:
            self.resolve_timeout(now)

    def build_training_sequence(self, stat_name):
        if stat_name == "power":
            return [
                {"type": "offense", "move_id": "left_straight"},
                {"type": "offense", "move_id": "right_straight"},
                {"type": "offense", "move_id": "right_hook"},
                {"type": "offense", "move_id": "left_hook"},
                {"type": "offense", "move_id": "right_uppercut"},
            ]
        if stat_name == "stamina":
            return [
                {"type": "offense", "move_id": "left_straight"},
                {"type": "offense", "move_id": "right_straight"},
                {"type": "offense", "move_id": "left_straight"},
                {"type": "offense", "move_id": "right_straight"},
                {"type": "offense", "move_id": "left_hook"},
                {"type": "offense", "move_id": "right_hook"},
            ]
        return [
            {"type": "defense", "move_id": "slip_left", "enemy_attack_id": "right_straight"},
            {"type": "defense", "move_id": "slip_right", "enemy_attack_id": "left_straight"},
            {"type": "defense", "move_id": "guard", "enemy_attack_id": "left_hook"},
            {"type": "defense", "move_id": "guard", "enemy_attack_id": "right_uppercut"},
        ]

    def spawn_training_prompt(self, now, frame_w, frame_h):
        if not self.training_sequence:
            self.training_sequence = self.build_training_sequence(self.training_mode)
        template = self.training_sequence[(self.training_hits + self.training_misses) % len(self.training_sequence)]
        expires_at = now + (1.65 if self.training_mode != "agility" else 1.35)
        prompt = dict(template)
        prompt["issued_at"] = now
        prompt["expires_at"] = expires_at
        if prompt["type"] == "offense":
            move = MOVE_BY_ID[prompt["move_id"]]
            prompt["move"] = move
            target_key = self.target_key_for_move(move["id"])
            size = int(min(frame_w, frame_h) * 0.17)
            lane = (self.training_hits + self.training_misses) % 3
            lanes_x = [int(frame_w * 0.30), int(frame_w * 0.50), int(frame_w * 0.70)]
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

        if prompt["type"] == "offense":
            if now - self.last_punch_at > PUNCH_COOLDOWN and self.detect_target_hit(pose_data, prompt):
                duration = max(0.001, prompt["expires_at"] - prompt["issued_at"])
                timing = max(0.0, min(1.0, (prompt["expires_at"] - now) / duration))
                score = 0.9 + timing * (0.9 if self.training_mode == "power" else 0.6)
                self.training_score_accum += score
                self.training_samples += 1
                self.training_hits += 1
                self.training_streak += 1
                self.last_punch_at = now
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
                self.enemy_attack_pose = None
                self.training_prompt = None

        if self.training_prompt and now >= self.training_prompt["expires_at"]:
            self.training_misses += 1
            self.training_streak = 0
            self.training_samples += 1
            self.set_message("Training miss. Reset and hit the next prompt cleanly.", 0.8)
            self.audio.play_sfx("sfx/whoosh.wav", throttle=0.04)
            self.enemy_attack_pose = None
            self.training_prompt = None
        if time.time() - self.training_started_at >= self.training_duration:
            self.finish_training()

    def update_round_state(self):
        if self.app_state != "fight" or self.phase == "tutorial" or self.match_over:
            return

        if self.enemy_hp <= 0:
            self.player_rounds += 1
            if self.player_rounds >= ROUNDS_TO_WIN:
                self.match_over = True
                self.match_winner = "PLAYER"
                self.last_payout = self.career.apply_match_result(
                    self.active_arena,
                    True,
                    self.match_landed_hits,
                    self.combo_peak,
                    max(self.player_hp, 0) / max(1, self.fight_player_max_hp),
                )
                self.save_progress()
                self.match_settled = True
                self.set_message(f"You win by KO. Payout ${self.last_payout}.", 8.0)
                self.audio.play_sfx("sfx/cheer.wav", throttle=0.2)
            elif self.round_index == 1:
                self.start_round(2)
            else:
                self.start_round(1)
            return

        if self.player_hp <= 0:
            self.enemy_rounds += 1
            if self.enemy_rounds >= ROUNDS_TO_WIN:
                self.match_over = True
                self.match_winner = "OPPONENT"
                self.last_payout = self.career.apply_match_result(
                    self.active_arena,
                    False,
                    self.match_landed_hits,
                    self.combo_peak,
                    0.0,
                )
                self.save_progress()
                self.match_settled = True
                self.set_message("Opponent wins by KO. Entry fee and upkeep charged.", 8.0)
                self.audio.play_sfx("sfx/cheer.wav", throttle=0.2)
            elif self.round_index == 1:
                self.start_round(2)
            else:
                self.start_round(1)

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

    def draw_bar(self, frame, label, x, y, hp, max_hp, color):
        bar_w = 260
        bar_h = 24 if label == "YOU" else 48
        cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_DUPLEX, 0.8, WHITE, 1, cv2.LINE_AA)
        cv2.rectangle(frame, (x, y), (x + bar_w, y + bar_h), (40, 40, 55), -1)
        fill = int(bar_w * (hp / max_hp))
        cv2.rectangle(frame, (x, y), (x + fill, y + bar_h), color, -1)
        cv2.rectangle(frame, (x, y), (x + bar_w, y + bar_h), WHITE, 1)

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

    def opponent_anchor(self, frame):
        h, w = frame.shape[:2]
        return int(w * 0.50), int(h * 0.53)

    def draw_opponent(self, frame, now):
        cx, cy = self.opponent_anchor(frame)
        recoil = 0
        if now < self.impact_until:
            recoil = int(18 * math.sin((self.impact_until - now) * 20))

        head = (cx + recoil, cy - 135)
        torso_top = (cx + recoil, cy - 92)
        torso_bottom = (cx + recoil, cy + 30)
        color = (190, 205, 235)
        cv2.circle(frame, head, 28, color, 3, cv2.LINE_AA)
        cv2.line(frame, torso_top, torso_bottom, color, 4, cv2.LINE_AA)
        
        l_shoulder = (cx - 30 + recoil, cy - 54)
        r_shoulder = (cx + 30 + recoil, cy - 54)
        l_elbow = (cx - 52 + recoil, cy - 20)
        r_elbow = (cx + 52 + recoil, cy - 20)
        left_arm = (cx - 52 + recoil, cy - 42)
        right_arm = (cx + 52 + recoil, cy - 18)
        
        pose_name = self.enemy_attack_pose
        if pose_name == "wide_gate":
            l_elbow = (cx - 100 + recoil, cy - 40)
            r_elbow = (cx + 100 + recoil, cy - 40)
            left_arm = (cx - 130 + recoil, cy - 90)
            right_arm = (cx + 130 + recoil, cy - 90)
        elif pose_name == "tight_shell":
            l_elbow = (cx - 15 + recoil, cy - 30)
            r_elbow = (cx + 15 + recoil, cy - 30)
            left_arm = (cx - 12 + recoil, cy - 115)
            right_arm = (cx + 12 + recoil, cy - 115)
        elif pose_name == "left_post":
            l_elbow = (cx - 30 + recoil, cy - 60)
            r_elbow = (cx + 60 + recoil, cy - 20)
            left_arm = (cx - 6 + recoil, cy - 120)
            right_arm = (cx + 70 + recoil, cy - 50)
        elif pose_name == "elbows_high":
            l_elbow = (cx - 60 + recoil, cy - 90)
            r_elbow = (cx + 60 + recoil, cy - 90)
            left_arm = (cx - 26 + recoil, cy - 135)
            right_arm = (cx + 26 + recoil, cy - 135)
        elif pose_name == "left_straight":
            l_elbow = (cx - 80 + recoil, cy - 54)
            left_arm = (cx - 126 + recoil, cy - 54)
        elif pose_name == "right_straight":
            r_elbow = (cx + 80 + recoil, cy - 42)
            right_arm = (cx + 132 + recoil, cy - 42)
        elif pose_name == "left_hook":
            l_elbow = (cx - 90 + recoil, cy - 40)
            left_arm = (cx - 118 + recoil, cy - 86)
        elif pose_name == "right_hook":
            r_elbow = (cx + 90 + recoil, cy - 40)
            right_arm = (cx + 118 + recoil, cy - 86)
        elif pose_name == "left_uppercut":
            l_elbow = (cx - 30 + recoil, cy + 20)
            left_arm = (cx - 10 + recoil, cy + 18)
        elif pose_name == "right_uppercut":
            r_elbow = (cx + 30 + recoil, cy + 20)
            right_arm = (cx + 10 + recoil, cy + 18)
            
        cv2.line(frame, l_shoulder, l_elbow, color, 4, cv2.LINE_AA)
        cv2.line(frame, l_elbow, left_arm, color, 4, cv2.LINE_AA)
        cv2.line(frame, r_shoulder, r_elbow, color, 4, cv2.LINE_AA)
        cv2.line(frame, r_elbow, right_arm, color, 4, cv2.LINE_AA)
        cv2.line(frame, (cx - 20 + recoil, cy + 30), (cx - 45 + recoil, cy + 96), color, 4, cv2.LINE_AA)
        cv2.line(frame, (cx + 20 + recoil, cy + 30), (cx + 45 + recoil, cy + 96), color, 4, cv2.LINE_AA)

        enemy_glove = self.assets["gloves"].get("enemy_glove_rgba")
        if enemy_glove is not None:
            mirrored = cv2.flip(enemy_glove, 1)
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
                left_angle = -20
                right_angle = 20
            self.overlay_rgba(frame, mirrored, left_arm, scale=0.28, angle=left_angle, alpha_scale=0.94)
            self.overlay_rgba(frame, enemy_glove, right_arm, scale=0.28, angle=right_angle, alpha_scale=0.94)

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
            cv2.putText(frame, f"POWER LEVEL: {self.power_level}", (cx - 122, cy - 92), cv2.FONT_HERSHEY_DUPLEX, 0.68, GOLD, 2, cv2.LINE_AA)
        elif self.enemy_block:
            cv2.putText(frame, self.enemy_block["label"], (cx - 84, cy - 98), cv2.FONT_HERSHEY_DUPLEX, 0.58, ORANGE, 2, cv2.LINE_AA)

    def draw_player_gloves(self, frame):
        sprite = self.assets["gloves"].get("player_glove_rgba")
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
        if prompt["type"] == "offense":
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
            cv2.putText(frame, prompt["move"]["label"], (frame.shape[1] // 2 - 130, 216), cv2.FONT_HERSHEY_DUPLEX, 0.82, WHITE, 2, cv2.LINE_AA)
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
        line1 = "Straight incoming: slip left or right."
        line2 = "Hooks and uppercuts: high guard."
        line3 = "Wide gloves -> straight   Tight gloves -> hook   Elbows high -> uppercut."
        if self.prompt and self.prompt.get("enemy_block"):
            block = self.prompt["enemy_block"]
            line1 = f"Rival shows {block['label']}."
            line2 = block["hint"]
            line3 = "Follow the center prompt and match the opening."
        elif self.prompt and self.prompt.get("enemy_attack_id"):
            attack = MOVE_BY_ID[self.prompt["enemy_attack_id"]]
            line1 = f"Incoming {attack['label']}."
            line2 = f"Defend with {self.prompt['move']['label']}."
            line3 = "Beat the timer to avoid damage."
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
        x1, y1, x2, y2 = w // 2 - 220, 122, w // 2 + 220, 292
        self.tech_panel(frame, (x1, y1, x2, y2), MAGENTA, fill=(12, 12, 24), alpha=0.86)
        self.draw_move_icon(frame, move["id"], (w // 2, y1 + 78))
        cv2.putText(frame, move["label"], (w // 2 - 135, y1 + 140), cv2.FONT_HERSHEY_DUPLEX, 0.94, WHITE, 2, cv2.LINE_AA)
        cv2.putText(frame, move["hint"], (w // 2 - 170, y1 + 170), cv2.FONT_HERSHEY_SIMPLEX, 0.58, SOFT, 2, cv2.LINE_AA)
        if self.prompt:
            if self.prompt["type"] == "defense" and self.prompt.get("enemy_attack_id"):
                attack = MOVE_BY_ID[self.prompt["enemy_attack_id"]]
                cv2.putText(frame, f"INCOMING: {attack['label']}", (w // 2 - 154, y1 + 198), cv2.FONT_HERSHEY_SIMPLEX, 0.56, GOLD, 2, cv2.LINE_AA)
            elif self.prompt["type"] == "offense" and self.prompt.get("enemy_block"):
                block = self.prompt["enemy_block"]
                cv2.putText(frame, block["label"], (w // 2 - 88, y1 + 198), cv2.FONT_HERSHEY_SIMPLEX, 0.58, ORANGE, 2, cv2.LINE_AA)
                cv2.putText(frame, block["hint"], (w // 2 - 196, y1 + 224), cv2.FONT_HERSHEY_SIMPLEX, 0.48, SOFT, 1, cv2.LINE_AA)
        remain = max(0.0, expires_at - time.time())
        fill_w = int((x2 - x1 - 24) * (remain / REACTION_TIME))
        timer_color = GREEN if remain > 0.9 else GOLD if remain > 0.4 else RED
        cv2.rectangle(frame, (x1 + 12, y2 - 26), (x2 - 12, y2 - 10), (45, 45, 60), -1)
        cv2.rectangle(frame, (x1 + 12, y2 - 26), (x1 + 12 + fill_w, y2 - 10), timer_color, -1)

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
        self.draw_bar(frame, "YOU", 40, 50, self.player_hp, self.fight_player_max_hp, GREEN)
        self.draw_bar(frame, "RIVAL", w - 360, 50, self.enemy_hp, self.fight_enemy_max_hp, MAGENTA)
        rounds_text = f"ROUND {self.round_index}   YOU {self.player_rounds} - {self.enemy_rounds} RIVAL"
        cv2.putText(frame, rounds_text, (w // 2 - 180, 48), cv2.FONT_HERSHEY_DUPLEX, 0.78, WHITE, 1, cv2.LINE_AA)
        phase_label = "Tutorial" if self.phase == "tutorial" else "Command Mode" if self.phase == "command_round" else "Target Mode"
        pace_text = f"{phase_label}   Gap {self.current_gap():.2f}s   Guard {'ON' if defense['guard'] else 'OFF'}"
        cv2.putText(frame, pace_text, (w // 2 - 180, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.68, SOFT, 2, cv2.LINE_AA)
        arena = self.active_arena if self.app_state == "fight" else self.current_arena_for_ui()
        cv2.putText(frame, f"{arena['name'].upper()}  |  {arena['scene']}", (34, 118), cv2.FONT_HERSHEY_SIMPLEX, 0.60, CYAN, 2, cv2.LINE_AA)
        combo_pulse = 1.0 + 0.08 * math.sin(time.time() * 10.0)
        combo_color = GOLD if time.time() < self.combo_until else SOFT
        cv2.putText(frame, f"COMBO x{self.combo_count}", (34, 144), cv2.FONT_HERSHEY_DUPLEX, 0.82 * combo_pulse, combo_color, 3, cv2.LINE_AA)
        if self.last_action_feedback and time.time() < self.last_action_feedback["until"]:
            cv2.putText(frame, self.last_action_feedback["text"], (34, 176), cv2.FONT_HERSHEY_DUPLEX, 0.66, self.last_action_feedback["color"], 3, cv2.LINE_AA)
        if time.time() < self.message_until:
            cv2.putText(frame, self.message, (34, h - 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, GOLD, 3, cv2.LINE_AA)

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
            cv2.putText(frame, "Right Hook back to map  |  Left Hook rematch", (w // 2 - 200, h // 2 + 190), cv2.FONT_HERSHEY_SIMPLEX, 0.68, WHITE, 3, cv2.LINE_AA)
        elif self.phase == "command_round" and time.time() < self.round_freeze_until:
            cv2.putText(frame, f"ROUND {self.round_index}", (w // 2 - 150, h // 2), cv2.FONT_HERSHEY_DUPLEX, 2.0, GOLD, 4, cv2.LINE_AA)
            cv2.putText(frame, "GET READY", (w // 2 - 80, h // 2 + 50), cv2.FONT_HERSHEY_DUPLEX, 0.9, WHITE, 2, cv2.LINE_AA)

    def draw_pose(self, frame, landmarks):
        if landmarks is None:
            return
        self.mp_drawing.draw_landmarks(
            frame,
            landmarks,
            mp.solutions.pose.POSE_CONNECTIONS,
            landmark_drawing_spec=self.mp_drawing.DrawingSpec(color=(245, 245, 255), thickness=2, circle_radius=2),
            connection_drawing_spec=self.mp_drawing.DrawingSpec(color=(110, 180, 255), thickness=2),
        )

    def draw_tutorial_panel(self, frame):
        if self.phase != "tutorial" or self.tutorial_step >= len(TUTORIAL_SEQUENCE):
            return
        move_id = TUTORIAL_SEQUENCE[self.tutorial_step]
        move = MOVE_BY_ID[move_id]
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = w // 2 - 250, 120, w // 2 + 250, 318
        self.tech_panel(frame, (x1, y1, x2, y2), ORANGE, fill=(12, 12, 24), alpha=0.88)
        self.draw_move_icon(frame, move_id, (w // 2, y1 + 78))
        cv2.putText(frame, f"CAPTURE {move['label']}", (w // 2 - 198, y1 + 146), cv2.FONT_HERSHEY_DUPLEX, 0.92, WHITE, 3, cv2.LINE_AA)
        cv2.putText(frame, move["hint"], (w // 2 - 190, y1 + 184), cv2.FONT_HERSHEY_SIMPLEX, 0.7, GOLD, 3, cv2.LINE_AA)
        current_rep = self.tutorial_samples.get(move_id, 0)
        needed = tutorial_rep_target(move_id)
        progress = f"Capture {current_rep}/{needed}   Build your own motion profile"
        cv2.putText(frame, progress, (w // 2 - 172, y2 - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.62, SOFT, 2, cv2.LINE_AA)

    def draw_hub(self, frame):
        h, w = frame.shape[:2]
        cv2.putText(frame, "CAREER MAP", (40, 64), cv2.FONT_HERSHEY_DUPLEX, 1.2, WHITE, 2, cv2.LINE_AA)
        cv2.putText(
            frame,
            f"Cash ${self.career.cash}   Points {self.career.points}   W-L {self.career.record['wins']}-{self.career.record['losses']}   Rank #{self.career.current_world_rank()}",
            (40, 98),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.74,
            GOLD,
            2,
            cv2.LINE_AA,
        )
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
            cv2.putText(frame, label.upper(), (x1 + 34, y1 + 78), cv2.FONT_HERSHEY_DUPLEX, 0.98, WHITE, 3, cv2.LINE_AA)
        arena = self.current_arena_for_ui()
        self.tech_panel(frame, (40, h - 176, 540, h - 76), CYAN, fill=(10, 14, 24), alpha=0.76)
        cv2.putText(frame, f"UP NEXT: {arena['name'].upper()}", (56, h - 136), cv2.FONT_HERSHEY_DUPLEX, 0.82, WHITE, 2, cv2.LINE_AA)
        cv2.putText(frame, arena["challenge"], (56, h - 102), cv2.FONT_HERSHEY_SIMPLEX, 0.58, SOFT, 2, cv2.LINE_AA)
        cv2.putText(frame, "Slip Left / Right to move. Left Hook confirm. Right Hook back.", (40, h - 46), cv2.FONT_HERSHEY_SIMPLEX, 0.68, WHITE, 3, cv2.LINE_AA)

    def draw_arena_map(self, frame):
        h, w = frame.shape[:2]
        cv2.putText(frame, "FIGHT MAP", (40, 64), cv2.FONT_HERSHEY_DUPLEX, 1.2, WHITE, 2, cv2.LINE_AA)
        x_positions = np.linspace(110, w - 110, num=len(CAREER_ARENAS)).astype(int)
        y_wave = [h // 2 + offset for offset in (-40, 30, -10, 26, -32)]
        for idx, arena in enumerate(CAREER_ARENAS):
            x = int(x_positions[idx])
            y = int(y_wave[idx])
            unlocked = self.career.is_unlocked(arena["id"])
            selected = idx == self.selected_arena_index
            color = GOLD if selected else GREEN if unlocked else SOFT
            cv2.circle(frame, (x, y), 30 if selected else 22, color, 3, cv2.LINE_AA)
            cv2.putText(frame, arena["name"].upper(), (x - 42, y + 56), cv2.FONT_HERSHEY_DUPLEX, 0.5, WHITE, 1, cv2.LINE_AA)
            cv2.putText(frame, arena["scene"], (x - 74, y + 76), cv2.FONT_HERSHEY_SIMPLEX, 0.42, SOFT, 1, cv2.LINE_AA)
            status = "READY" if self.career.can_enter(arena) else "LOCKED" if not unlocked else f"Need ${arena['entry_fee']}"
            cv2.putText(frame, status, (x - 40, y - 38), cv2.FONT_HERSHEY_SIMPLEX, 0.46, color, 1, cv2.LINE_AA)
            if idx < len(CAREER_ARENAS) - 1:
                cv2.line(frame, (x + 26, y), (int(x_positions[idx + 1]) - 26, int(y_wave[idx + 1])), CYAN, 2, cv2.LINE_AA)
        arena = CAREER_ARENAS[self.selected_arena_index]
        preview = self.assets["backgrounds"].get(arena["id"])
        panel = (w - 430, 138, w - 34, h - 110)
        self.tech_panel(frame, panel, GOLD, fill=(10, 14, 24), alpha=0.82)
        resized = self.resize_cover(preview, panel[2] - panel[0] - 20, 180)
        if resized is not None:
            frame[panel[1] + 14 : panel[1] + 194, panel[0] + 10 : panel[2] - 10] = resized
        cv2.putText(frame, arena["name"].upper(), (panel[0] + 18, panel[1] + 230), cv2.FONT_HERSHEY_DUPLEX, 0.80, WHITE, 2, cv2.LINE_AA)
        cv2.putText(frame, arena["unlock_rule"], (panel[0] + 18, panel[1] + 264), cv2.FONT_HERSHEY_SIMPLEX, 0.60, GOLD, 2, cv2.LINE_AA)
        cv2.putText(frame, arena["challenge"], (panel[0] + 18, panel[1] + 302), cv2.FONT_HERSHEY_SIMPLEX, 0.54, SOFT, 2, cv2.LINE_AA)
        cv2.putText(frame, f"Entry ${arena['entry_fee']}   Upkeep ${arena['upkeep']}", (panel[0] + 18, panel[1] + 338), cv2.FONT_HERSHEY_SIMPLEX, 0.60, WHITE, 2, cv2.LINE_AA)
        cv2.putText(frame, "Slip Left / Right to choose arena. Left Hook enter fight. Right Hook back.", (40, h - 46), cv2.FONT_HERSHEY_SIMPLEX, 0.68, WHITE, 3, cv2.LINE_AA)

    def draw_locker_room(self, frame):
        h, w = frame.shape[:2]
        cv2.putText(frame, "LOCKER ROOM", (40, 64), cv2.FONT_HERSHEY_DUPLEX, 1.2, WHITE, 2, cv2.LINE_AA)
        belt_text = "STATE BELT: OWNED" if self.career.state_belt_won else "STATE BELT: LOCKED"
        cv2.putText(frame, f"Cash ${self.career.cash}   Sponsor clears {self.career.completed_tasks}   {belt_text}", (40, 98), cv2.FONT_HERSHEY_SIMPLEX, 0.72, GOLD, 2, cv2.LINE_AA)
        panel_x1, panel_y1 = 40, 140
        self.tech_panel(frame, (panel_x1, panel_y1, w - 40, h - 70), CYAN, fill=(16, 18, 28), alpha=0.82)
        stats = self.career.stats
        lines = [
            f"Power   {stats['power']:.1f}   Cost ${self.career.train_cost('power')}",
            f"Stamina {stats['stamina']:.1f}   Cost ${self.career.train_cost('stamina')}",
            f"Agility {stats['agility']:.1f}   Cost ${self.career.train_cost('agility')}",
            f"Active Sponsor Goal: {self.career.sponsor_tasks[self.career.completed_tasks % len(self.career.sponsor_tasks)]}",
            f"Selected Arena: {CAREER_ARENAS[self.selected_arena_index]['name']}  Entry ${CAREER_ARENAS[self.selected_arena_index]['entry_fee']}  Upkeep ${CAREER_ARENAS[self.selected_arena_index]['upkeep']}",
            f"World Rank Estimate: #{self.career.current_world_rank()}",
        ]
        for idx, text in enumerate(lines):
            cv2.putText(frame, text, (68, 188 + idx * 54), cv2.FONT_HERSHEY_DUPLEX if idx < 3 else cv2.FONT_HERSHEY_SIMPLEX, 0.72 if idx < 3 else 0.62, WHITE if idx < 3 else SOFT, 1, cv2.LINE_AA)
        glove_sheet = self.assets["sheets"].get("gloves_sheet")
        if glove_sheet is not None:
            preview = self.resize_cover(glove_sheet, 360, 210)
            frame[panel_y1 + 32 : panel_y1 + 242, w - 420 : w - 60] = preview
        cv2.putText(frame, "Right Hook to go back. Open Training from the hub to start drills.", (50, h - 34), cv2.FONT_HERSHEY_SIMPLEX, 0.68, WHITE, 3, cv2.LINE_AA)

    def draw_training_menu(self, frame):
        h, w = frame.shape[:2]
        cv2.putText(frame, "TRAINING GYM", (40, 64), cv2.FONT_HERSHEY_DUPLEX, 1.2, WHITE, 2, cv2.LINE_AA)
        cv2.putText(frame, f"Cash ${self.career.cash}", (40, 98), cv2.FONT_HERSHEY_SIMPLEX, 0.74, GOLD, 2, cv2.LINE_AA)
        base_y = h // 2 - 120
        for idx, label in enumerate(TRAINING_MENU):
            y1 = base_y + idx * 95
            y2 = y1 + 72
            selected = idx == self.selected_training_index
            border = GOLD if selected else CYAN
            stat_key = label.lower()
            cost = self.career.train_cost(stat_key)
            self.tech_panel(frame, (w // 2 - 240, y1, w // 2 + 240, y2), border, fill=(16, 18, 28), alpha=0.82, line=3 if selected else 2)
            cv2.putText(frame, label.upper(), (w // 2 - 196, y1 + 44), cv2.FONT_HERSHEY_DUPLEX, 0.88, WHITE, 3, cv2.LINE_AA)
            cv2.putText(frame, f"Cost ${cost}", (w // 2 + 68, y1 + 44), cv2.FONT_HERSHEY_SIMPLEX, 0.7, SOFT, 3, cv2.LINE_AA)
        self.draw_target_preview_card(frame, self.assets["targets"].get("jab_target"), (40, 150, 300, 318), "JAB TARGET", CYAN)
        self.draw_target_preview_card(frame, self.assets["targets"].get("hook_target"), (320, 150, 580, 318), "HOOK TARGET", GREEN)
        self.draw_target_preview_card(frame, self.assets["targets"].get("uppercut_target"), (40, 336, 300, 504), "UPPERCUT TARGET", GOLD)
        self.draw_target_preview_card(frame, self.assets["targets"].get("body_target"), (320, 336, 580, 504), "BODY SHIELD", ORANGE)
        cv2.putText(frame, "Slip Left / Right to select. Left Hook start drill. Right Hook back.", (40, h - 46), cv2.FONT_HERSHEY_SIMPLEX, 0.68, WHITE, 3, cv2.LINE_AA)

    def draw_training_overlay(self, frame):
        if self.app_state != "training" or self.training_mode is None:
            return
        h, w = frame.shape[:2]
        remaining = max(0.0, self.training_duration - (time.time() - self.training_started_at))
        title = f"{self.training_mode.upper()} DRILL"
        hint = {
            "power": "Throw hard clean punches into the camera lane",
            "stamina": "Keep a steady rhythm of combos without stopping",
            "agility": "Slip left/right or guard as fast as you can",
        }[self.training_mode]
        combo_goal = {
            "power": "Combo Goal: Left Straight > Right Straight > Right Hook",
            "stamina": "Combo Goal: Jab > Cross > Jab > Cross nonstop",
            "agility": "Combo Goal: Slip Left > Slip Right > Guard reset",
        }[self.training_mode]
        self.tech_panel(frame, (w // 2 - 250, 24, w // 2 + 250, 112), ORANGE, fill=(12, 12, 24), alpha=0.86)
        cv2.putText(frame, title, (w // 2 - 120, 54), cv2.FONT_HERSHEY_DUPLEX, 0.96, WHITE, 3, cv2.LINE_AA)
        cv2.putText(frame, hint, (w // 2 - 205, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.62, GOLD, 3, cv2.LINE_AA)
        cv2.putText(frame, combo_goal, (w // 2 - 214, 108), cv2.FONT_HERSHEY_SIMPLEX, 0.56, CYAN, 2, cv2.LINE_AA)
        cv2.putText(frame, f"{remaining:0.1f}s", (w // 2 - 36, 132), cv2.FONT_HERSHEY_DUPLEX, 0.8, WHITE, 2, cv2.LINE_AA)
        cv2.putText(frame, f"Hits {self.training_hits}   Misses {self.training_misses}   Streak x{self.training_streak}", (42, 124), cv2.FONT_HERSHEY_SIMPLEX, 0.62, WHITE, 2, cv2.LINE_AA)
        active_cards = [
            ("jab_target", (w - 320, 140, w - 40, 286), "JAB TARGET", CYAN),
            ("hook_target", (w - 320, 304, w - 40, 450), "HOOK TARGET", GREEN),
            ("uppercut_target", (w - 320, 468, w - 40, 614), "UPPERCUT", GOLD),
        ]
        for key, rect, label, accent in active_cards:
            self.draw_target_preview_card(frame, self.assets["targets"].get(key), rect, label, accent)

    def run(self):
        while self.cap.isOpened():
            ok, frame = self.cap.read()
            if not ok:
                break

            now = time.time()
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
                    if self.app_state in ("hub", "arena_map", "locker", "training_menu") or (self.app_state == "fight" and self.match_over):
                        self.handle_menu_gestures(pose_data, defense, now)
                    if self.app_state == "fight":
                        if self.phase == "tutorial":
                            self.run_tutorial(pose_data, defense, now)
                        elif self.phase == "command_round":
                            self.process_command_round(pose_data, defense, now)
                        elif self.phase == "target_round":
                            self.process_target_round(pose_data, now, frame_w, frame_h)
                        self.update_round_state()
                    elif self.app_state == "training":
                        self.process_training(pose_data, defense, frame_w, frame_h)
                else:
                    self.last_pose_data = None
                    self.set_message("Move back a little: show head, both hands, and hips in camera.", 0.35)
            else:
                self.last_pose_data = None
                self.set_message("Camera cannot see your body yet. Step into the center.", 0.35)

            self.sync_audio_scene()
            self.draw_arena_background(frame)
            self.draw_holo_grid(frame, step=74)
            if self.app_state == "hub":
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
                self.draw_ghost_guides(frame)
                self.draw_monitor_widget(frame)
                if self.app_state == "fight":
                    self.draw_target_prompt(frame)
                elif self.app_state == "training":
                    self.draw_training_prompt(frame)
                if self.app_state == "fight":
                    if self.phase == "tutorial":
                        self.draw_tutorial_panel(frame)
                    elif self.phase == "command_round" and self.prompt:
                        self.draw_command_panel(frame, self.prompt["move"], self.prompt["expires_at"])
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

            cv2.imshow(WINDOW_NAME, frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("r"):
                self.reset_match()
                self.app_state = "hub"
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
