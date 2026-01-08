import cv2
import mediapipe as mp
import numpy as np
from utils.geometry import calculate_distance_normalized

class GazeTracker:
    def __init__(self, min_detection_confidence=0.5, min_tracking_confidence=0.5):
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,  # Crucial for Iris landmarks
            min_tracking_confidence=min_tracking_confidence
        )
        self.calibration_data = []
        self.homography_matrix = None
        
    def reset_calibration(self):
        self.calibration_data = [] # Stores (raw_dx, raw_dy, screen_x, screen_y)
        self.homography_matrix = None
        
    def add_calibration_point(self, raw_dx, raw_dy, screen_x, screen_y):
        """
        Collects data map: Eye Space (dx, dy) -> Screen Space (sx, sy)
        """
        self.calibration_data.append([raw_dx, raw_dy, screen_x, screen_y])

    def finalize_calibration(self):
        """
        Computes the Homography Matrix H.
        Need at least 4 points.
        """
        if len(self.calibration_data) < 4:
            print("Not enough points for calibration (need 4+)")
            return
            
        data = np.array(self.calibration_data)
        
        # Source Points: Eye Space (dx, dy)
        src_pts = data[:, 0:2].reshape(-1, 1, 2)
        
        # Destination Points: Screen Space (sx, sy)
        # We assume normalized screen coordinates (0.0 - 1.0) passed in
        dst_pts = data[:, 2:4].reshape(-1, 1, 2)
        
        # Calculate Homography
        # RANSAC is robust to outliers if we have many points, but for 4-5 points, 0 is fine
        self.homography_matrix, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        
        print("Calibration Complete: Homography Matrix Computed")
        print(self.homography_matrix)

    def get_gaze_point(self, results):
        if not results.multi_face_landmarks:
            return None
            
        landmarks = results.multi_face_landmarks[0]
        
        # Indices (MediaPipe Face Mesh Refined)
        right_eye_indices = [33, 133, 159, 145] 
        right_iris_indices = [468, 469, 470, 471]
        
        left_eye_indices = [362, 263, 386, 374]
        left_iris_indices = [473, 474, 475, 476]
        
        r_x, r_y = self.get_gaze_ratio(landmarks, right_eye_indices, right_iris_indices)
        l_x, l_y = self.get_gaze_ratio(landmarks, left_eye_indices, left_iris_indices)
        
        avg_x = (r_x + l_x) / 2.0
        avg_y = (r_y + l_y) / 2.0
        
        # Apply Calibration
        norm_x, norm_y = avg_x, avg_y # Default if no calibration
        
        if self.homography_matrix is not None:
            # Perspective Transform
            # Point: [x, y, 1]
            pt = np.array([[[avg_x, avg_y]]], dtype=np.float32)
            dst_pt = cv2.perspectiveTransform(pt, self.homography_matrix)
            
            norm_x = dst_pt[0][0][0]
            norm_y = dst_pt[0][0][1]
        else:
             # Fallback to simple scaling if not calibrated yet (approximate)
             # Default range +/- 0.10
             norm_x = (avg_x - (-0.10)) / 0.20
             norm_y = (avg_y - (-0.10)) / 0.20
        
        return max(0.0, min(1.0, norm_x)), max(0.0, min(1.0, norm_y)), avg_x, avg_y
        
    def process_frame(self, image):
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        return self.face_mesh.process(image_rgb)
        
    def get_gaze_ratio(self, landmarks, eye_indices, iris_indices):
        """
        Calculates the relative position of the iris.
        """
        # Eye corners
        p_left = landmarks.landmark[eye_indices[0]]
        p_right = landmarks.landmark[eye_indices[1]]
        
        # Iris center
        iris_center_x = np.mean([landmarks.landmark[i].x for i in iris_indices])
        iris_center_y = np.mean([landmarks.landmark[i].y for i in iris_indices])
        
        # Eye Width (Scale factor)
        eye_width = max(0.001, calculate_distance_normalized(p_left, p_right))
        
        # Center of the eye (between corners)
        eye_center_x = (p_left.x + p_right.x) / 2.0
        eye_center_y = (p_left.y + p_right.y) / 2.0
        
        # Deviation from center, normalized by width
        # This makes it independent of head scale/distance
        dx = (iris_center_x - eye_center_x) / eye_width
        dy = (iris_center_y - eye_center_y) / eye_width
        
        return dx, dy

