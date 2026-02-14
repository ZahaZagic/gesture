import pygame
import cv2
import random
import time
import os
import sys
import numpy as np
from core.gaze_tracker import GazeTracker
from utils.smoothing import AdaptiveSmoothing

# --- Configuration ---
ASSETS_DIR = "assets"
LANES = 8
# Colors
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLACK = (0, 0, 0)
YELLOW = (255, 255, 0)
BLUE = (0, 0, 255)
CYAN = (0, 255, 255)

class EyeInput:
    def __init__(self, camera_id=0):
        self.cap = cv2.VideoCapture(camera_id)
        if not self.cap.isOpened():
            print(f"Error: Could not open camera {camera_id}")
            sys.exit(1)
        
        # Get Resolution
        self.cam_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.cam_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Initialize Core components
        self.gaze_tracker = GazeTracker()
        
        # Smoothing (Same params as app_eye_demo.py)
        self.smoother_x = AdaptiveSmoothing(min_alpha=0.02, max_alpha=0.8, slope=20.0)
        self.smoother_y = AdaptiveSmoothing(min_alpha=0.02, max_alpha=0.8, slope=20.0) # Added Y for calibration/debug
        
        self.current_sx = 0.5  # Normalized X position (0.0 to 1.0)
        self.current_sy = 0.5  # Normalized Y position
        self.frame_bgr = None
        
        # Store raw gaze for calibration
        self.last_raw_dx = 0
        self.last_raw_dy = 0

    def update(self):
        ret, frame = self.cap.read()
        if not ret:
            return 0.5, 0.5
            
        # Flip for mirror view (standard for eye control)
        frame = cv2.flip(frame, 1)
        self.frame_bgr = frame
        
        # Process Gaze
        gaze_results = self.gaze_tracker.process_frame(frame)
        gaze_data = self.gaze_tracker.get_gaze_point(gaze_results)
        
        if gaze_data:
            # gaze_data is (norm_x, norm_y, raw_dx, raw_dy)
            gx, gy, raw_dx, raw_dy = gaze_data
            
            self.last_raw_dx = raw_dx
            self.last_raw_dy = raw_dy
            
            # Update Smoothing
            self.current_sx = self.smoother_x.update(gx)
            self.current_sy = self.smoother_y.update(gy)
            
        return self.current_sx, self.current_sy
        
    def add_calibration_point(self, target_x, target_y):
        # target_x, target_y are normalized screen coordinates
        if self.last_raw_dx is not None:
             self.gaze_tracker.add_calibration_point(self.last_raw_dx, self.last_raw_dy, target_x, target_y)

    def finalize_calibration(self):
        self.gaze_tracker.finalize_calibration()
        
    def reset_calibration(self):
        self.gaze_tracker.reset_calibration()
        
    def release(self):
        self.cap.release()

class Ship(pygame.sprite.Sprite):
    def __init__(self, screen_width, screen_height, num_lanes):
        super().__init__()
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.num_lanes = num_lanes
        self.lane_width = screen_width / num_lanes
        
        # Load Image
        img_path = os.path.join(ASSETS_DIR, "ship.png")
        if os.path.exists(img_path):
            self.image = pygame.image.load(img_path).convert()
            self.image.set_colorkey(WHITE)
        else:
            # Fallback
            self.image = pygame.Surface((50, 50))
            self.image.fill(GREEN)
            
        # Scale ship to fit lane (with some padding)
        target_width = int(self.lane_width * 0.8)
        scale_factor = target_width / self.image.get_width()
        new_height = int(self.image.get_height() * scale_factor)
        self.image = pygame.transform.scale(self.image, (target_width, new_height))
        
        self.rect = self.image.get_rect()
        self.rect.bottom = screen_height - 20
        self.current_lane = num_lanes // 2
        
    def update(self, normalized_x):
        # Map 0.0-1.0 to lane index 0-7
        # Clamp input
        nx = max(0.0, min(1.0, normalized_x))
        self.current_lane = int(nx * self.num_lanes)
        
        # Clamp lane (just in case 1.0 maps to 8)
        self.current_lane = min(self.current_lane, self.num_lanes - 1)
        
        # Snap to center of lane
        center_x = (self.current_lane * self.lane_width) + (self.lane_width / 2)
        self.rect.centerx = center_x

