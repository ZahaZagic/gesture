import cv2
import yaml
import time
from core.posture_detector import PostureDetector
from core.spine_kyphosis import SpineKyphosis
from core.face_alignment import FaceAlignment
from core.overlay_renderer import OverlayRenderer
from core.guidance_bubbles import GuidanceBubbles
from core.report_exporter import ReportExporter

def load_config(path="config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def main():
    config = load_config()
    cap = cv2.VideoCapture(config.get('camera_id', 0))
    
    # Initialize Core Modules
    detector = PostureDetector()
    spine_calc = SpineKyphosis()
    face_calc = FaceAlignment()
    
    # Initialize Visualization
    renderer = OverlayRenderer(config)
    bubbles = GuidanceBubbles()
    
    # Initialize Reporting
    exporter = ReportExporter()
    
    print("Starting Posture Analysis... Press 'q' to quit, 'r' to generate report.")
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame.")
            break
            
        # 1. Detection
        results = detector.process_frame(frame)
        landmarks = detector.get_landmarks(results)
        
        metrics = {}
        
        if landmarks:
            # 2. Analysis
            metrics = spine_calc.calculate_metrics(landmarks, frame.shape)
            face_metrics = face_calc.check_symmetry(landmarks, frame.shape)
            metrics.update(face_metrics)
            
            # 3. Visualization
            renderer.draw_landmarks(frame, landmarks)
            renderer.draw_lines(frame, landmarks, metrics)
            renderer.draw_metrics(frame, metrics)
            bubbles.update(frame, metrics, landmarks)
            
        # Show Output
        cv2.imshow('Posture Analysis', frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('r'):
            # Generate Report
            filename = f"screenshot_{int(time.time())}.jpg"
            cv2.imwrite(filename, frame)
            exporter.generate_report(metrics, filename)
            
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
