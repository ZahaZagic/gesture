import cv2
import numpy as np
import time
import math
from openvino.runtime import Core

from utils.smoothing import AdaptiveSmoothing

# --- OpenVINO Tracker Class ---
class OpenVINOGazeTracker:
    def __init__(self, model_dir="models/intel"):
        self.core = Core()
        
        # Paths (FP16 is usually good balance for CPU/GPU)
        # Adjust paths based on omz_downloader output structure
        base_prec = "FP16" 
        
        self.model_face = self._load_model(f"{model_dir}/face-detection-adas-0001/{base_prec}/face-detection-adas-0001.xml")
        self.model_lm = self._load_model(f"{model_dir}/facial-landmarks-35-adas-0002/{base_prec}/facial-landmarks-35-adas-0002.xml")
        self.model_pose = self._load_model(f"{model_dir}/head-pose-estimation-adas-0001/{base_prec}/head-pose-estimation-adas-0001.xml")
        self.model_gaze = self._load_model(f"{model_dir}/gaze-estimation-adas-0002/{base_prec}/gaze-estimation-adas-0002.xml")
        
        # Inference Requests
        self.req_face = self.model_face.create_infer_request()
        self.req_lm = self.model_lm.create_infer_request()
        self.req_pose = self.model_pose.create_infer_request()
        self.req_gaze = self.model_gaze.create_infer_request()
        
        # Input/Output Names (Hardcoded for these specific ADAS models)
        self.input_face = self.model_face.input(0)
        self.out_face = self.model_face.output(0)
        
        # Calibration Data (Homography)
        self.calibration_points = [] # List of (raw_x, raw_y, screen_x, screen_y)
        self.homography_matrix = None

    def _load_model(self, path):
        print(f"Loading {path}...")
        model = self.core.read_model(path)
        return self.core.compile_model(model, "AUTO")

    def _preprocess(self, frame, input_layer):
        n, c, h, w = input_layer.shape
        resized = cv2.resize(frame, (w, h))
        transposed = resized.transpose((2, 0, 1)) # HWC -> CHW
        reshaped = transposed.reshape((n, c, h, w))
        return reshaped

    def get_face(self, frame):
        h, w = frame.shape[:2]
        in_tensor = self._preprocess(frame, self.input_face)
        self.req_face.infer({0: in_tensor})
        res = self.req_face.get_output_tensor(0).data
        
        # Parse output: [1, 1, N, 7] -> [image_id, label, conf, x_min, y_min, x_max, y_max]
        # We take the best confidence face
        best_face = None
        max_conf = 0
        
        for obj in res[0][0]:
            conf = obj[2]
            if conf > 0.5:
                if conf > max_conf:
                    max_conf = conf
                    xmin = int(obj[3] * w)
                    ymin = int(obj[4] * h)
                    xmax = int(obj[5] * w)
                    ymax = int(obj[6] * h)
                    
                    # Clamp
                    xmin = max(0, xmin)
                    ymin = max(0, ymin)
                    xmax = min(w, xmax)
                    ymax = min(h, ymax)
                    
                    best_face = (xmin, ymin, xmax, ymax)
        
        return best_face

    def get_landmarks(self, face_crop):
        if face_crop.size == 0: return None
        in_tensor = self._preprocess(face_crop, self.model_lm.input(0))
        self.req_lm.infer({0: in_tensor})
        # Output: [1, 70] -> 35 pairs of (x, y) normalized
        res = self.req_lm.get_output_tensor(0).data.flatten()
        
        landmarks = []
        fh, fw = face_crop.shape[:2]
        for i in range(0, len(res), 2):
            x = int(res[i] * fw)
            y = int(res[i+1] * fh)
            landmarks.append((x, y))
        return landmarks

    def get_head_pose(self, face_crop):
        if face_crop.size == 0: return None
        in_tensor = self._preprocess(face_crop, self.model_pose.input(0))
        self.req_pose.infer({0: in_tensor})
        
        # Outputs: angle_y_fc (yaw), angle_p_fc (pitch), angle_r_fc (roll)
        yaw = self.req_pose.get_tensor("angle_y_fc").data[0][0]
        pitch = self.req_pose.get_tensor("angle_p_fc").data[0][0]
        roll = self.req_pose.get_tensor("angle_r_fc").data[0][0]
        return (yaw, pitch, roll)

    def get_gaze(self, left_eye, right_eye, head_pose):
        if left_eye.size == 0 or right_eye.size == 0: return None
        
        # Gaze Model Inputs:
        # left_eye_image: [1, 3, 60, 60]
        # right_eye_image: [1, 3, 60, 60]
        # head_pose_angles: [1, 3] -> (yaw, pitch, roll)
        
        in_left = self._preprocess(left_eye, self.model_gaze.input("left_eye_image"))
        in_right = self._preprocess(right_eye, self.model_gaze.input("right_eye_image"))
        in_angles = np.array([head_pose]).reshape((1, 3))
        
        self.req_gaze.infer({
            "left_eye_image": in_left,
            "right_eye_image": in_right,
            "head_pose_angles": in_angles
        })
        
        # Output: gaze_vector [1, 3] -> (x, y, z)
        gaze_vec = self.req_gaze.get_output_tensor(0).data[0]
        return gaze_vec

    def process_frame(self, frame):
        face_rect = self.get_face(frame)
        if not face_rect: return None, None
        
        xmin, ymin, xmax, ymax = face_rect
        face_crop = frame[ymin:ymax, xmin:xmax]
        
        landmarks = self.get_landmarks(face_crop)
        if not landmarks: return None, None
        
        # Landmarks 0-35. 
        # Left Eye: 0 (outer), 1 (inner) approx center ~0,1? No, 35 landmarks:
        # 0,1: Left Eye corners? 
        # Actually 35-ADAS: 
        # 0-1: Left eyebrow
        # 2-3: Right eyebrow
        # 4-7: Nose
        # 8-11: Left Eye (8=outer, 9=upper, 10=inner, 11=lower) -> Center approx avg
        # 12-15: Right Eye (12=inner, 13=upper, 14=outer, 15=lower)
        # ...
        
        # Extract Eye Centers (Relative to face crop)
        le_c = np.mean([landmarks[8], landmarks[9], landmarks[10], landmarks[11]], axis=0).astype(int)
        re_c = np.mean([landmarks[12], landmarks[13], landmarks[14], landmarks[15]], axis=0).astype(int)
        
        # Crop Eyes (Fixed size 60x60 for model, but we extract square region)
        eye_size = 60
        half = eye_size // 2
        
        def crop_eye(center, img):
            cx, cy = center
            x1 = max(0, cx - half)
            y1 = max(0, cy - half)
            x2 = min(img.shape[1], cx + half)
            y2 = min(img.shape[0], cy + half)
            crop = img[y1:y2, x1:x2]
            # Pad if needed
            if crop.shape[0] != eye_size or crop.shape[1] != eye_size:
                padded = np.zeros((eye_size, eye_size, 3), dtype=np.uint8)
                h, w = crop.shape[:2]
                padded[0:h, 0:w] = crop
                return padded
            return crop

        left_eye_img = crop_eye(le_c, face_crop)
        right_eye_img = crop_eye(re_c, face_crop)
        
        # Head Pose
        angles = self.get_head_pose(face_crop)
        
        # Gaze Vector
        gaze_vec = self.get_gaze(left_eye_img, right_eye_img, angles)
        
        # Debug Info dictionary
        debug_info = {
            "face": face_rect,
            "landmarks": [(lx+xmin, ly+ymin) for lx, ly in landmarks],
            "gaze_vec": gaze_vec,
            "head_pose": angles
        }
        
        return gaze_vec, debug_info

    # --- Calibration Methods (Same as before) ---
    def add_calibration_point(self, raw_dx, raw_dy, screen_x, screen_y):
        self.calibration_points.append([raw_dx, raw_dy, screen_x, screen_y])

    def finalize_calibration(self):
        if len(self.calibration_points) < 4:
            print("Not enough calibration points.")
            return

        pts = np.array(self.calibration_points)
        src = pts[:, :2] # raw gaze vector x, y
        dst = pts[:, 2:] # screen x, y (normalized)
        
        # Find Homography
        try:
            self.homography_matrix, status = cv2.findHomography(src, dst)
            print("Calibration Successful. Matrix:\n", self.homography_matrix)
        except Exception as e:
            print("Calibration Failed:", e)
    
    def reset_calibration(self):
        self.calibration_points = []
        self.homography_matrix = None

    def map_gaze(self, gaze_vec):
        # gaze_vec is (x, y, z)
        # We project to 2D plain x, y. 
        # Usually raw x, -y (inverted y for screen)
        raw_x = gaze_vec[0]
        raw_y = -gaze_vec[1] # Flip Y for screen coords
        
        if self.homography_matrix is None:
            # Default uncalibrated mapping (just scaling for testing)
            # Rough approximation: Gaze X -0.5 to 0.5 -> 0 to 1
            # Gaze Y -0.3 to 0.3 -> 0 to 1
            sx = 0.5 + (raw_x * 2.0)
            sy = 0.5 + (raw_y * 2.0)
            return sx, sy, raw_x, raw_y
        
        # Apply Homography
        pt = np.array([[[raw_x, raw_y]]], dtype=np.float32)
        dst = cv2.perspectiveTransform(pt, self.homography_matrix)
        sx = dst[0][0][0]
        sy = dst[0][0][1]
        
        return sx, sy, raw_x, raw_y

