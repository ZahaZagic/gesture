import cv2
import yaml
import time
from core.gaze_tracker import GazeTracker
from core.blink_detector import BlinkDetector
from core.gesture_mouse_controller import GestureMouseController
from core.gesture_overlay_renderer import GestureOverlayRenderer

from utils.smoothing import AdaptiveSmoothing
import collections

def load_config(path="config.yaml"):
    try:
        with open(path, "r") as f:
            return yaml.safe_load(f)
    except:
        return {}

def main():
    config = load_config()
    cap = cv2.VideoCapture(config.get('camera_id', 0))
    
    # Initialize Core
    gaze_tracker = GazeTracker()
    blink_detector = BlinkDetector()
    controller = GestureMouseController(config)
    
    # Adaptive Smoothing for Eyes
    # min_alpha=0.02 (very smooth for static), max_alpha=0.7 (responsive for fast looks)
    # slope=20 means if velocity > 0.05 (5% screen width), we hit max alpha
    smoother_x = AdaptiveSmoothing(min_alpha=0.02, max_alpha=0.8, slope=20.0)
    smoother_y = AdaptiveSmoothing(min_alpha=0.02, max_alpha=0.8, slope=20.0)
    
    # Visuals reuse 
    # We can reuse drawing utils but overlay might need custom text
    
    # Gaze Trail (History of points)
    gaze_trail = collections.deque(maxlen=20)
    
    # Calibration State
    is_calibrating = False
    calibration_stage = 0 
    # Stages: 0=Start, 1=Top-Left, 2=Top-Right, 3=Bottom-Right, 4=Bottom-Left, 5=Done
    calibration_timer = 0
    calibration_duration = 2.0 # seconds per point
    
    print("Starting Eye Tracking Mouse... Press 'q' to quit. Press 'c' to Calibrate.")
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        # Flip frame for mirror view
        frame = cv2.flip(frame, 1)
        h, w, c = frame.shape
        
        # 1. Detection
        gaze_results = gaze_tracker.process_frame(frame)
        gaze_data = gaze_tracker.get_gaze_point(gaze_results) # Now returns 4 values
        
        blink_results = blink_detector.process_frame(frame)
        blink_event = blink_detector.check_blink(blink_results)
        
        if gaze_data:
            # Unpack (norm_x, norm_y, raw_dx, raw_dy)
            gx, gy, raw_dx, raw_dy = gaze_data
            
            # --- CALIBRATION LOGIC ---
            if is_calibrating:
                cv2.putText(frame, "CALIBRATION MODE", (w//2 - 100, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                
                # Define Waypoints for Trajectory (Box + Cross)
                waypoints = [
                    (50, 50),          # TL
                    (w-50, 50),        # TR
                    (w-50, h-50),      # BR
                    (50, h-50),        # BL
                    (50, 50),          # TL (Close Box)
                    (w-50, h-50),      # BR (Diag 1)
                    (w-50, 50),        # TR (Up)
                    (50, h-50),        # BL (Diag 2)
                    (w//2, h//2)       # Center (End)
                ]
                
                total_duration = 30.0 # seconds for full path
                segment_duration = total_duration / (len(waypoints) - 1)
                
                elapsed = time.time() - calibration_timer
                
                # Check if done
                if elapsed > total_duration:
                     is_calibrating = False
                     gaze_tracker.finalize_calibration()
                     print("Moving Calibration Done")
                else:
                    # Calculate current position
                    current_idx = int(elapsed / segment_duration)
                    if current_idx >= len(waypoints) - 1:
                        target = waypoints[-1]
                    else:
                        t = (elapsed % segment_duration) / segment_duration
                        p1 = waypoints[current_idx]
                        p2 = waypoints[current_idx + 1]
                        
                        tx = int(p1[0] + (p2[0] - p1[0]) * t)
                        ty = int(p1[1] + (p2[1] - p1[1]) * t)
                        target = (tx, ty)
                    
                    # Draw Moving Target
                    cv2.circle(frame, target, 20, (0, 0, 255), -1)
                    cv2.circle(frame, target, 10, (255, 255, 0), -1)
                    
                    cv2.putText(frame, "Follow the Dot", (w//2 - 100, h//2), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                    
                    # Record Data Continuously
                    target_norm_x = target[0] / w
                    target_norm_y = target[1] / h
                    gaze_tracker.add_calibration_point(raw_dx, raw_dy, target_norm_x, target_norm_y)
                    
            else:
                # --- TRACKING LOGIC ---
                
                # Apply Adaptive Smoothing locally
                sx = smoother_x.update(gx)
                sy = smoother_y.update(gy)
                
                # Update trail
                gaze_trail.append((int(sx * w), int(sy * h)))
                
                # Move Mouse (Bypass controller's internal smoothing by passing raw if set up, 
                # but controller applies its own EMA. 
                # Ideally we skip controller smoothing or set it to 1.0 (instant).
                # Let's override controller smoothing temporarily.
                controller.smoother_x.alpha = 1.0 
                controller.smoother_y.alpha = 1.0
                
                controller.execute_action("MOVE", None, sx, sy, frame.shape)
                
                # Visual Debug
                # Draw Trail
                for i in range(1, len(gaze_trail)):
                    # Fade color
                    alpha = i / len(gaze_trail)
                    thickness = int(2 + 4 * alpha)
                    pt1 = gaze_trail[i-1]
                    pt2 = gaze_trail[i]
                    cv2.line(frame, pt1, pt2, (0, 255 * alpha, 255 * (1-alpha)), thickness)
                
                # Current Point
                cx, cy = int(sx * w), int(sy * h)
                cv2.circle(frame, (cx, cy), 10, (0, 255, 0), -1)
                cv2.circle(frame, (cx, cy), 15, (255, 255, 255), 2)

                # Click Logic
                if blink_event == 'DOUBLE_BLINK': 
                     controller.execute_action("DOUBLE_CLICK_LEFT", "START", None, None, frame.shape)
                     cv2.putText(frame, "DOUBLE CLICK!", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
                elif blink_event == 'BLINK':
                     cv2.putText(frame, "BLINK", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        # HUD
        cv2.putText(frame, "Press 'c' to Calibrate", (20, h - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
        
        cv2.imshow('Eye Mouse', frame)
        
        key = cv2.waitKey(5) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('c'):
            is_calibrating = True
            calibration_stage = 1
            calibration_timer = time.time()
            gaze_tracker.reset_calibration()
            print("Starting Calibration...")
            
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
