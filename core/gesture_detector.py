import cv2
import mediapipe as mp
import numpy as np

class GestureDetector:
    def __init__(self, 
                 static_image_mode=False, 
                 max_num_hands=1, 
                 min_detection_confidence=0.7, 
                 min_tracking_confidence=0.5):
        
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=static_image_mode,
            max_num_hands=max_num_hands,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )
        self.mp_drawing = mp.solutions.drawing_utils

    def process_frame(self, image):
        """
        Processes frame and returns hand landmarks.
        """
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = self.hands.process(image_rgb)
        return results

    def get_landmarks(self, results):
        if results.multi_hand_landmarks:
            # Return the first hand found for single-hand control
            return results.multi_hand_landmarks[0]
        return None
    
    def get_handedness(self, results):
        if results.multi_handedness:
            return results.multi_handedness[0].classification[0].label
        return None
