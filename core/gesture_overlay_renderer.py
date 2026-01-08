import cv2
import mediapipe as mp

class GestureOverlayRenderer:
    def __init__(self):
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_hands = mp.solutions.hands
        
        self.colors = {
            'IDLE': (200, 200, 200),
            'MOVE': (0, 255, 0),
            'CLICK_LEFT': (0, 255, 255),
            'CLICK_RIGHT': (255, 0, 255),
            'DRAG': (0, 0, 255),
            'SCROLL': (255, 165, 0)
        }

    def draw_landmarks(self, image, landmarks):
        if landmarks:
            self.mp_drawing.draw_landmarks(
                image, 
                landmarks, 
                self.mp_hands.HAND_CONNECTIONS,
                landmark_drawing_spec=self.mp_drawing.DrawingSpec(color=(255,255,255), thickness=1, circle_radius=1)
            )

    def draw_state(self, image, state, confidence=1.0):
        h, w, c = image.shape
        
        color = self.colors.get(state, (255, 255, 255))
        
        # Status Box
        cv2.rectangle(image, (10, 10), (200, 100), (0, 0, 0), -1)
        cv2.addWeighted(image[10:100, 10:200], 0.7, image[10:100, 10:200], 0.3, 0)
        
        cv2.putText(image, f"Mode: {state}", (20, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        
        cv2.putText(image, f"Conf: {confidence:.2f}", (20, 70), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    def draw_cursor_mapper(self, image, index_finger_norm):
        """
        Visualizes the cursor mapping ROI in the camera view.
        """
        h, w, c = image.shape
        roi_start = (int(w*0.1), int(h*0.1))
        roi_end = (int(w*0.9), int(h*0.9))
        
        cv2.rectangle(image, roi_start, roi_end, (100, 100, 100), 1)
        
        if index_finger_norm:
            cx, cy = int(index_finger_norm.x * w), int(index_finger_norm.y * h)
            cv2.circle(image, (cx, cy), 10, (0, 255, 255), 2)
    def draw_instructions(self, image):
        """
        Draws a list of instructions on the image.
        """
        h, w, c = image.shape
        x_start = 20
        y_start = h - 140
        line_height = 25
        
        instructions = [
            "Instructions:",
            " - Point (Index): Move Cursor",
            " - Pinch (Middle+Thumb): Left Click",
            " - Pinch (Index+Thumb): Right Click",
            " - Double Blink: Dbl Left Click",
            " - Fist: Drag",
            " - Open Hand: Scroll"
        ]
        
        # Draw background for better visibility
        overlay = image.copy()
        cv2.rectangle(overlay, (x_start - 10, y_start - 25), (350, y_start + len(instructions)*line_height - 15), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, image, 0.4, 0, image)
        
        for i, text in enumerate(instructions):
            color = (255, 255, 255)
            if i == 0: color = (0, 255, 255) # Header color
            cv2.putText(image, text, (x_start, y_start + i*line_height), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
