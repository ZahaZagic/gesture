from pynput.mouse import Button, Controller
import numpy as np
import time
import subprocess
import re
from utils.smoothing import ExponentialSmoothing

class GestureMouseController:
    def __init__(self, config=None):
        self.config = config or {}
        
        # Get Screen Size via subprocess (safer than tkinter on macOS)
        self.screen_width = 1920
        self.screen_height = 1080
        try:
            cmd = ['system_profiler', 'SPDisplaysDataType']
            output = subprocess.check_output(cmd).decode("utf-8")
            match = re.search(r"Resolution: (\d+) x (\d+)", output)
            if match:
                self.screen_width = int(match.group(1))
                self.screen_height = int(match.group(2))
                print(f"Detected Screen Resolution: {self.screen_width}x{self.screen_height}")
        except Exception as e:
            print(f"Warning: Could not detect screen size: {e}. Defaulting to 1920x1080.")
        
        self.mouse = Controller()
        
        # Scaling params
        self.frame_margin = 100 
        
        # Smoothing
        smoothing_factor = self.config.get('gesture', {}).get('smoothing_factor', 0.5)
        self.smoother_x = ExponentialSmoothing(alpha=smoothing_factor)
        self.smoother_y = ExponentialSmoothing(alpha=smoothing_factor)
        
        self.last_click_time = 0
        self.click_cooldown = 0.5
        
    def map_coordinates(self, x_norm, y_norm, frame_width, frame_height):
        """
        Maps normalized coordinates (0-1) from camera to screen pixels.
        """
        # 1. Convert to pixel coordinates in frame
        x_px = x_norm * frame_width
        y_px = y_norm * frame_height
        
        # 2. ROI mapping (10% margins)
        roi_start_x = frame_width * 0.1
        roi_end_x = frame_width * 0.9
        roi_start_y = frame_height * 0.1
        roi_end_y = frame_height * 0.9
        
        # Numpy interp for mapping
        x_mapped = np.interp(x_px, [roi_start_x, roi_end_x], [0, self.screen_width])
        y_mapped = np.interp(y_px, [roi_start_y, roi_end_y], [0, self.screen_height])
        
        # 3. Smooth
        x_smooth = self.smoother_x.update(x_mapped)
        y_smooth = self.smoother_y.update(y_mapped)
        
        # Clamp to screen bounds
        x_smooth = max(0, min(self.screen_width - 1, x_smooth))
        y_smooth = max(0, min(self.screen_height - 1, y_smooth))
        
        return float(x_smooth), float(y_smooth)

    def execute_action(self, state, action_trigger, x_norm, y_norm, frame_shape):
        if x_norm is not None and y_norm is not None:
            h, w, c = frame_shape
            screen_x, screen_y = self.map_coordinates(x_norm, y_norm, w, h)
        else:
            screen_x, screen_y = self.mouse.position

        # MOVE
        if state == "MOVE" and x_norm is not None:
            self.mouse.position = (screen_x, screen_y)
            
        # CLICK LEFT
        elif state == "CLICK_LEFT":
            if action_trigger == "START_CLICK_LEFT":
                if time.time() - self.last_click_time > self.click_cooldown:
                    self.mouse.click(Button.left, 1)
                    self.last_click_time = time.time()
            elif x_norm is not None:
                 self.mouse.position = (screen_x, screen_y)

        # CLICK RIGHT
        elif state == "CLICK_RIGHT":
             if action_trigger == "START_CLICK_RIGHT":
                  if time.time() - self.last_click_time > self.click_cooldown:
                        self.mouse.click(Button.right, 1)
                        self.last_click_time = time.time()
        
        # DRAG (Left Button Hold)
        elif state == "DRAG":
            if action_trigger == "START_DRAG":
                self.mouse.press(Button.left)
            
            self.mouse.position = (screen_x, screen_y)
            
        # SCROLL
        elif state == "SCROLL":
            # Map vertical position to scroll speed
            dy = 0.5 - y_norm 
            scroll_speed = int(dy * 5) # Reduced multiplier for pynput (steps)
            if abs(scroll_speed) > 0:
                self.mouse.scroll(0, scroll_speed)

        # DOUBLE CLICK LEFT
        elif state == "DOUBLE_CLICK_LEFT":
             self.mouse.click(Button.left, 2)


        # DOUBLE CLICK LEFT
        elif state == "DOUBLE_CLICK_LEFT":
             self.mouse.click(Button.left, 2)


    def release_drag(self):
        self.mouse.release(Button.left)
