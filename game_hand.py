import pygame
import cv2
import random
import time
import os
import sys
import numpy as np
from core.gesture_detector import GestureDetector
from core.gesture_overlay_renderer import GestureOverlayRenderer
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

class HandInput:
    def __init__(self, camera_id=0):
        self.cap = cv2.VideoCapture(camera_id)
        if not self.cap.isOpened():
            print(f"Error: Could not open camera {camera_id}")
            sys.exit(1)
        
        # Get Resolution
        self.cam_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.cam_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Initialize Core components
        self.detector = GestureDetector()
        self.renderer = GestureOverlayRenderer() # For drawing landmarks
        
        # Smoothing (Using same params as EyeInput for consistency but hand might be faster)
        # Maybe faster response for hand is better?
        self.smoother_x = AdaptiveSmoothing(min_alpha=0.1, max_alpha=0.9, slope=15.0)
        self.smoother_y = AdaptiveSmoothing(min_alpha=0.1, max_alpha=0.9, slope=15.0)
        
        self.current_sx = 0.5  # Normalized X position (0.0 to 1.0)
        self.current_sy = 0.5  # Normalized Y position
        self.frame_bgr = None
        self.landmarks = None

    def update(self):
        ret, frame = self.cap.read()
        if not ret:
            return 0.5, 0.5
            
        # Flip for mirror view (standard like mouse demo)
        frame = cv2.flip(frame, 1)
        self.frame_bgr = frame
        
        # Process Hand
        results = self.detector.process_frame(frame)
        self.landmarks = self.detector.get_landmarks(results)
        
        gx, gy = self.current_sx, self.current_sy
        
        # If hand detected, use Index Finger Tip (Landmark 8)
        if self.landmarks:
             index_tip = self.landmarks.landmark[8]
             gx = index_tip.x
             gy = index_tip.y
        else:
            # If hand lost, maybe stay at last position or center slowly?
            # Let's keep last position for stickiness or center?
            # Keeping last position (gx, gy unchanged from prev loop, wait no)
            # Actually if landmarks is None, we just return current smoothed state (no update)
            # But let's verify if we should smooth towards center.
            # Keeping last valid input is usually better UX than snapping to center.
            pass

        # Update Smoothing
        self.current_sx = self.smoother_x.update(gx)
        self.current_sy = self.smoother_y.update(gy)
            
        return self.current_sx, self.current_sy
        
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
        
        # Initialize Hand Input first to get resolution
        self.hand_input = HandInput()
        self.width = self.hand_input.cam_w
        self.height = self.hand_input.cam_h
        
        # Create Window
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("SpaceRocks - Hand Controlled")
        
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
            
            # Get Hand Position
            hand_x, hand_y = self.hand_input.update()
            
            if not self.game_over:
                # 2. Update Game Logic
                self.ship.update(hand_x)
                
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
            self.draw_game(hand_x, hand_y)
            
            # Cap FPS
            self.clock.tick(60)
            
        # Cleanup
        self.hand_input.release()
        pygame.quit()
        
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
        self.current_bg = random.choice(self.bg_images)
        
    def draw_game(self, hand_x, hand_y):
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
        
        # --- VISUAL HAND INDICATOR ---
        hand_screen_x = int(hand_x * self.width)
        
        # Draw vertical line at hand X
        pygame.draw.line(self.screen, (0, 0, 255, 128), (hand_screen_x, 0), (hand_screen_x, self.height), 2)
        
        # Draw Hand Landmarks Overlay (Optional but cool)
        # We need access to the raw frame or just draw points ourself.
        # It's tricky because the game is Pygame, but frame is OpenCV.
        # We can draw circles in Pygame if we map landmarks. 
        if self.hand_input.landmarks:
             # Draw simplistic skeleton
             landmarks = self.hand_input.landmarks.landmark
             
             # Index Finger Tip
             idx_tip = landmarks[8]
             tx, ty = int(idx_tip.x * self.width), int(idx_tip.y * self.height)
             pygame.draw.circle(self.screen, CYAN, (tx, ty), 10)
             
             # Optionally draw others small
             for lm in landmarks:
                 lx, ly = int(lm.x * self.width), int(lm.y * self.height)
                 pygame.draw.circle(self.screen, (100, 100, 255), (lx, ly), 3)

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
