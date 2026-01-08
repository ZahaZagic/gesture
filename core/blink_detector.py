import cv2
import mediapipe as mp
import numpy as np
import time
from utils.geometry import calculate_distance_normalized

class BlinkDetector:
    def __init__(self, min_detection_confidence=0.5, min_tracking_confidence=0.5):
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )
        
        # EAR Threshold
        self.ear_threshold = 0.25 # If EAR drops below this, it's a closed eye
        
        # State
        self.blink_start_time = 0
        self.blinking = False
        self.last_blink_time = 0
        self.blink_count = 0
        
        # Double Click logic
        self.double_blink_window = 0.5 # seconds allowed between blinks
        
    def process_frame(self, image):
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        return self.face_mesh.process(image_rgb)
        
    def calculate_ear(self, landmarks, eye_indices):
        """
        Calculates Eye Aspect Ratio (EAR).
        """
        # Vertical distances
        v1 = calculate_distance_normalized(landmarks.landmark[eye_indices[1]], landmarks.landmark[eye_indices[5]])
        v2 = calculate_distance_normalized(landmarks.landmark[eye_indices[2]], landmarks.landmark[eye_indices[4]])
        
        # Horizontal distance
        h = calculate_distance_normalized(landmarks.landmark[eye_indices[0]], landmarks.landmark[eye_indices[3]])
        
        if h == 0: return 0.0
        ear = (v1 + v2) / (2.0 * h)
        return ear

    def check_blink(self, results):
        """
        Returns 'DOUBLE_BLINK' if detected, 'BLINK' if single, or None.
        """
        if not results.multi_face_landmarks:
            return None
            
        landmarks = results.multi_face_landmarks[0]
        
        # MediaPipe Face Mesh Eye Indices
        # Left Eye (from viewer perspective, actually Right Eye of person): [33, 160, 158, 133, 153, 144]
        # Right Eye (viewer perspective): [362, 385, 387, 263, 373, 380]
        # Indices in order: P1(Left corner), P2, P3, P4(Right corner), P5, P6
        
        left_eye_indices = [33, 160, 158, 133, 153, 144]
        right_eye_indices = [362, 385, 387, 263, 373, 380]
        
        left_ear = self.calculate_ear(landmarks, left_eye_indices)
        right_ear = self.calculate_ear(landmarks, right_eye_indices)
        
        avg_ear = (left_ear + right_ear) / 2.0
        
        event = None
        
        if avg_ear < self.ear_threshold:
            self.blinking = True
        else:
            if self.blinking:
                # Eye just opened -> Blink completed
                self.blinking = False
                current_time = time.time()
                
                # Check timeframe for double blink
                if (current_time - self.last_blink_time) < self.double_blink_window:
                    event = 'DOUBLE_BLINK'
                    self.last_blink_time = 0 # Reset
                else:
                    # Potential first blink of a pair
                    event = 'BLINK'
                    self.last_blink_time = current_time
                    
        return event
