import numpy as np

class FaceAlignment:
    def __init__(self):
        pass

    def check_symmetry(self, landmarks, image_shape):
        h, w, c = image_shape
        
        def get_coords(idx):
            lm = landmarks.landmark[idx]
            return [lm.x * w, lm.y * h]

        l_eye = get_coords(2)
        r_eye = get_coords(5)
        nose = get_coords(0)
        
        # Midpoint of eyes
        eyes_mid = [(l_eye[0] + r_eye[0]) / 2, (l_eye[1] + r_eye[1]) / 2]
        
        # Deviation of nose from eyes midpoint
        # Ideally nose should be strictly below eyes_mid
        
        dx = nose[0] - eyes_mid[0]
        
        # Normalize by eye distance to be scale invariant
        eye_dist = np.linalg.norm(np.array(l_eye) - np.array(r_eye))
        symmetry_ratio = 1.0
        
        if eye_dist > 0:
             symmetry_ratio = 1.0 - (abs(dx) / eye_dist)
             
        return {
            "face_symmetry_ratio": max(0.0, symmetry_ratio),
            "chin_offset": dx # Raw pixel offset, maybe better to normalize
        }