# --- Main Demo ---
def main():
    tracker = OpenVINOGazeTracker()
    cap = cv2.VideoCapture(0)
    
    # Smoothers
    smoother_x = AdaptiveSmoothing(min_alpha=0.1, max_alpha=0.9, slope=15.0)
    smoother_y = AdaptiveSmoothing(min_alpha=0.1, max_alpha=0.9, slope=15.0)

    # Calibration State
    is_calibrating = False
    calibration_stage = 0
    calibration_timer = 0
    
    # Waypoints for calibration
    waypoints = []
    
    print("OpenVINO Gaze Tracker Started.")
    print("Press 'c' to Calibrate.")
    print("Press 'q' to Quit.")
    
    while True:
        ret, frame = cap.read()
        if not ret: break
        
        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        
        # Inference
        gaze_vec, debug = tracker.process_frame(frame)
        
        gx, gy = 0.5, 0.5
        
        if gaze_vec is not None:
            # Mapping
            sx, sy, raw_x, raw_y = tracker.map_gaze(gaze_vec)
            
            # Calibration Collection
            if is_calibrating and len(waypoints) > 0:
                 elapsed = time.time() - calibration_timer
                 duration = 2.0
                 idx = int(elapsed / duration)
                 
                 if idx >= len(waypoints):
                     is_calibrating = False
                     tracker.finalize_calibration()
                     print("Calibration Done")
                 else:
                     target = waypoints[idx]
                     # Draw Target
                     cv2.circle(frame, target, 20, (0,0,255), -1)
                     cv2.circle(frame, target, 5, (255,255,0), -1)
                     
                     # Collect Data
                     tx_norm = target[0] / w
                     ty_norm = target[1] / h
                     tracker.add_calibration_point(raw_x, raw_y, tx_norm, ty_norm)

            # Apply Smoothing
            gx = smoother_x.update(sx)
            gy = smoother_y.update(sy)
            
            # Visuals
            # Draw Face Box
            fx1, fy1, fx2, fy2 = debug['face']
            cv2.rectangle(frame, (fx1, fy1), (fx2, fy2), (0, 255, 0), 1)
            
            # Draw Landmarks (Eyes)
            for (lx, ly) in debug['landmarks']:
                cv2.circle(frame, (lx, ly), 2, (0, 255, 255), -1)
                
            # Draw Gaze Vector (Projected)
            # Just draw a line from face center
            fcx = (fx1 + fx2) // 2
            fcy = (fy1 + fy2) // 2
            g_end_x = int(fcx + gaze_vec[0] * 200)
            g_end_y = int(fcy - gaze_vec[1] * 200)
            cv2.arrowedLine(frame, (fcx, fcy), (g_end_x, g_end_y), (0, 0, 255), 2)
            
            # Draw Gaze Point on Screen
            screen_x = int(gx * w)
            screen_y = int(gy * h)
            cv2.circle(frame, (screen_x, screen_y), 15, (255, 0, 255), 2)
            cv2.line(frame, (screen_x - 10, screen_y), (screen_x + 10, screen_y), (255, 0, 255), 2)
            cv2.line(frame, (screen_x, screen_y - 10), (screen_x, screen_y + 10), (255, 0, 255), 2)
        
        cv2.imshow("OpenVINO Gaze", frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        if key == ord('c'):
            is_calibrating = True
            tracker.reset_calibration()
            calibration_timer = time.time()
            # Define 9 points
            waypoints = [
                (50, 50), (w//2, 50), (w-50, 50),
                (50, h//2), (w//2, h//2), (w-50, h//2),
                (50, h-50), (w//2, h-50), (w-50, h-50)
            ]
            print("Calibration started...")

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
