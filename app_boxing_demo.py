import math
import random
import time
from collections import deque

import cv2
import mediapipe as mp
import numpy as np


WINDOW_NAME = "Boxing Command Arena"
MAX_HP = 12
ROUNDS_TO_WIN = 2
REACTION_TIME = 2.0
ROUND_FREEZE_TIME = 1.4
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
]


class BoxingCommandArena:
    def __init__(self, camera_id=0):
        self.cap = cv2.VideoCapture(camera_id)
        self.pose = mp.solutions.pose.Pose(
            model_complexity=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.mp_drawing = mp.solutions.drawing_utils
        self.wrist_history = {"left": deque(maxlen=7), "right": deque(maxlen=7)}
        self.last_punch_at = 0.0
        self.hit_flash_until = 0.0
        self.damage_flash_until = 0.0
        self.message = "Move back a little so camera sees your head, both hands, and hips."
        self.message_until = 0.0
        self.match_over = False
        self.match_winner = None
        self.round_index = 1
        self.player_rounds = 0
        self.enemy_rounds = 0
        self.actions_cleared = 0
        self.prompt = None
        self.next_prompt_at = 0.0
        self.phase = "tutorial"
        self.tutorial_step = 0
        self.target_prompt = None
        self.reset_match()

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
        self.target_prompt = None
        self.player_hp = MAX_HP
        self.enemy_hp = MAX_HP
        self.wrist_history["left"].clear()
        self.wrist_history["right"].clear()
        self.round_freeze_until = time.time() + 0.5
        self.next_prompt_at = 0.0
        self.set_message("Tutorial first: perform each move once so tracking can lock in.", 2.5)

    def start_round(self, round_index):
        now = time.time()
        self.round_index = round_index
        self.player_hp = MAX_HP
        self.enemy_hp = MAX_HP
        self.prompt = None
        self.target_prompt = None
        self.last_punch_at = 0.0
        self.wrist_history["left"].clear()
        self.wrist_history["right"].clear()
        self.round_freeze_until = now + ROUND_FREEZE_TIME
        self.next_prompt_at = self.round_freeze_until + 0.8
        self.phase = "command_round" if round_index == 1 else "target_round"
        label = "Round 1: command mode" if round_index == 1 else "Round 2: target mode"
        self.set_message(f"{label}. Follow the prompt in the center.", 2.0)

    def set_message(self, text, duration=1.0):
        self.message = text
        self.message_until = time.time() + duration

    def current_gap(self):
        speedup = 0.06 * min(self.actions_cleared, 10) + 0.12 * max(self.round_index - 1, 0)
        return max(0.50, 1.40 - speedup)

    def spawn_prompt(self, now):
        if self.prompt or self.match_over or now < self.round_freeze_until or now < self.next_prompt_at:
            return

        prompt_type = "offense" if random.random() < 0.78 else "defense"
        move = random.choice(OFFENSE_MOVES if prompt_type == "offense" else DEFENSE_MOVES)
        self.prompt = {"type": prompt_type, "move": move, "issued_at": now, "expires_at": now + REACTION_TIME}

    def build_pose_data(self, pose_landmarks, frame_w, frame_h):
        def pt(idx):
            lm = pose_landmarks.landmark[idx]
            return np.array([lm.x * frame_w, lm.y * frame_h, lm.z], dtype=np.float32), lm.visibility

        nose, nose_vis = pt(0)
        l_elbow, le_vis = pt(13)
        r_elbow, re_vis = pt(14)
        l_shoulder, ls_vis = pt(11)
        r_shoulder, rs_vis = pt(12)
        l_wrist, lw_vis = pt(15)
        r_wrist, rw_vis = pt(16)
        l_hip, lh_vis = pt(23)
        r_hip, rh_vis = pt(24)

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

        _, start = history[0]
        _, end = history[-1]
        _, mid = history[len(history) // 2]
        shoulder_width = pose_data["shoulder_width"]
        torso_height = pose_data["torso_height"]
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
        return {
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
        }

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
        return {
            "guard": guard_active,
            "slip_left": lean_ratio < -0.18,
            "slip_right": lean_ratio > 0.18,
            "lean_ratio": lean_ratio,
        }

    def detect_offense_move(self, move_id, pose_data, strict=False):
        move = MOVE_BY_ID[move_id]
        motion = self.summarize_wrist_motion(move["hand"], pose_data)
        if motion is None:
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
            return (
                direction_ok
                and late_direction_ok
                and abs(motion["dx"]) > abs(motion["dy"]) * 1.15
                and motion["planar"] > hook_planar
            )

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
            return straight_score >= 4

        if move_id.endswith("uppercut"):
            current_uppercut_dy = uppercut_dy
            current_height_gain = 0.08
            current_center_limit = 0.42
            if move_id == "left_uppercut":
                current_uppercut_dy += 0.035
                current_height_gain = 0.04
                current_center_limit = 0.54

            if motion["dy"] >= current_uppercut_dy:
                return False
            if motion["late_dy"] >= current_uppercut_dy * 0.72:
                return False
            if motion["end_hand_height"] <= motion["start_hand_height"] + current_height_gain:
                return False

            uppercut_score = 2
            if abs(motion["dy"]) > abs(motion["dx"]) * 0.72:
                uppercut_score += 1
            if motion["elbow_to_wrist_y"] > 0.03:
                uppercut_score += 1
            if abs(motion["wrist_to_center_x"]) < current_center_limit:
                uppercut_score += 1
            if wrist[1] < shoulder[1] + pose_data["torso_height"] * 0.34:
                uppercut_score += 1
            return uppercut_score >= 5

        return False

    def detect_target_hit(self, pose_data, prompt):
        move_id = prompt["move_id"]
        if not self.detect_offense_move(move_id, pose_data, strict=False):
            return False

        hand = MOVE_BY_ID[move_id]["hand"]
        self.wrist_history[hand].clear()
        return True

    def defense_success(self, defense, move_id):
        return defense.get(move_id, False)

    def complete_tutorial_step(self):
        move_id = TUTORIAL_SEQUENCE[self.tutorial_step]
        self.set_message(f"{MOVE_BY_ID[move_id]['label']} confirmed.", 0.9)
        self.tutorial_step += 1
        self.wrist_history["left"].clear()
        self.wrist_history["right"].clear()
        if self.tutorial_step >= len(TUTORIAL_SEQUENCE):
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
            if self.detect_offense_move(move_id, pose_data, strict=False) and now - self.last_punch_at > PUNCH_COOLDOWN:
                self.last_punch_at = now
                self.complete_tutorial_step()
            elif self.prompt is None:
                self.prompt = {"type": "tutorial", "move": MOVE_BY_ID[move_id], "issued_at": now, "expires_at": now + TUTORIAL_WINDOW}

    def resolve_command_success(self, move, is_defense, now):
        if is_defense:
            self.set_message(f"{move['label']} successful.", 0.85)
        else:
            self.enemy_hp = max(0, self.enemy_hp - 1)
            self.hit_flash_until = now + 0.18
            self.set_message(f"{move['label']} landed. Rival loses 1 HP.", 0.9)
        self.actions_cleared += 1
        self.prompt = None
        self.next_prompt_at = now + self.current_gap()

    def resolve_target_success(self, now):
        move = MOVE_BY_ID[self.target_prompt["move_id"]]
        self.enemy_hp = max(0, self.enemy_hp - 1)
        self.hit_flash_until = now + 0.18
        self.set_message(f"{move['label']} hit the target. Rival loses 1 HP.", 0.9)
        self.actions_cleared += 1
        self.target_prompt = None
        self.next_prompt_at = now + self.current_gap()

    def resolve_timeout(self, now):
        if self.phase == "command_round" and self.prompt:
            move = self.prompt["move"]
            if self.prompt["type"] == "defense":
                self.player_hp = max(0, self.player_hp - 1)
                self.damage_flash_until = now + 0.22
                self.set_message(f"Too slow on {move['label']}. You lose 1 HP.", 1.0)
            else:
                self.set_message(f"Missed {move['label']}. Match the punch direction next time.", 1.0)
            self.prompt = None
            self.next_prompt_at = now + self.current_gap()
        elif self.phase == "target_round" and self.target_prompt:
            move = MOVE_BY_ID[self.target_prompt["move_id"]]
            self.set_message(f"Missed target for {move['label']}.", 1.0)
            self.target_prompt = None
            self.next_prompt_at = now + self.current_gap()

    def process_command_round(self, pose_data, defense, now):
        self.spawn_prompt(now)
        if not self.prompt:
            return
        move = self.prompt["move"]
        if self.prompt["type"] == "offense":
            if now - self.last_punch_at > PUNCH_COOLDOWN and self.detect_offense_move(move["id"], pose_data, strict=True):
                self.last_punch_at = now
                self.wrist_history[move["hand"]].clear()
                self.resolve_command_success(move, False, now)
                return
        else:
            if self.defense_success(defense, move["id"]):
                self.resolve_command_success(move, True, now)
                return

        if now >= self.prompt["expires_at"]:
            self.resolve_timeout(now)

    def build_target_prompt(self, frame_w, frame_h):
        move = random.choice(OFFENSE_MOVES)
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
        return {"move_id": move["id"], "shape": shape, "rect": rect, "expires_at": time.time() + REACTION_TIME}

    def process_target_round(self, pose_data, now, frame_w, frame_h):
        if self.target_prompt is None and now >= self.next_prompt_at and now >= self.round_freeze_until:
            self.target_prompt = self.build_target_prompt(frame_w, frame_h)

        if self.target_prompt is None:
            return

        if now - self.last_punch_at > PUNCH_COOLDOWN and self.detect_target_hit(pose_data, self.target_prompt):
            self.last_punch_at = now
            self.resolve_target_success(now)
            return

        if now >= self.target_prompt["expires_at"]:
            self.resolve_timeout(now)

    def update_round_state(self):
        if self.phase == "tutorial" or self.match_over:
            return

        if self.enemy_hp <= 0:
            self.player_rounds += 1
            if self.player_rounds >= ROUNDS_TO_WIN:
                self.match_over = True
                self.match_winner = "PLAYER"
                self.set_message("You win by KO.", 8.0)
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
                self.set_message("Opponent wins by KO.", 8.0)
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
        offset = -70 if direction == "right" else 70
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

    def draw_command_panel(self, frame, move, expires_at):
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = w // 2 - 220, 122, w // 2 + 220, 292
        cv2.rectangle(frame, (x1, y1), (x2, y2), (12, 12, 24), -1)
        cv2.rectangle(frame, (x1, y1), (x2, y2), MAGENTA, 2)
        self.draw_move_icon(frame, move["id"], (w // 2, y1 + 78))
        cv2.putText(frame, move["label"], (w // 2 - 135, y1 + 140), cv2.FONT_HERSHEY_DUPLEX, 0.94, WHITE, 2, cv2.LINE_AA)
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
        glow = frame.copy()
        cv2.rectangle(glow, (x1 - 8, y1 - 8), (x2 + 8, y2 + 8), GOLD, -1)
        cv2.addWeighted(glow, 0.10, frame, 0.90, 0, frame)
        if self.target_prompt["shape"] == "circle":
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            radius = (x2 - x1) // 2
            cv2.circle(frame, (cx, cy), radius, CYAN, 4, cv2.LINE_AA)
        else:
            cv2.rectangle(frame, (x1, y1), (x2, y2), CYAN, 4)
        cv2.putText(frame, move["label"], (x1 - 10, max(40, y1 - 14)), cv2.FONT_HERSHEY_DUPLEX, 0.7, WHITE, 2, cv2.LINE_AA)

    def draw_hud(self, frame, defense):
        h, w = frame.shape[:2]
        cv2.rectangle(frame, (20, 18), (w - 20, 108), (10, 10, 20), -1)
        cv2.rectangle(frame, (20, 18), (w - 20, 108), CYAN, 2)
        self.draw_bar(frame, "YOU", 40, 50, self.player_hp, MAX_HP, GREEN)
        self.draw_bar(frame, "RIVAL", w - 360, 50, self.enemy_hp, MAX_HP, MAGENTA)
        rounds_text = f"ROUND {self.round_index}   YOU {self.player_rounds} - {self.enemy_rounds} RIVAL"
        cv2.putText(frame, rounds_text, (w // 2 - 180, 48), cv2.FONT_HERSHEY_DUPLEX, 0.78, WHITE, 1, cv2.LINE_AA)
        phase_label = "Tutorial" if self.phase == "tutorial" else "Command Mode" if self.phase == "command_round" else "Target Mode"
        pace_text = f"{phase_label}   Gap {self.current_gap():.2f}s   Guard {'ON' if defense['guard'] else 'OFF'}"
        cv2.putText(frame, pace_text, (w // 2 - 180, 82), cv2.FONT_HERSHEY_SIMPLEX, 0.6, SOFT, 1, cv2.LINE_AA)
        if time.time() < self.message_until:
            cv2.putText(frame, self.message, (34, h - 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, GOLD, 2, cv2.LINE_AA)

        if self.match_over:
            label = "YOU WIN" if self.match_winner == "PLAYER" else "YOU LOSE"
            color = GREEN if self.match_winner == "PLAYER" else RED
            cv2.rectangle(frame, (w // 2 - 210, h // 2 - 90), (w // 2 + 210, h // 2 + 90), (15, 15, 28), -1)
            cv2.rectangle(frame, (w // 2 - 210, h // 2 - 90), (w // 2 + 210, h // 2 + 90), color, 3)
            cv2.putText(frame, label, (w // 2 - 115, h // 2 - 8), cv2.FONT_HERSHEY_DUPLEX, 1.6, color, 3, cv2.LINE_AA)
            cv2.putText(frame, "Press R to restart", (w // 2 - 105, h // 2 + 36), cv2.FONT_HERSHEY_SIMPLEX, 0.8, WHITE, 2, cv2.LINE_AA)

    def draw_pose(self, frame, landmarks):
        if landmarks is None:
            return
        self.mp_drawing.draw_landmarks(
            frame,
            landmarks,
            mp.solutions.pose.POSE_CONNECTIONS,
            landmark_drawing_spec=self.mp_drawing.DrawingSpec(color=(210, 210, 210), thickness=1, circle_radius=1),
            connection_drawing_spec=self.mp_drawing.DrawingSpec(color=(90, 90, 120), thickness=1),
        )

    def draw_tutorial_panel(self, frame):
        if self.phase != "tutorial" or self.tutorial_step >= len(TUTORIAL_SEQUENCE):
            return
        move_id = TUTORIAL_SEQUENCE[self.tutorial_step]
        move = MOVE_BY_ID[move_id]
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = w // 2 - 250, 120, w // 2 + 250, 318
        cv2.rectangle(frame, (x1, y1), (x2, y2), (12, 12, 24), -1)
        cv2.rectangle(frame, (x1, y1), (x2, y2), ORANGE, 2)
        self.draw_move_icon(frame, move_id, (w // 2, y1 + 78))
        cv2.putText(frame, f"LEARN {move['label']}", (w // 2 - 185, y1 + 146), cv2.FONT_HERSHEY_DUPLEX, 0.88, WHITE, 2, cv2.LINE_AA)
        cv2.putText(frame, move["hint"], (w // 2 - 190, y1 + 184), cv2.FONT_HERSHEY_SIMPLEX, 0.64, GOLD, 2, cv2.LINE_AA)
        progress = f"Step {self.tutorial_step + 1}/{len(TUTORIAL_SEQUENCE)}"
        cv2.putText(frame, progress, (w // 2 - 48, y2 - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.62, SOFT, 2, cv2.LINE_AA)

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
                self.update_wrist_memory(pose_data)
                if pose_data["min_visibility"] > 0.45:
                    defense = self.defense_state(pose_data)
                    if self.phase == "tutorial":
                        self.run_tutorial(pose_data, defense, now)
                    elif self.phase == "command_round":
                        self.process_command_round(pose_data, defense, now)
                    elif self.phase == "target_round":
                        self.process_target_round(pose_data, now, frame_w, frame_h)
                    self.update_round_state()
                else:
                    self.set_message("Move back a little: show head, both hands, and hips in camera.", 0.35)
            else:
                self.set_message("Camera cannot see your body yet. Step into the center.", 0.35)

            self.draw_gradient(frame)
            self.draw_target_prompt(frame)
            if self.phase == "tutorial":
                self.draw_tutorial_panel(frame)
            elif self.phase == "command_round" and self.prompt:
                self.draw_command_panel(frame, self.prompt["move"], self.prompt["expires_at"])
            self.draw_pose(frame, pose_landmarks)
            self.draw_hud(frame, defense)

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

        self.cap.release()
        cv2.destroyAllWindows()


def main():
    BoxingCommandArena().run()


if __name__ == "__main__":
    main()
