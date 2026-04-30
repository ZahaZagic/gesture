import cv2
import yaml
import time
import argparse
from core.posture_detector import PostureDetector
from core.spine_kyphosis import SpineKyphosis
from core.face_alignment import FaceAlignment
from core.overlay_renderer import OverlayRenderer
from core.guidance_bubbles import GuidanceBubbles
from core.report_exporter import ReportExporter
from core.posture_assessment import PostureAssessment
from core.posture_notifier import PostureNotifier

def load_config(path="config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def parse_args():
    parser = argparse.ArgumentParser(description="Webcam posture monitor")
    parser.add_argument("--background", action="store_true",
                        help="Run without the OpenCV preview window and notify on sustained bad posture.")
    parser.add_argument("--camera-id", type=int, default=None,
                        help="Override camera_id from config.yaml.")
    return parser.parse_args()

def main():
    args = parse_args()
    config = load_config()
    camera_id = config.get('camera_id', 0) if args.camera_id is None else args.camera_id
    cap = cv2.VideoCapture(camera_id)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.get("width", 1280))
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.get("height", 720))
    cap.set(cv2.CAP_PROP_FPS, config.get("fps_target", 30))
    
    # Initialize Core Modules
    posture_config = config.get("posture", {})
    detector = PostureDetector(
        min_detection_confidence=posture_config.get("min_detection_confidence", 0.5),
        min_tracking_confidence=posture_config.get("min_tracking_confidence", 0.5),
    )
    spine_calc = SpineKyphosis()
    face_calc = FaceAlignment()
    assessor = PostureAssessment(config)
    notifier = PostureNotifier(config)
    
    # Initialize Visualization
    renderer = OverlayRenderer(config)
    bubbles = GuidanceBubbles(config)
    
    # Initialize Reporting
    exporter = ReportExporter()
    
    if args.background:
        print("Starting background posture monitor... Press Ctrl+C to quit.")
    else:
        print("Starting Posture Analysis... Press 'q' to quit, 'r' to generate report, 'c' to recalibrate.")
    
    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                print("Failed to grab frame.")
                break
            
            # 1. Detection
            results = detector.process_frame(frame)
            landmarks = detector.get_landmarks(results)
            world_landmarks = detector.get_world_landmarks(results)

            metrics = {}
            assessment = None

            if landmarks:
                # 2. Analysis
                metrics = spine_calc.calculate_metrics(landmarks, frame.shape, world_landmarks)
                face_metrics = face_calc.check_symmetry(landmarks, frame.shape)
                metrics.update(face_metrics)
                assessment = assessor.assess(metrics)

                if assessment.get("sustained_bad"):
                    issues = ", ".join(issue["message"] for issue in assessment.get("issues", [])[:2])
                    notifier.notify("Posture needs attention", issues or "Please reset your posture.")

                if not args.background:
                    # 3. Visualization
                    renderer.draw_landmarks(frame, landmarks)
                    renderer.draw_lines(frame, landmarks, metrics)
                    renderer.draw_metrics(frame, assessment["metrics"], assessment=assessment)
                    bubbles.update(frame, assessment["metrics"], landmarks, assessment)
            else:
                assessment = assessor.assess(metrics)
                if not args.background:
                    renderer.draw_metrics(frame, {}, assessment=assessment)

            if args.background:
                continue

            # Show Output
            cv2.imshow('Posture Analysis', frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('c'):
                assessor.reset_calibration()
                print("Posture calibration restarted. Sit upright for a few seconds.")
            elif key == ord('r'):
                # Generate Report
                filename = f"screenshot_{int(time.time())}.jpg"
                cv2.imwrite(filename, frame)
                exporter.generate_report(assessment.get("metrics", metrics), filename)
    except KeyboardInterrupt:
        print("Stopping posture monitor.")
            
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
