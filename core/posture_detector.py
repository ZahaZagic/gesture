import cv2
import mediapipe as mp
import numpy as np
from typing import NamedTuple, Optional

class PostureDetector:
    def __init__(self, 
                 static_image_mode=False, 
                 model_complexity=1, 
                 smooth_landmarks=True, 
                 enable_segmentation=False, 
                 smooth_segmentation=True, 
                 min_detection_confidence=0.5, 
                 min_tracking_confidence=0.5):
        
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=static_image_mode,
            model_complexity=model_complexity,
            smooth_landmarks=smooth_landmarks,
            enable_segmentation=enable_segmentation,
            smooth_segmentation=smooth_segmentation,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )
        self.mp_drawing = mp.solutions.drawing_utils

    def process_frame(self, image: np.ndarray) -> NamedTuple:
        """
        Processes a BGR image and returns the pose landmarks.
        """
        # Convert the BGR image to RGB.
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Process the image and find the pose.
        results = self.pose.process(image_rgb)
        
        return results

    def get_landmarks(self, results) -> Optional[object]:
        if results.pose_landmarks:
            return results.pose_landmarks
        return None

    def get_world_landmarks(self, results) -> Optional[object]:
        if results.pose_world_landmarks:
            return results.pose_world_landmarks
        return None
