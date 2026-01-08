import numpy as np

class ExponentialSmoothing:
    def __init__(self, alpha=0.5):
        """
        alpha: Smoothing factor, 0 < alpha <= 1.
               Lower alpha = more smoothing (slower response).
               Higher alpha = less smoothing (faster response).
        """
        self.alpha = alpha
        self.value = None

    def update(self, new_value):
        if new_value is None:
            return self.value
            
        if self.value is None:
            self.value = np.array(new_value, dtype=np.float32)
        else:
            self.value = self.alpha * np.array(new_value, dtype=np.float32) + \
                         (1 - self.alpha) * self.value
        return self.value

    def reset(self):
        self.value = None

class AdaptiveSmoothing:
    """
    Adaptive Exponential Smoothing.
    Alpha varies based on velocity of the signal.
    """
    def __init__(self, min_alpha=0.01, max_alpha=0.5, slope=10.0):
        self.min_alpha = min_alpha
        self.max_alpha = max_alpha
        self.slope = slope
        self.last_val = None
        self.last_velocity = 0.0
        
    def update(self, val):
        if self.last_val is None:
            self.last_val = val
            return val
            
        # Calculate velocity (change since last frame)
        velocity = abs(val - self.last_val)
        
        # Map velocity to alpha
        target_alpha = self.min_alpha + (self.max_alpha - self.min_alpha) * min(1.0, velocity * self.slope)
        
        # Apply smoothing
        smoothed = self.last_val + target_alpha * (val - self.last_val)
        self.last_val = smoothed
        return smoothed

