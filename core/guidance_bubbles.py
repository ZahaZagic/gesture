import cv2
import numpy as np

class GuidanceBubbles:
    def __init__(self, config=None):
        posture_config = (config or {}).get("posture", {})
        self.colors = posture_config.get("colors", {})

    def draw_bubble(self, image, text, position, color=(0, 255, 0)):
        """
        Draws a rounded rectangle bubble with text at position (x, y).
        """
        x, y = position
        
        (w, h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
        
        padding = 10
        box_coords = ((x, y - h - 2*padding), (x + w + 2*padding, y))
        
        # Draw bubble background
        cv2.rectangle(image, box_coords[0], box_coords[1], color, -1)
        cv2.rectangle(image, box_coords[0], box_coords[1], (255, 255, 255), 1)
        
        # Draw text
        cv2.putText(image, text, (x + padding, y - padding), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA)

    def update(self, image, metrics, landmarks=None, assessment=None):
        """
        Analyzes metrics and draws suggestions.
        """
        h, w, c = image.shape
        
        msgs = []

        if assessment:
            if assessment.get("calibrating"):
                msgs.append(("Calibrating posture...", (50, h - 20), (0, 255, 0)))
            elif assessment.get("status") == "low_confidence":
                msgs.append(("Move fully into camera view", (50, h - 20), (0, 255, 255)))
            else:
                for idx, issue in enumerate(assessment.get("issues", [])[:3]):
                    color = (0, 0, 255) if issue.get("severity", 1) >= 2 else (0, 255, 255)
                    msgs.append((issue["message"], (50, h - 20 - idx * 40), color))
        else:
            # Backward-compatible fallback for callers that only pass metrics.
            if abs(metrics.get('shoulder_slope', 0)) > 5:
                msgs.append(("Level Shoulders", (50, h - 100), (0, 255, 255)))
            if abs(metrics.get('head_tilt', 0)) > 8:
                msgs.append(("Straighten Head", (50, h - 60), (0, 255, 255)))
            if metrics.get('forward_head_angle', 0) > 15:
                msgs.append(("Tuck Chin (Forward Head)", (50, h - 20), (0, 0, 255)))

        # Draw all generated messages
        for txt, pos, col in msgs:
            self.draw_bubble(image, txt, pos, col)
