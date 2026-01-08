import numpy as np
import math

class SpineKyphosis:
    def __init__(self):
        pass

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
        
    def calculate_metrics(self, landmarks, image_shape):
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
        
        # 1. Shoulder Slope (Horizontal alignment)
        shoulder_slope = self.calculate_slope(l_shoulder, r_shoulder)
        
        # 2. Head Tilt (Roll)
        # Angle of eyes line or ears line relative to horizontal
        head_tilt = self.calculate_slope(l_ear, r_ear)
        
        # 3. Forward Head Angle (Approximation from front/oblique view)
        # This is strictly better from side view. If front view, it's hard.
        # Assuming we might have some depth info or user is slightly turned?
        # Or we rely on vertical offset?
        # For now, implementing as vertical alignment check (if looking from side)
        # OR if looking from front, we assume Z-axis (depth) might help if using world_landmarks?
        # Let's use 2D projection for now as robust fallback.
        avg_shoulder = [(l_shoulder[0] + r_shoulder[0])/2, (l_shoulder[1] + r_shoulder[1])/2]
        avg_ear = [(l_ear[0] + r_ear[0])/2, (l_ear[1] + r_ear[1])/2]
        forward_head_angle = self.get_forward_head_angle(avg_ear, avg_shoulder)
        
        return {
            "shoulder_slope": shoulder_slope,
            "head_tilt": head_tilt,
            "forward_head_angle": forward_head_angle
        }
