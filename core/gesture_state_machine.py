import time
from utils.geometry import calculate_distance_normalized

class GestureStateMachine:
    def __init__(self, config=None):
        self.config = config or {}
        self.state = "IDLE"  # IDLE, MOVE, CLICK_LEFT, CLICK_RIGHT, DRAG, SCROLL
        self.last_state = "IDLE"
        self.state_change_time = time.time()
        
        # Buffer for state stability
        self.state_buffer = []
        self.buffer_size = 3
        
        # Thresholds
        self.pinch_threshold = self.config.get('gesture', {}).get('pinch_distance_threshold', 0.05)
        
    def _detect_gesture(self, landmarks):
        """
        Classifies the current hand pose into a raw gesture.
        """
        # Landmarks:
        # 4: Thumb Tip, 8: Index Tip, 12: Middle Tip, 16: Ring, 20: Pinky
        # 0: Wrist
        
        thumb_tip = landmarks.landmark[4]
        index_tip = landmarks.landmark[8]
        middle_tip = landmarks.landmark[12]
        ring_tip = landmarks.landmark[16]
        pinky_tip = landmarks.landmark[20]
        wrist = landmarks.landmark[0]
        
        # Distances
        pinch_dist = calculate_distance_normalized(thumb_tip, index_tip)
        middle_pinch_dist = calculate_distance_normalized(thumb_tip, middle_tip)
        
        # Check if fingers are extended (simplified check: tip y < pip y)
        # Note: This assumes hand is pointing UP. A more robust way is distance from wrist.
        def is_extended(tip_idx, pip_idx):
            return calculate_distance_normalized(landmarks.landmark[tip_idx], wrist) > \
                   calculate_distance_normalized(landmarks.landmark[pip_idx], wrist) * 1.2

        index_ext = is_extended(8, 6)
        middle_ext = is_extended(12, 10)
        ring_ext = is_extended(16, 14)
        pinky_ext = is_extended(20, 18)
        
        # Logic
        
        # Fist (All closed)
        if not index_ext and not middle_ext and not ring_ext and not pinky_ext:
            return "DRAG"
            
        # Left Click (Pinch Middle+Thumb) - User preference
        if middle_pinch_dist < self.pinch_threshold:
            return "CLICK_LEFT"
            
        # Right Click (Pinch Index+Thumb) - Swapped
        if pinch_dist < self.pinch_threshold:
            return "CLICK_RIGHT"
            
        # Move (Index extended, others closed-ish)
        # Note: Since Index pinch is now Right Click, we need to ensure MOVE doesn't trigger when pinching
        # But MOVE checks for index_ext. When pinching, index is usually curved but tip is far from wrist?
        # Actually, if pinching index, index might not be "extended" fully or pinch_dist check overrides it.
        # We put click checks BEFORE move checks, so it's fine.
        if index_ext and not middle_ext and not ring_ext and not pinky_ext:
            return "MOVE"
            
        # Scroll (Open Hand / spread)
        if index_ext and middle_ext and ring_ext and pinky_ext:
            return "SCROLL"
            
        return "IDLE"

    def update(self, landmarks):
        """
        Updates the state machine based on the new landmarks.
        Returns (current_state, action_trigger)
        """
        if not landmarks:
            self.state = "IDLE"
            return self.state, None
            
        raw_gesture = self._detect_gesture(landmarks)
        
        # Add to buffer
        self.state_buffer.append(raw_gesture)
        if len(self.state_buffer) > self.buffer_size:
            self.state_buffer.pop(0)
            
        # Majority vote for stability
        stable_gesture = max(set(self.state_buffer), key=self.state_buffer.count)
        
        action = None
        
        # State Transitions
        if stable_gesture != self.state:
            # Define valid transitions if needed
            self.last_state = self.state
            self.state = stable_gesture
            self.state_change_time = time.time()
            action = f"START_{self.state}"
        else:
            action = f"HOLD_{self.state}"
            
        return self.state, action
