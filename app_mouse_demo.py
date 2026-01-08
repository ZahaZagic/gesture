import cv2
import yaml
import time
from core.gesture_detector import GestureDetector
from core.gesture_state_machine import GestureStateMachine
from core.gesture_mouse_controller import GestureMouseController
from core.gesture_overlay_renderer import GestureOverlayRenderer
from core.blink_detector import BlinkDetector

def load_config(path="config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)

def main():
    config = load_config()
    cap = cv2.VideoCapture(config.get('camera_id', 0))
    
    # Initialize Core
    detector = GestureDetector()
    blink_detector = BlinkDetector()
    state_machine = GestureStateMachine(config)
    controller = GestureMouseController(config)
    
    # Initialize Visuals
    renderer = GestureOverlayRenderer()
    
    print("Starting Gesture Mouse... Press 'q' to quit.")
    
    # Track previous state to handle drag release
    prev_state = "IDLE"
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        # Flip frame for mirror view (easier for user interaction)
        frame = cv2.flip(frame, 1)
        h, w, c = frame.shape
        
        # 1. Detection
        results = detector.process_frame(frame)
        landmarks = detector.get_landmarks(results)
        
        # Blink Detection
        blink_results = blink_detector.process_frame(frame)
        blink_event = blink_detector.check_blink(blink_results)
        
        current_state = "IDLE"
        
        if landmarks:
            # 2. Logic (State Machine)
            current_state, action = state_machine.update(landmarks)
            
            # 3. Action (Mouse Control)
            # Use Index Finger tip for cursor mapping
            index_tip = landmarks.landmark[8]
            controller.execute_action(current_state, action, index_tip.x, index_tip.y, frame.shape)
            
            # 4. Rendering
            renderer.draw_landmarks(frame, landmarks)
            renderer.draw_cursor_mapper(frame, index_tip)
            
        else:
             state_machine.update(None)
        
        # Priority Override: Double Blink
        if blink_event == 'DOUBLE_BLINK':
             # Execute double click at current pos (ignoring hand mapping for this instant if we want)
             # Or passing None to use current mouse pos
             controller.execute_action("DOUBLE_CLICK_LEFT", "START", None, None, frame.shape)
             cv2.putText(frame, "DOUBLE BLINK!", (w//2 - 100, h//2), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

        # Handle Drag Release logic (if state transitions from DRAG to anything else)
        if prev_state == "DRAG" and current_state != "DRAG":
            controller.release_drag()
            
        prev_state = current_state
        
        # Draw HUD
        renderer.draw_state(frame, current_state)
        renderer.draw_instructions(frame)
        
        cv2.imshow('Gesture Mouse', frame)
        
        if cv2.waitKey(5) & 0xFF == ord('q'):
            break
            
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
