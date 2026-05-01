from copy import deepcopy


PROFILE_KEYS = {
    "left_straight": ["dz", "mid_dz", "reach_x", "dx", "dy", "planar"],
    "right_straight": ["dz", "mid_dz", "reach_x", "dx", "dy", "planar"],
    "left_uppercut": ["dy", "late_dy", "pre_dy", "elbow_to_wrist_y", "wrist_to_center_x", "start_hand_height", "end_hand_height"],
    "right_uppercut": ["dy", "late_dy", "pre_dy", "elbow_to_wrist_y", "wrist_to_center_x", "start_hand_height", "end_hand_height"],
    "left_hook": ["dx", "late_dx", "pre_dx", "planar"],
    "right_hook": ["dx", "late_dx", "pre_dx", "planar"],
}


def tutorial_rep_target(move_id):
    if move_id in ("left_straight", "right_straight", "left_uppercut", "right_uppercut", "left_hook", "right_hook"):
        return 3
    return 2


def merge_motion_profile(existing, motion):
    if not motion:
        return existing
    if not existing:
        profile = deepcopy(motion)
        profile["_samples"] = 1
        for key, value in motion.items():
            profile[f"{key}_min"] = float(value)
            profile[f"{key}_max"] = float(value)
        return profile
    samples = int(existing.get("_samples", 1))
    merged = {"_samples": samples + 1}
    for key, value in motion.items():
        old = float(existing.get(key, value))
        value = float(value)
        merged[key] = (old * samples + value) / (samples + 1)
        merged[f"{key}_min"] = min(float(existing.get(f"{key}_min", value)), value)
        merged[f"{key}_max"] = max(float(existing.get(f"{key}_max", value)), value)
    return merged


def profile_match(move_id, motion, profile):
    if not motion or not profile:
        return True
    keys = PROFILE_KEYS.get(move_id)
    if not keys:
        return True
    votes = 0
    for key in keys:
        target = float(profile.get(key, 0.0))
        value = float(motion.get(key, 0.0))
        profile_min = float(profile.get(f"{key}_min", target))
        profile_max = float(profile.get(f"{key}_max", target))
        spread = max(abs(profile_max - profile_min), abs(target) * 0.25)
        tolerance = max(0.035, spread * 1.25, abs(target) * 0.32)
        if abs(value - target) <= tolerance:
            votes += 1
    return votes >= max(3, len(keys) - 2)
