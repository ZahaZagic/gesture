import cv2
import numpy as np
import mediapipe as mp

class OverlayRenderer:
    def __init__(self, config=None):
        self.config = config or {}
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_pose = mp.solutions.pose
        
        # Define styles
        self.colors = {
            'normal': (0, 255, 0),
            'warning': (0, 255, 255),
            'critical': (0, 0, 255),
            'text': (255, 255, 255),
            'bg': (0, 0, 0)
        }

    def draw_landmarks(self, image, landmarks):
        """Draws standard MediaPipe landmarks."""
        if landmarks:
            self.mp_drawing.draw_landmarks(
                image,
                landmarks,
                self.mp_pose.POSE_CONNECTIONS,
                landmark_drawing_spec=self.mp_drawing.DrawingSpec(color=(255,255,255), thickness=1, circle_radius=1),
                connection_drawing_spec=self.mp_drawing.DrawingSpec(color=(255,255,255), thickness=1)
            )

    def draw_metrics(self, image, metrics, guidelines=True, assessment=None):
        """
        Draws calculated metrics and guidelines on the image.
        metrics: dict containing 'shoulder_slope', 'head_tilt', etc.
        """
        h, w, c = image.shape
        
        # Display text info in top-left corner
        y_offset = 30
        x_offset = 20
        line_height = 25
        
        # Background box for text
        cv2.rectangle(image, (0, 0), (470, 280), (0, 0, 0), -1)
        cv2.addWeighted(image[0:280, 0:470], 0.7, image[0:280, 0:470], 0.3, 0)

        if assessment:
            status = assessment.get("status", "unknown").replace("_", " ").title()
            if assessment.get("calibrating"):
                status = "Calibrating"
            status_color = self.colors["normal"]
            if assessment.get("status") == "warning":
                status_color = self.colors["warning"]
            elif assessment.get("status") == "critical":
                status_color = self.colors["critical"]
            cv2.putText(image, f"Status: {status}", (x_offset, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2, cv2.LINE_AA)
            y_offset += line_height
        
        visible_metrics = (
            "shoulder_slope",
            "head_tilt",
            "head_lateral_offset_norm",
            "forward_head_angle",
            "forward_head_offset_norm",
            "neck_compaction_norm",
            "landmark_min_visibility",
        )
        for key in visible_metrics:
            value = metrics.get(key)
            if value is None:
                continue
            text = f"{key.replace('_', ' ').title()}: {value:.1f}"
            if "offset" in key or "visibility" in key:
                text = f"{key.replace('_', ' ').title()}: {value:.2f}"
            color = self.colors['normal']
            
            # Simple threshold check for coloring text (hardcoded defaults if config missing)
            if 'angle' in key or 'slope' in key or 'tilt' in key:
                 if value > 15: color = self.colors['critical']
                 elif value > 5: color = self.colors['warning']
            
            cv2.putText(image, text, (x_offset, y_offset), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1, cv2.LINE_AA)
            y_offset += line_height

    def draw_lines(self, image, landmarks, metrics):
        """Draws specific alignment lines (shoulder line, eye line, spine)."""
        if not landmarks: return
        
        h, w, c = image.shape
        
        def get_pt(idx):
            lm = landmarks.landmark[idx]
            return (int(lm.x * w), int(lm.y * h))
        
        l_shoulder = get_pt(11)
        r_shoulder = get_pt(12)
        l_ear = get_pt(7)
        r_ear = get_pt(8)
        
        # Shoulder line
        cv2.line(image, l_shoulder, r_shoulder, (0, 255, 255), 2)
        
        # Eye/Ear line (Head tilt)
        cv2.line(image, l_ear, r_ear, (255, 0, 255), 2)
        
        # Vertical reference (Spine-ish)
        mid_shoulder = ((l_shoulder[0] + r_shoulder[0])//2, (l_shoulder[1] + r_shoulder[1])//2)
        cv2.line(image, mid_shoulder, (mid_shoulder[0], mid_shoulder[1] + 200), (255, 255, 0), 1, cv2.LINE_AA)