class Asteroid(pygame.sprite.Sprite):
    def __init__(self, screen_width, screen_height, num_lanes):
        super().__init__()
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.lane_width = screen_width / num_lanes
        
        # Load Image
        img_path = os.path.join(ASSETS_DIR, "asteroid.png")
        if os.path.exists(img_path):
            self.image = pygame.image.load(img_path).convert()
            self.image.set_colorkey(WHITE)
        else:
            self.image = pygame.Surface((40, 40))
            self.image.fill(RED)
            
        # Scale
        target_width = int(self.lane_width * 0.7)
        scale_factor = target_width / self.image.get_width()
        new_height = int(self.image.get_height() * scale_factor)
        self.image = pygame.transform.scale(self.image, (target_width, new_height))
        
        self.rect = self.image.get_rect()
        
        # Spawn logic
        lane = random.randint(0, num_lanes - 1)
        center_x = (lane * self.lane_width) + (self.lane_width / 2)
        self.rect.centerx = center_x
        self.rect.bottom = 0 # Start just above screen
        
        # Speed (increases slightly with difficulty/score potentially, but fixed for now)
        self.speed = random.randint(3, 8)
        
    def update(self):
        self.rect.y += self.speed
        if self.rect.top > self.screen_height:
            self.kill()

class SpaceRocksGame:
    def __init__(self):
        pygame.init()
        pygame.font.init()
        
        # Initialize Eye Input first to get resolution
        self.eye_input = EyeInput()
        self.width = self.eye_input.cam_w
        self.height = self.eye_input.cam_h
        
        # Create Window
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("SpaceRocks - Eye Controlled")
        
        # Load Backgrounds
        self.bg_images = []
        for bg_name in ["bg_normal.jpg", "bg_pink.jpg", "bg_snow.jpg"]:
            path = os.path.join(ASSETS_DIR, bg_name)
            if os.path.exists(path):
                img = pygame.image.load(path).convert()
                img = pygame.transform.scale(img, (self.width, self.height))
                self.bg_images.append(img)
            else:
                s = pygame.Surface((self.width, self.height))
                s.fill(BLACK)
                self.bg_images.append(s)
                
        self.current_bg = self.bg_images[0]
        
        # Sprites
        self.all_sprites = pygame.sprite.Group()
        self.asteroids = pygame.sprite.Group()
        
        self.ship = Ship(self.width, self.height, LANES)
        self.all_sprites.add(self.ship)
        
        # Game State
        self.clock = pygame.time.Clock()
        self.running = True
        self.start_time = time.time()
        self.score = 0
        self.game_over = False
        
        # Spawning
        self.spawn_timer = 0
        self.spawn_interval = 1000 # ms
        self.last_spawn_time = pygame.time.get_ticks()
        
        # Calibration State
        self.is_calibrating = False
        self.calibration_timer = 0
        self.calibration_points = [
            (50, 50), (self.width-50, 50), (self.width-50, self.height-50), (50, self.height-50), # Corners
            (self.width//2, self.height//2) # Center
        ]
        # We'll use a continuous path for calibration like the demo
        self.calib_waypoints = [
            (50, 50),          # TL
            (self.width-50, 50),        # TR
            (self.width-50, self.height-50),      # BR
            (50, self.height-50),        # BL
            (50, 50),          # TL (Close Box)
            (self.width-50, self.height-50),      # BR (Diag 1)
            (self.width-50, 50),        # TR (Up)
            (50, self.height-50),        # BL (Diag 2)
            (self.width//2, self.height//2)       # Center (End)
        ]
        self.total_calib_duration = 20.0 # seconds
        self.calib_segment_duration = self.total_calib_duration / (len(self.calib_waypoints) - 1)

    def run(self):
        while self.running:
            # 1. Input Processing
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_q:
                        self.running = False
                    if event.key == pygame.K_r and self.game_over:
                        self.reset_game()
                    if event.key == pygame.K_c:
                        self.toggle_calibration()
            
            # Get Gaze Position
            eye_x, eye_y = self.eye_input.update()
            
            if self.is_calibrating:
                self.update_calibration()
                self.draw_calibration(eye_x, eye_y)
            else:
                if not self.game_over:
                    # 2. Update Game Logic
                    self.ship.update(eye_x)
                    
                    # Spawn Asteroids
                    now = pygame.time.get_ticks()
                    if now - self.last_spawn_time > self.spawn_interval:
                        self.spawn_asteroid()
                        self.last_spawn_time = now
                        # Make it harder over time
                        if self.spawn_interval > 300:
                             self.spawn_interval -= 5
                    
                    self.asteroids.update()
                    
                    # Collisions
                    if pygame.sprite.spritecollide(self.ship, self.asteroids, False):
                        self.game_over = True
                        print(f"Game Over! Score: {self.score}")
                    
                    # Score (Time survived)
                    self.score = int(time.time() - self.start_time)
                
                # 3. Draw Game
                self.draw_game(eye_x, eye_y)
            
            # Cap FPS
            self.clock.tick(60)
            
        # Cleanup
        self.eye_input.release()
        pygame.quit()
        
    def toggle_calibration(self):
        self.is_calibrating = not self.is_calibrating
        if self.is_calibrating:
            self.calibration_timer = time.time()
            self.eye_input.reset_calibration()
            print("Starting Calibration...")
        else:
            print("Calibration Cancelled.")

    def update_calibration(self):
        elapsed = time.time() - self.calibration_timer
        
        if elapsed > self.total_calib_duration:
            self.is_calibrating = False
            self.eye_input.finalize_calibration()
            self.reset_game() # Restart game after calibration
            print("Calibration Done")
            return

        # Calculate target position
        current_idx = int(elapsed / self.calib_segment_duration)
        if current_idx >= len(self.calib_waypoints) - 1:
            target = self.calib_waypoints[-1]
        else:
            t = (elapsed % self.calib_segment_duration) / self.calib_segment_duration
            p1 = self.calib_waypoints[current_idx]
            p2 = self.calib_waypoints[current_idx+1]
            tx = int(p1[0] + (p2[0] - p1[0]) * t)
            ty = int(p1[1] + (p2[1] - p1[1]) * t)
            target = (tx, ty)
            
        # Record Data
        target_norm_x = target[0] / self.width
        target_norm_y = target[1] / self.height
        self.eye_input.add_calibration_point(target_norm_x, target_norm_y)
        
        self.current_calib_target = target

    def draw_calibration(self, eye_x, eye_y):
        self.screen.fill(BLACK)
        
        # Draw Target
        if hasattr(self, 'current_calib_target'):
            pygame.draw.circle(self.screen, RED, self.current_calib_target, 20)
            pygame.draw.circle(self.screen, YELLOW, self.current_calib_target, 10)
        
        # Draw Current Gaze (Visual Feedback)
        gaze_pos = (int(eye_x * self.width), int(eye_y * self.height))
        pygame.draw.circle(self.screen, GREEN, gaze_pos, 15, 2)
        pygame.draw.line(self.screen, GREEN, (gaze_pos[0]-20, gaze_pos[1]), (gaze_pos[0]+20, gaze_pos[1]), 1)
        pygame.draw.line(self.screen, GREEN, (gaze_pos[0], gaze_pos[1]-20), (gaze_pos[0], gaze_pos[1]+20), 1)

        # Text
        font = pygame.font.Font(None, 48)
        text = font.render("Follow the Dot", True, WHITE)
        self.screen.blit(text, (self.width//2 - 100, self.height//2))
        
        pygame.display.flip()

    def spawn_asteroid(self):
        asteroid = Asteroid(self.width, self.height, LANES)
        self.all_sprites.add(asteroid)
        self.asteroids.add(asteroid)
        
    def reset_game(self):
        self.game_over = False
        self.score = 0
        self.start_time = time.time()
        self.spawn_interval = 1000
        
        # Clear asteroids
        for a in self.asteroids:
            a.kill()
            
        # Change background for variety
        # self.current_bg = random.choice(self.bg_images) 
        # Keep same bg to avoid flicker or just random
        self.current_bg = random.choice(self.bg_images)
        
    def draw_game(self, eye_x, eye_y):
        # Draw Background
        self.screen.blit(self.current_bg, (0, 0))
        
        # Draw Lanes (faint lines)
        lane_w = self.width / LANES
        for i in range(1, LANES):
            x = i * lane_w
            pygame.draw.line(self.screen, (50, 50, 50), (x, 0), (x, self.height), 1)
            
        # Draw Sprites
        self.all_sprites.draw(self.screen)
        
        # Draw HUD
        font = pygame.font.Font(None, 36)
        score_text = font.render(f"Score: {self.score}", True, WHITE)
        self.screen.blit(score_text, (10, 10))
        instr_text = font.render("Press 'C' to Calibrate", True, CYAN)
        self.screen.blit(instr_text, (10, self.height - 40))
        
        # --- VISUAL GAZE INDICATOR (Green/Red Dot) ---
        gaze_screen_x = int(eye_x * self.width)
        gaze_screen_y = int(eye_y * self.height)
        
        # Draw vertical line at gaze X
        pygame.draw.line(self.screen, (255, 0, 0, 128), (gaze_screen_x, 0), (gaze_screen_x, self.height), 2)
        
        # Draw specific gaze point
        pygame.draw.circle(self.screen, GREEN, (gaze_screen_x, gaze_screen_y), 10)
        
        if self.game_over:
            over_font = pygame.font.Font(None, 72)
            text = over_font.render("GAME OVER", True, RED)
            text_rect = text.get_rect(center=(self.width/2, self.height/2))
            self.screen.blit(text, text_rect)
            
            restart_font = pygame.font.Font(None, 36)
            restart_text = restart_font.render("Press 'R' to Restart", True, WHITE)
            restart_rect = restart_text.get_rect(center=(self.width/2, self.height/2 + 60))
            self.screen.blit(restart_text, restart_rect)
            
        pygame.display.flip()

if __name__ == "__main__":
    game = SpaceRocksGame()
    game.run()
