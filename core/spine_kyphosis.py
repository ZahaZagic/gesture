import numpy as np

class SpineKyphosis:
    def __init__(self):
        self.required_landmarks = (0, 2, 5, 7, 8, 11, 12)

    def calculate_angle(self, a, b, c):
        """
        Calculates the angle between three points (A, B, C).
        B is the vertex.
        """
        a = np.array(a)
        b = np.array(b)
        c = np.array(c)

        radians = np.arctan2(c[1] - b[1], c[0] - b[0]) - np.arctan2(a[1] - b[1], a[0] - b[0])
        angle = np.abs(radians * 180.0 / np.pi)

        if angle > 180.0:
            angle = 360 - angle

        return angle

    def calculate_slope(self, a, b):
        """
        Calculates the slope angle of a line segment relative to the horizontal.
        """
        a = np.array(a)
        b = np.array(b)
        
        radians = np.arctan2(b[1] - a[1], b[0] - a[0])
        angle = radians * 180.0 / np.pi
        if angle > 90.0:
            angle -= 180.0
        elif angle < -90.0:
            angle += 180.0
        
        return angle

    def get_forward_head_angle(self, ear, shoulder, vertical_ref=True):
        """
        Calculates Forward Head Angle (FHA).
        Typically measured as the angle between the vertical line through the shoulder 
        and the line connecting the shoulder to the ear (tragus).
        
        Args:
            ear: (x, y) coordinates of the ear (tragus).
            shoulder: (x, y) coordinates of the acromion (shoulder).
            vertical_ref: If True, measures against vertical.
        """
        if vertical_ref:
            # Create a virtual point directly above the shoulder to form a vertical line
            vertical_point = [shoulder[0], shoulder[1] - 100] # Y decreases upwards
            return self.calculate_angle(vertical_point, shoulder, ear)
        else:
            # Alternatively, could be measured against C7 if available, but here we use vertical ref
            pass
        return 0.0

    def get_lateral_head_offset(self, nose, shoulder_mid, shoulder_width):
        """
        Returns the side-to-side head offset normalized by shoulder width.
        Positive means the nose is to the right of the shoulder midpoint.
        """
        if shoulder_width <= 1e-6:
            return 0.0
        return (nose[0] - shoulder_mid[0]) / shoulder_width

    def get_forward_head_offset(self, ear_world, shoulder_world, shoulder_width_world):
        """
        Estimates forward/back head position from MediaPipe world landmarks.

        MediaPipe's world Z axis is camera-relative and can vary by setup, so the
        raw value is best interpreted after per-user baseline calibration.
        """
        if ear_world is None or shoulder_world is None or shoulder_width_world <= 1e-6:
            return None
        return float((ear_world[2] - shoulder_world[2]) / shoulder_width_world)

    def landmark_quality(self, landmarks):
        values = []
        for idx in self.required_landmarks:
            lm = landmarks.landmark[idx]
            values.append(getattr(lm, "visibility", 1.0))
        return float(min(values)), float(np.mean(values))

    def get_kyphosis_angle(self, shoulder, spine_mid, sternum_approx=None):
        """
        Estimates Kyphosis severity (Thoracic Kyphosis).
        Since we don't have a side view spine scan, we use a proxy:
        The angle formed by the shoulder placement relative to the spine line.
        
        A more direct specific 'Angle of Kyphosis' usually requires Cobb angle from X-rays.
        Here we approximate 'Rounded Shoulders' which correlates with Kyphosis.
        
        Using: Shoulder protraction.
        """
        # This is a heuristic. 
        # Real kyphosis needs depth or side profile. 
        # In front view, we can detect if shoulders are "rolled forward" 
        # by checking if they are narrower than expected or by heuristic landmarks.
        # But for this module, the user asked for "Sternum - Shoulder - SpineTop".
        # We might need to approximate Sternum position from shoulders midpoint.
        pass
        
    def calculate_metrics(self, landmarks, image_shape, world_landmarks=None):
        """
        Extracts all relevant posture metrics from landmarks.
        """
        h, w, c = image_shape
        
        # Landmarks indices (MediaPipe Pose)
        # 0: nose
        # 2: left_eye
        # 5: right_eye
        # 7: left_ear
        # 8: right_ear
        # 11: left_shoulder
        # 12: right_shoulder
        
        # Helper to get coords
        def get_coords(idx):
            lm = landmarks.landmark[idx]
            return [lm.x * w, lm.y * h]

        l_shoulder = get_coords(11)
        r_shoulder = get_coords(12)
        l_ear = get_coords(7)
        r_ear = get_coords(8)
        nose = get_coords(0)
        l_eye = get_coords(2)
        r_eye = get_coords(5)
        
        # 1. Shoulder Slope (Horizontal alignment)
        shoulder_slope = self.calculate_slope(l_shoulder, r_shoulder)
        shoulder_slope_abs = abs(shoulder_slope)
        shoulder_width = float(np.linalg.norm(np.array(l_shoulder) - np.array(r_shoulder)))
        shoulder_mid = [(l_shoulder[0] + r_shoulder[0]) / 2, (l_shoulder[1] + r_shoulder[1]) / 2]
        shoulder_height_delta_norm = 0.0
        if shoulder_width > 1e-6:
            shoulder_height_delta_norm = (l_shoulder[1] - r_shoulder[1]) / shoulder_width
        
        # 2. Head Tilt (Roll)
        # Angle of eyes line or ears line relative to horizontal
        head_tilt = self.calculate_slope(l_ear, r_ear)
        head_tilt_abs = abs(head_tilt)
        
        # 3. Forward Head Angle (Approximation from front/oblique view)
        # This is strictly better from side view. If front view, it's hard.
        # Assuming we might have some depth info or user is slightly turned?
        # Or we rely on vertical offset?
        # For now, implementing as vertical alignment check (if looking from side)
        # OR if looking from front, we assume Z-axis (depth) might help if using world_landmarks?
        # Let's use 2D projection for now as robust fallback.
        avg_shoulder = shoulder_mid
        avg_ear = [(l_ear[0] + r_ear[0]) / 2, (l_ear[1] + r_ear[1]) / 2]
        forward_head_angle = self.get_forward_head_angle(avg_ear, avg_shoulder)

        eye_width = float(np.linalg.norm(np.array(l_eye) - np.array(r_eye)))
        ear_width = float(np.linalg.norm(np.array(l_ear) - np.array(r_ear)))
        face_yaw_proxy = 0.0
        if shoulder_width > 1e-6:
            face_yaw_proxy = abs(eye_width - ear_width) / shoulder_width

        forward_head_offset = None
        if world_landmarks:
            def get_world(idx):
                lm = world_landmarks.landmark[idx]
                return np.array([lm.x, lm.y, lm.z], dtype=np.float32)

            l_shoulder_w = get_world(11)
            r_shoulder_w = get_world(12)
            l_ear_w = get_world(7)
            r_ear_w = get_world(8)
            shoulder_width_w = float(np.linalg.norm(l_shoulder_w - r_shoulder_w))
            avg_shoulder_w = (l_shoulder_w + r_shoulder_w) / 2
            avg_ear_w = (l_ear_w + r_ear_w) / 2
            forward_head_offset = self.get_forward_head_offset(avg_ear_w, avg_shoulder_w, shoulder_width_w)

        min_visibility, avg_visibility = self.landmark_quality(landmarks)
        
        return {
            "shoulder_slope": shoulder_slope,
            "shoulder_slope_abs": shoulder_slope_abs,
            "shoulder_height_delta_norm": shoulder_height_delta_norm,
            "head_tilt": head_tilt,
            "head_tilt_abs": head_tilt_abs,
            "head_lateral_offset_norm": self.get_lateral_head_offset(nose, shoulder_mid, shoulder_width),
            "forward_head_angle": forward_head_angle,
            "forward_head_offset_norm": forward_head_offset,
            "face_yaw_proxy": face_yaw_proxy,
            "landmark_min_visibility": min_visibility,
            "landmark_avg_visibility": avg_visibility
        }
