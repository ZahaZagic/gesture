import pygame
import cv2
import random
import time
import os
import sys
import numpy as np
import math
from core.gesture_detector import GestureDetector
from core.blink_detector import BlinkDetector
from utils.smoothing import AdaptiveSmoothing

# --- Configuration & Styling ---
ASSETS_DIR = "assets"
LANES = 10
WINDOW_TITLE = "Gaze of the Cosmos"

# Colors (Cosmic Redesign)
PRIMARY = (50, 199, 228)
NEBULA_ROSE = (229, 154, 166)
OBSIDIAN = (26, 29, 32)
BG_DARK = (17, 30, 33)
WHITE = (255, 255, 255)
RED = (255, 50, 50)
GOLD = (255, 215, 0)
SLATE_300 = (203, 213, 225)
SLATE_400 = (148, 163, 184)
SLATE_100 = (241, 245, 249)

# For compatibility with existing code
BLACK = BG_DARK
ROSE_GOLD = NEBULA_ROSE
CYAN = PRIMARY

# --- Asset Management ---

class AssetLoader:
    def __init__(self):
        self.cache = {}

    def get_image_variants(self, folder, base_name):
        """Loads all images that match base_name or base_name_N."""
        # This is a bit complex for a generic loader, let's simplify for the prompt requirements
        # We'll look for [base_name].png, [base_name]1.png, ..., in folder
        images = []
        # Try base name first
        path = os.path.join(ASSETS_DIR, folder, f"{base_name}.png")
        if os.path.exists(path):
            images.append(self.load_image(path))
        
        # Try numbered versions
        for i in range(1, 10):
            path = os.path.join(ASSETS_DIR, folder, f"{base_name}{i}.png")
            if os.path.exists(path):
                images.append(self.load_image(path))
        
        # If folder version empty, try root assets
        if not images:
            path = os.path.join(ASSETS_DIR, f"{base_name}.png")
            if os.path.exists(path):
                images.append(self.load_image(path))

        return images

    def load_image(self, path, flip_y=False, rotate=0):
        if (path, flip_y, rotate) in self.cache:
            return self.cache[(path, flip_y, rotate)]
        try:
            img = pygame.image.load(path).convert_alpha()
            # If the image has no alpha channel or is mostly opaque, black might be the background
            # Check a few corners for colorkey (better than just 0,0)
            is_opaque = True
            for pos in [(0,0), (img.get_width()-1, 0), (0, img.get_height()-1)]:
                if img.get_at(pos)[3] < 200:
                    is_opaque = False
                    break
            if is_opaque:
                 img.set_colorkey((0,0,0))
            
            if flip_y:
                img = pygame.transform.flip(img, False, True)
            if rotate != 0:
                img = pygame.transform.rotate(img, rotate)
            self.cache[(path, flip_y, rotate)] = img
            return img
        except Exception as e:
            print(f"DEBUG: Failed to load image {path}: {e}")
            return None

    def get_paired_variants(self, folder, human_prefix, stone_prefix):
        """Loads pairs of human and stone sprites."""
        pairs = []
        for i in range(1, 10):
            suffix = str(i) if i > 1 else ""
            h_path = os.path.join(ASSETS_DIR, folder, f"{human_prefix}{suffix}.png")
            s_path = os.path.join(ASSETS_DIR, folder, f"{stone_prefix}{suffix}.png")
            
            # Use root folder if not in episode folder
            if not os.path.exists(h_path):
                h_path = os.path.join(ASSETS_DIR, f"Subject {i}.png")
            
            if os.path.exists(h_path):
                h_img = self.load_image(h_path)
                s_img = self.load_image(s_path) if os.path.exists(s_path) else None
                pairs.append((h_img, s_img))
        return pairs

class SoundManager:
    def __init__(self):
        self.sfx = {}
        self.current_bgm = None
        self.debug_mode = True
        self.vol_bgm = 0.5
        self.vol_sfx = 0.7

    def play_bgm(self, filename, folder=""):
        if self.current_bgm:
            pygame.mixer.music.stop()
        path = os.path.join(ASSETS_DIR, folder, filename)
        # Fallback for old naming convention
        if not os.path.exists(path) and "ep" in folder:
            alt_path = os.path.join(ASSETS_DIR, folder, f"bgm_{folder}.wav")
            if os.path.exists(alt_path): path = alt_path
            
        if not os.path.exists(path):
            # Try global audio folder
            path = os.path.join(ASSETS_DIR, "audio effect", filename)

        if os.path.exists(path):
            try:
                pygame.mixer.music.load(path)
                pygame.mixer.music.set_volume(self.vol_bgm)
                pygame.mixer.music.play(-1)
                print(f"DEBUG: Playing BGM: {path}")
                self.current_bgm = path
            except Exception as e:
                print(f"DEBUG: Failed to play BGM {path}: {e}")

    def update_volumes(self, bgm_v, sfx_v):
        self.vol_bgm = bgm_v
        self.vol_sfx = sfx_v
        pygame.mixer.music.set_volume(self.vol_bgm)
        for s in self.sfx.values():
            s.set_volume(self.vol_sfx)

    def play_sfx(self, filename, folder=""):
        path = os.path.join(ASSETS_DIR, folder, filename)
        
        # If not found in specific folder, try known subfolders in audio effects
        if not os.path.exists(path):
            found_sub = False
            for sub in ["laser", "snow", "stone & magic & bones", "fire", "dragons", "scary", "spaceshipt"]:
                p = os.path.join(ASSETS_DIR, "audio effect", sub, filename)
                if os.path.exists(p):
                    path = p
                    found_sub = True
                    break # Found it, break the loop
            
            # If still not found, try the root audio effect folder
            if not found_sub:
                p = os.path.join(ASSETS_DIR, "audio effect", filename)
                if os.path.exists(p):
                    path = p

        if os.path.exists(path):
            if path not in self.sfx:
                try:
                    self.sfx[path] = pygame.mixer.Sound(path)
                except Exception as e:
                    if self.debug_mode:
                        print(f"DEBUG: Failed to load SFX {path}: {e}")
                    return
            self.sfx[path].set_volume(self.vol_sfx)
            self.sfx[path].play()
        else:
            if self.debug_mode:
                print(f"DEBUG: SFX not found: {path} (original: {filename})")

# --- Input Handling ---

class HandInput:
    def __init__(self, camera_id=0):
        self.cap = cv2.VideoCapture(camera_id)
        self.cam_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.cam_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.detector = GestureDetector()
        self.blink_detector = BlinkDetector()
        self.smoother_x = AdaptiveSmoothing(min_alpha=0.1, max_alpha=0.9, slope=15.0)
        self.smoother_y = AdaptiveSmoothing(min_alpha=0.1, max_alpha=0.9, slope=15.0)
        self.current_x = 0.5
        self.current_y = 0.5
        self.landmarks = None

    def update(self):
        ret, frame = self.cap.read()
        if not ret: return 0.5, 0.5, False, None
        
        frame = cv2.flip(frame, 1)
        
        # Gestures
        results = self.detector.process_frame(frame)
        self.landmarks = self.detector.get_landmarks(results)
        
        # Blinks
        blink_results = self.blink_detector.process_frame(frame)
        blink_event = self.blink_detector.check_blink(blink_results)
        
        is_pinching = False
        if self.landmarks:
            l = self.landmarks.landmark
            # Euclidean distance between 4 (thumb tip) and 8 (index tip)
            dist = math.sqrt((l[4].x - l[8].x)**2 + (l[4].y - l[8].y)**2 + (l[4].z - l[8].z)**2)
            is_pinching = dist < 0.05
            
            self.current_x = self.smoother_x.update(l[8].x)
            self.current_y = self.smoother_y.update(l[8].y)
            
        return self.current_x, self.current_y, is_pinching, blink_event

    def release(self):
        self.cap.release()

# --- Episode Logic ---

class Episode:
    def __init__(self, engine, ep_id, name, quote):
        self.engine = engine
        self.id = ep_id
        self.name = name
        self.quote = quote
        self.score = 0
        self.start_time = time.time()
        self.all_sprites = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()
        self.is_finished = False
        self.bg_img = engine.assets.load_image(os.path.join(ASSETS_DIR, f"ep{ep_id}", "bg.jpg"))
        if not self.bg_img: self.bg_img = engine.assets.load_image(os.path.join(ASSETS_DIR, "bg_normal.jpg"))

    def update(self, hx, hy, pinching, blinking):
        pass

    def draw(self, screen):
        # ALWAYS clear screen or blit BG to avoid leftovers from previous episodes
        if self.bg_img:
            screen.blit(pygame.transform.scale(self.bg_img, (self.engine.width, self.engine.height)), (0, 0))
        else:
            screen.fill((10, 10, 20)) # Very dark blue fallback

class AvoidanceEpisode(Episode):
    def __init__(self, engine, ep_id, name, quote, obstacle_key, sfx_key):
        super().__init__(engine, ep_id, name, quote)
        self.lane_w = engine.width / LANES
        self.obstacle_images = engine.assets.get_image_variants(f"ep{ep_id}", obstacle_key)
        self.sfx_key = sfx_key
        flip = (ep_id in [1, 6])
        self.player_img = engine.assets.load_image(os.path.join(ASSETS_DIR, f"ep{ep_id}", "player.png"), flip_y=flip)
        if not self.player_img: self.player_img = engine.assets.load_image(os.path.join(ASSETS_DIR, f"ep{ep_id}", "ship.png"), flip_y=flip)
        if not self.player_img: self.player_img = engine.assets.load_image(os.path.join(ASSETS_DIR, "ship.png"), flip_y=flip)
        
        self.player_rect = pygame.Rect(0, 0, 50, 50)
        self.spawn_timer = 0

    def update(self, hx, hy, pinching, blinking):
        lane = int(max(0, min(1, hx)) * LANES)
        lane = min(lane, LANES - 1)
        self.player_rect.centerx = (lane * self.lane_w) + (self.lane_w / 2)
        self.player_rect.bottom = self.engine.height - 20
        
        # Spawn
        now = pygame.time.get_ticks()
        if now - self.spawn_timer > 1000:
            self.spawn_timer = now
            obs = Obstacle(self.engine.width, self.engine.height, LANES, self.obstacle_images)
            self.all_sprites.add(obs)
            self.enemies.add(obs)
            
        self.all_sprites.update()
        
        # Collision
        for enemy in self.enemies:
            if self.player_rect.colliderect(enemy.rect):
                print(f"DEBUG: {self.name} Collision Hit!")
                self.engine.play_sfx(self.sfx_key, f"ep{self.id}")
                self.is_finished = True
        
        self.score = int(time.time() - self.start_time)

    def draw(self, screen):
        super().draw(screen)
        # Draw Lanes (faint)
        for i in range(1, LANES):
            pygame.draw.line(screen, (40, 40, 60), (i * self.lane_w, 0), (i * self.lane_w, self.engine.height), 1)
        
        self.all_sprites.draw(screen)
        if self.player_img:
            scale = (self.lane_w * 0.8) / self.player_img.get_width()
            img = pygame.transform.scale(self.player_img, (int(self.player_img.get_width()*scale), int(self.player_img.get_height()*scale)))
            # Transparent black square fix: convert_alpha() already handled in AssetLoader
            rect = img.get_rect(center=self.player_rect.center)
            screen.blit(img, rect)
        else:
            pygame.draw.rect(screen, CYAN, self.player_rect)

class MedusaEpisode(Episode):
    def __init__(self, engine, ep_id, name, quote):
        super().__init__(engine, ep_id, name, quote)
        self.pairs = engine.assets.get_paired_variants(f"ep{ep_id}", "human", "stone")
        if not self.pairs:
            # Fallback based on Subject files
            for i in range(1, 10):
                h = engine.assets.load_image(f"assets/Subject {i}.png")
                if h: self.pairs.append((h, None))
        
        self.mirror_img = engine.assets.load_image(os.path.join(ASSETS_DIR, "ep3", "mirror.png"))
        if not self.mirror_img:
            # Fallback placeholder for mirror if missing
            self.mirror_img = pygame.Surface((60, 100), pygame.SRCALPHA)
            pygame.draw.rect(self.mirror_img, (200, 200, 255), (0,0,60,100), border_radius=5)
            pygame.draw.rect(self.mirror_img, WHITE, (5,5,50,90), 2, border_radius=5)

        self.mirrors = pygame.sprite.Group()
        self.spawn_timer = 0
        self.cursor_pos = (0, 0)

    def update(self, hx, hy, pinching, blinking):
        self.cursor_pos = (int(hx * self.engine.width), int(hy * self.engine.height))
        
        now = pygame.time.get_ticks()
        if now - self.spawn_timer > 2000:
            self.spawn_timer = now
            if random.random() < 0.2: # 20% chance to spawn a mirror
                mir = Mirror(self.engine.width, self.engine.height, self.mirror_img)
                self.all_sprites.add(mir)
                self.mirrors.add(mir)
            elif self.pairs:
                h, s = random.choice(self.pairs)
                fig = Figure(self.engine.width, self.engine.height, h, s)
                self.all_sprites.add(fig)
                self.enemies.add(fig)
        
        self.all_sprites.update()
        
        if blinking == 'DOUBLE_BLINK':
            # Check Mirrors first (Fail condition)
            for mir in self.mirrors:
                if mir.rect.collidepoint(self.cursor_pos):
                    print("DEBUG: Blinked on Mirror! Gaze reflected.")
                    self.is_finished = True
                    return

            for fig in self.enemies:
                if fig.rect.collidepoint(self.cursor_pos):
                    if not fig.petrified:
                        # Magic Gaze -> Stone -> Scream
                        self.engine.play_sfx("magicgaze.wav", f"ep{self.id}")
                        fig.petrify()
                        self.engine.play_sfx("sfx.wav", f"ep{self.id}") # stone.wav
                        # Queue scream
                        self.engine.play_sfx("scream.wav", f"ep{self.id}")
                        self.score += 10
        
        if time.time() - self.start_time > 60:
            self.is_finished = True

    def draw(self, screen):
        super().draw(screen)
        self.all_sprites.draw(screen)
        pygame.draw.circle(screen, ROSE_GOLD, self.cursor_pos, 20, 2)

class DragonEpisode(Episode):
    def __init__(self, engine, ep_id, name, quote):
        super().__init__(engine, ep_id, name, quote)
        self.lane_w = engine.width / LANES
        # Try various paths for dragon
        for dp in [os.path.join(ASSETS_DIR, "ep4", "dragon.png"), os.path.join(ASSETS_DIR, "ep4", "Dragon.png")]:
            self.dragon_img = engine.assets.load_image(dp)
            if self.dragon_img: break
            
        self.food_images = [engine.assets.load_image(os.path.join(ASSETS_DIR, "ep4", f), flip_y=True) for f in ["food.png", "food1.png"] if os.path.exists(os.path.join(ASSETS_DIR, "ep4", f))]
        # If list empty, try variants
        if not self.food_images:
            self.food_images = [pygame.transform.flip(img, False, True) for img in engine.assets.get_image_variants("ep4", "food")]
            
        self.enemy_images = [pygame.transform.flip(img, False, True) for img in engine.assets.get_image_variants("ep4", "enemy")]
        
        self.fire_img = engine.assets.load_image(os.path.join(ASSETS_DIR, "ep4", "fire.png"), rotate=-90)

        self.player_rect = pygame.Rect(0, 0, 60, 60)
        self.spawn_timer = 0
        self.projectiles = pygame.sprite.Group()

    def update(self, hx, hy, pinching, blinking):
        lane = int(max(0, min(1, hx)) * LANES)
        lane = min(lane, LANES - 1)
        self.player_rect.centerx = (lane * self.lane_w) + (self.lane_w / 2)
        self.player_rect.bottom = self.engine.height - 20
        
        if pinching:
            # Spit fire (rotated 90deg)
            fire = Projectile(self.player_rect.centerx, self.player_rect.top, self.fire_img)
            self.projectiles.add(fire)
            self.all_sprites.add(fire)
            self.engine.play_sfx("fire.wav", "ep4")
        
        now = pygame.time.get_ticks()
        if now - self.spawn_timer > 1200:
            self.spawn_timer = now
            is_enemy = random.random() > 0.5
            target = DragonTarget(self.engine.width, self.engine.height, LANES, self.enemy_images if is_enemy else self.food_images, is_enemy)
            self.all_sprites.add(target)
            self.enemies.add(target)
            
        self.all_sprites.update()
        
        # Dragon eats or hits
        for target in list(self.enemies):
            if self.player_rect.colliderect(target.rect):
                if target.is_enemy:
                    print("DEBUG: Dragon hit Enemy!")
                    self.is_finished = True
                else:
                    self.score += 5
                    self.engine.play_sfx("eat.wav", "ep4") # Ensure this file is called eat.wav
                    target.kill()
        
        # Fire hits
        pygame.sprite.groupcollide(self.projectiles, self.enemies, True, True)

    def draw(self, screen):
        super().draw(screen)
        self.all_sprites.draw(screen)
        pygame.draw.rect(screen, RED, self.player_rect)

class DesertEpisode(Episode):
    def __init__(self, engine, ep_id, name, quote):
        super().__init__(engine, ep_id, name, quote)
        self.bone_images = engine.assets.get_image_variants("ep5", "bone")
        # Scale bones up (per user request: same size as lens, ~100px)
        self.bone_images = [pygame.transform.scale(img, (100, 100)) for img in self.bone_images]
        self.bones = [] # Hidden BoneLocations
        for _ in range(random.randint(5, 10)):
            self.bones.append({
                'pos': (random.randint(50, engine.width-50), random.randint(50, engine.height-50)),
                'found': False,
                'img': random.choice(self.bone_images) if self.bone_images else None
            })
        self.cursor_pos = (0, 0)
        self.sparkles = [] # Particle effect

    def update(self, hx, hy, pinching, blinking):
        self.cursor_pos = (int(hx * self.engine.width), int(hy * self.engine.height))
        
        # Sparkle logic (glint)
        for b in self.bones:
            if not b['found']:
                dist = math.sqrt((self.cursor_pos[0] - b['pos'][0])**2 + (self.cursor_pos[1] - b['pos'][1])**2)
                if dist < 100:
                    if random.random() < 0.2: # Spawn particles
                        self.sparkles.append({
                            'pos': (b['pos'][0] + random.randint(-20, 20), b['pos'][1] + random.randint(-20, 20)),
                            'life': 1.0,
                            'color': (255, 255, 200, random.randint(150, 255))
                        })
        
        # Update sparkles
        for s in self.sparkles[:]:
            s['life'] -= 0.05
            if s['life'] <= 0:
                self.sparkles.remove(s)
        
        if blinking == 'DOUBLE_BLINK':
            for b in self.bones:
                if not b['found']:
                    dist = math.sqrt((self.cursor_pos[0] - b['pos'][0])**2 + (self.cursor_pos[1] - b['pos'][1])**2)
                    if dist < 50:
                        b['found'] = True
                        self.score += 1
                        self.engine.play_sfx("sfx.wav", f"ep{self.id}") # was dig.wav
        
        if all(b['found'] for b in self.bones) or time.time() - self.start_time > 45:
            self.is_finished = True

    def draw(self, screen):
        super().draw(screen)
        # Flashlight effect: Dark Grey instead of black
        mask = pygame.Surface((self.engine.width, self.engine.height), pygame.SRCALPHA)
        mask.fill((40, 40, 45, 220)) # Dark Grey, slightly transparent
        pygame.draw.circle(mask, (0, 0, 0, 0), self.cursor_pos, 120)
        
        # Draw found bones
        for b in self.bones:
            if b['found']:
                if b['img']: screen.blit(b['img'], b['pos'])
                else: pygame.draw.circle(screen, WHITE, b['pos'], 10)
        
        # Draw Sparkles (Glint)
        for s in self.sparkles:
            size = int(s['life'] * 5)
            if size > 0:
                p_surf = pygame.Surface((size*2, size*2), pygame.SRCALPHA)
                pygame.draw.circle(p_surf, s['color'], (size, size), size)
                screen.blit(p_surf, (s['pos'][0]-size, s['pos'][1]-size))

        screen.blit(mask, (0, 0))

# --- Sprites ---

class Obstacle(pygame.sprite.Sprite):
    def __init__(self, w, h, lanes, images):
        super().__init__()
        self.lane_w = w / lanes
        self.screen_h = h
        if images:
            self.image = random.choice(images)
            self.image = pygame.transform.scale(self.image, (int(self.lane_w*0.7), int(self.lane_w*0.7)))
        else:
            self.image = pygame.Surface((40, 40))
            self.image.fill(WHITE)
        self.rect = self.image.get_rect()
        lane = random.randint(0, lanes - 1)
        self.rect.centerx = (lane * self.lane_w) + (self.lane_w / 2)
        self.rect.bottom = 0
        self.speed = random.randint(4, 7)

    def update(self):
        self.rect.y += self.speed
        if self.rect.top > self.screen_h: self.kill()

class Figure(pygame.sprite.Sprite):
    def __init__(self, w, h, human_img, stone_img):
        super().__init__()
        self.human_img = human_img
        self.stone_img = stone_img
        self.petrified = False
        
        target_w = 60
        if self.human_img:
            scale = target_w / self.human_img.get_width()
            self.image = pygame.transform.scale(self.human_img, (target_w, int(self.human_img.get_height()*scale)))
        else:
            self.image = pygame.Surface((target_w, 100))
            self.image.fill(CYAN)
            
        self.rect = self.image.get_rect(center=(random.randint(50, w-50), random.randint(50, h-50)))
        self.alpha = 255
        self.petrify_time = 0
        self.vx = random.uniform(-2, 2)
        self.vy = random.uniform(-2, 2)
        self.w, self.h = w, h

    def petrify(self):
        self.petrified = True
        self.petrify_time = time.time()
        if self.stone_img:
            # Scale stone to match the human size exactly
            scale = 60.0 / self.stone_img.get_width()
            self.image = pygame.transform.scale(self.stone_img, (60, int(self.stone_img.get_height()*scale)))
        else:
            # Keep surface, just change color to grey
            self.image.fill((100, 100, 100))

    def update(self):
        if not self.petrified:
            self.rect.x += self.vx
            self.rect.y += self.vy
            if self.rect.left < 0 or self.rect.right > self.w: self.vx *= -1
            if self.rect.top < 0 or self.rect.bottom > self.h: self.vy *= -1
        else:
            # Fading effect (3s)
            elapsed = time.time() - self.petrify_time
            if elapsed > 3:
                self.kill()
            else:
                self.alpha = max(0, 255 - int((elapsed / 3.0) * 255))
                # Update image transparency
                self.image.set_alpha(self.alpha)

class Mirror(pygame.sprite.Sprite):
    def __init__(self, w, h, img):
        super().__init__()
        self.w, self.h = w, h
        self.image = pygame.transform.scale(img, (60, 100))
        self.rect = self.image.get_rect(center=(random.randint(50, w-50), random.randint(50, h-50)))
        self.vx = random.uniform(-3, 3)
        self.vy = random.uniform(-3, 3)

    def update(self):
        self.rect.x += self.vx
        self.rect.y += self.vy
        if self.rect.left < 0 or self.rect.right > self.w: self.vx *= -1
        if self.rect.top < 0 or self.rect.bottom > self.h: self.vy *= -1

class DragonTarget(Obstacle):
    def __init__(self, w, h, lanes, images, is_enemy):
        super().__init__(w, h, lanes, images)
        self.is_enemy = is_enemy
        if not images:
            self.image.fill(RED if is_enemy else GOLD)

class Projectile(pygame.sprite.Sprite):
    def __init__(self, x, y, img):
        super().__init__()
        if img: self.image = img
        else:
            self.image = pygame.Surface((10, 20))
            self.image.fill(RED)
        self.rect = self.image.get_rect(center=(x, y))

    def update(self):
        self.rect.y -= 10
        if self.rect.bottom < 0: self.kill()

# --- Main Engine ---

class GazeOfTheCosmosEngine:
    def __init__(self):
        pygame.init()
        pygame.mixer.init()
        pygame.mixer.music.set_volume(0.7)
        self.input = HandInput()
        self.width, self.height = self.input.cam_w, self.input.cam_h
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption(WINDOW_TITLE)
        self.clock = pygame.time.Clock()
        self.assets = AssetLoader()
        self.sounds = SoundManager()
        self.state = "MENU"
        self.debug_mode = True
        self.current_episode = None
        self.font_main = pygame.font.SysFont("Outfit", 36, bold=True)
        self.font_menu = pygame.font.SysFont("Outfit", 28)
        self.font_quote = pygame.font.SysFont("Outfit", 24, italic=True)
        
        self.episodes_data = [
            (1, "Space Fall", "The stars are not silent; they are counting down.", AvoidanceEpisode, ("asteroid", "sfx.wav")),
            (2, "Glacier Run", "The ice remembers the warmth it once lost.", AvoidanceEpisode, ("ice", "sfx.wav")),
            (3, "Curse of Glimpse", "To see is to condemn, to know is to shatter.", MedusaEpisode, ()),
            (4, "Dragon Rage", "Fire is the only language fate understands.", DragonEpisode, ()),
            (5, "Previous Lifetime", "Dust to dust, yet the marrow remains.", DesertEpisode, ()),
            (6, "End of World", "Darkness is a mirror that never blinks.", AvoidanceEpisode, ("asteroid", "sfx.wav"))
        ]
        self.menu_index = 0
        self.intertitle_timer = 0

    def play_sfx(self, filename, folder=""):
        self.sounds.play_sfx(filename, folder)

    def run(self):
        running = True
        while running:
            hx, hy, pinching, blinking = self.input.update()
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_q:
                        if self.state != "MENU":
                            self.state = "MENU"
                            if pygame.mixer.music.get_busy():
                                pygame.mixer.music.stop()
                        else:
                            running = False
            
            if self.state == "MENU":
                self.update_menu(hx, hy, blinking)
                self.draw_menu()
            elif self.state == "SETTINGS":
                self.update_settings(hx, hy, blinking)
                self.draw_settings()
            elif self.state == "INTERTITLE":
                self.update_intertitle()
                self.draw_intertitle()
            elif self.state == "PLAYING":
                self.update_game(hx, hy, pinching, blinking)
                self.draw_game()
                
            pygame.display.flip()
            self.clock.tick(60)
        self.input.release()
        pygame.quit()

    # --- UI Components (Cosmic Redesign) ---

    def draw_cosmic_bg(self):
        # 1. Base dark background
        self.screen.fill(BG_DARK)
        
        # 2. Cyan radial glow (top-left 20% 30%)
        l_glow = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        center_l = (int(self.width * 0.2), int(self.height * 0.3))
        for r in range(400, 0, -5):
            alpha = int(30 * (1 - r/400))
            pygame.draw.circle(l_glow, (*PRIMARY, alpha), center_l, r)
        self.screen.blit(l_glow, (0,0))

        # 3. Rose radial glow (bottom-right 80% 70%)
        r_glow = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        center_r = (int(self.width * 0.8), int(self.height * 0.7))
        for r in range(400, 0, -5):
            alpha = int(30 * (1 - r/400))
            pygame.draw.circle(r_glow, (*NEBULA_ROSE, alpha), center_r, r)
        self.screen.blit(r_glow, (0,0))
        
        # 4. Subtle horizontal linear-like overlay
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        for x in range(0, self.width, 20):
            if x < self.width // 2:
                alpha = int(20 * (1 - x / (self.width//2)))
                pygame.draw.rect(overlay, (*PRIMARY, alpha), (x, 0, 20, self.height))
            else:
                dist = x - (self.width // 2)
                alpha = int(20 * (dist / (self.width//2)))
                pygame.draw.rect(overlay, (*NEBULA_ROSE, alpha), (x, 0, 20, self.height))
        self.screen.blit(overlay, (0,0))

    def draw_frosted_glass_rect(self, rect, border_color=(50, 199, 228, 30), corner_radius=10, bg_alpha=100):
        surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(surf, (26, 29, 32, bg_alpha), (0,0,rect.width,rect.height), border_radius=corner_radius)
        pygame.draw.rect(surf, border_color, (0,0,rect.width,rect.height), width=1, border_radius=corner_radius)
        self.screen.blit(surf, (rect.x, rect.y))

    def update_menu(self, hx, hy, blinking):
        self.cursor_pos = (int(hx * self.width), int(hy * self.height))
        # Add entry for Settings at the bottom
        count = len(self.episodes_data) + 1
        self.menu_index = int(hy * count)
        self.menu_index = max(0, min(count-1, self.menu_index))
        
        if blinking == 'DOUBLE_BLINK':
            if self.menu_index < len(self.episodes_data):
                data = self.episodes_data[self.menu_index]
                cls = data[3]
                args = data[4]
                self.current_episode = cls(self, data[0], data[1], data[2], *args)
                self.state = "INTERTITLE"
                self.intertitle_timer = time.time()
                self.sounds.play_bgm("bgm.wav", f"ep{data[0]}")
            else:
                self.state = "SETTINGS"

    def draw_menu(self):
        self.draw_cosmic_bg()
        
        # --- Header Pill ---
        header_text = "The stars are not silent; they are counting down."
        font_h = pygame.font.SysFont("Space Grotesk", 16)
        rendered_h = font_h.render(header_text.upper(), True, PRIMARY)
        rendered_h.set_alpha(200)
        
        pill_w = rendered_h.get_width() + 60
        header_rect = pygame.Rect(self.width//2 - pill_w//2, 40, pill_w, 40)
        self.draw_frosted_glass_rect(header_rect, border_color=(50, 199, 228, 60), corner_radius=20)
        self.screen.blit(rendered_h, (header_rect.centerx - rendered_h.get_width()//2, header_rect.centery - rendered_h.get_height()//2))

        # --- Title ---
        title_y = 120
        title_surf = self.font_main.render("Gaze of the Cosmos", True, SLATE_100)
        self.screen.blit(title_surf, (self.width//2 - title_surf.get_width()//2, title_y))
        # Glow Line
        line_w = 120
        pygame.draw.rect(self.screen, (*PRIMARY, 40), (self.width//2 - line_w//2, title_y + 53, line_w, 4))
        pygame.draw.line(self.screen, PRIMARY, (self.width//2 - line_w//2, title_y + 55), (self.width//2 + line_w//2, title_y + 55), 1)

        # --- Nav List ---
        nav_start_y = 220
        count = len(self.episodes_data) + 1
        for i in range(count):
            is_active = (i == self.menu_index)
            if i < len(self.episodes_data):
                txt = self.episodes_data[i][1].upper()
                color = PRIMARY if is_active else SLATE_300
            else:
                txt = "CORE"
                color = PRIMARY if is_active else SLATE_300
                
            alpha = 255 if is_active else 150
            font_list = pygame.font.SysFont("Space Grotesk", 28 if is_active else 24)
            label = font_list.render(txt, True, color)
            label.set_alpha(alpha)
            
            rect = label.get_rect(center=(self.width//2, nav_start_y + i * 55))
            self.screen.blit(label, rect)
            
            if is_active:
                # Thin glow underline as in sample
                uw = 60
                pygame.draw.line(self.screen, PRIMARY, (rect.centerx - uw//2, rect.bottom + 5), (rect.centerx + uw//2, rect.bottom + 5), 2)
                # Small bloom
                bloom = pygame.Surface((uw, 6), pygame.SRCALPHA)
                pygame.draw.rect(bloom, (*PRIMARY, 60), (0,0,uw,6), border_radius=3)
                self.screen.blit(bloom, (rect.centerx - uw//2, rect.bottom + 3))

        # --- System Cards (REMOVED per user request) ---
        # --- Bottom Toolbar (REMOVED per user request) ---

        # --- Hand Cursor ---
        if hasattr(self, 'cursor_pos'):
            # Cyan ring
            pygame.draw.circle(self.screen, PRIMARY, self.cursor_pos, 14, 1)
            # Red dot
            pygame.draw.circle(self.screen, RED, self.cursor_pos, 4)

    def update_settings(self, hx, hy, blinking):
        self.cursor_pos = (int(hx * self.width), int(hy * self.height))
        # Split vertical space for Music vs SFX
        if hy < 0.4:
            self.sounds.vol_bgm = max(0.0, min(1.0, hx))
        elif 0.4 <= hy < 0.7:
            self.sounds.vol_sfx = max(0.0, min(1.0, hx))
            
        self.sounds.update_volumes(self.sounds.vol_bgm, self.sounds.vol_sfx)
        
        if blinking == 'DOUBLE_BLINK' and hy > 0.8:
            self.state = "MENU"

    def draw_settings(self):
        self.draw_cosmic_bg()
        title = self.font_main.render("Core Settings", True, SLATE_100)
        self.screen.blit(title, (self.width//2 - title.get_width()//2, 50))
        
        # BGM Slider
        y_bgm = 200
        pygame.draw.rect(self.screen, (26, 29, 32, 150), (self.width//4, y_bgm, self.width//2, 20), border_radius=10)
        pygame.draw.rect(self.screen, PRIMARY, (self.width//4, y_bgm, int((self.width//2)*self.sounds.vol_bgm), 20), border_radius=10)
        txt_bgm = self.font_menu.render(f"MUSIC: {int(self.sounds.vol_bgm*100)}%", True, SLATE_300)
        self.screen.blit(txt_bgm, (self.width//4, y_bgm - 40))
        
        # SFX Slider
        y_sfx = 350
        pygame.draw.rect(self.screen, (26, 29, 32, 150), (self.width//4, y_sfx, self.width//2, 20), border_radius=10)
        pygame.draw.rect(self.screen, NEBULA_ROSE, (self.width//4, y_sfx, int((self.width//2)*self.sounds.vol_sfx), 20), border_radius=10)
        txt_sfx = self.font_menu.render(f"SFX: {int(self.sounds.vol_sfx*100)}%", True, SLATE_300)
        self.screen.blit(txt_sfx, (self.width//4, y_sfx - 40))
        
        # Back Button
        is_back = self.cursor_pos[1] > self.height * 0.8
        color = PRIMARY if is_back else WHITE
        btn_txt = "TERMINATE MODULE" if is_back else "BACK TO BASE"
        btn = self.font_menu.render(btn_txt, True, color)
        rect = btn.get_rect(center=(self.width//2, self.height - 120))
        if is_back:
            self.draw_frosted_glass_rect(rect.inflate(40, 20), border_color=PRIMARY, corner_radius=10)
        self.screen.blit(btn, rect)
        
        if hasattr(self, 'cursor_pos'):
            pygame.draw.circle(self.screen, PRIMARY, self.cursor_pos, 14, 1)
            pygame.draw.circle(self.screen, RED, self.cursor_pos, 4)

    def update_intertitle(self):
        if time.time() - self.intertitle_timer > 3:
            self.state = "PLAYING"

    def draw_intertitle(self):
        self.screen.fill(BLACK)
        words = self.current_episode.quote.split(" ")
        lines = []
        current_line = ""
        for word in words:
            test_line = current_line + " " + word
            if self.font_quote.size(test_line)[0] < self.width - 100:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        lines.append(current_line)
        
        for i, line in enumerate(lines):
            text = self.font_quote.render(line, True, ROSE_GOLD)
            self.screen.blit(text, (self.width//2 - text.get_width()//2, self.height//2 - (len(lines)*15) + i*30))

    def update_game(self, hx, hy, pinching, blinking):
        self.current_episode.update(hx, hy, pinching, blinking)
        if self.current_episode.is_finished:
            self.state = "MENU"

    def draw_game(self):
        self.screen.fill(BLACK)
        if self.current_episode:
            self.current_episode.draw(self.screen)
            # Add a red flash if hit (collision feedback)
            if hasattr(self.current_episode, 'is_finished') and self.current_episode.is_finished:
                flash = pygame.Surface(self.screen.get_size())
                flash.fill((255, 0, 0))
                flash.set_alpha(128)
                self.screen.blit(flash, (0, 0))
                pygame.display.flip()
                pygame.time.delay(100)
        score_text = self.font_menu.render(f"Score: {self.current_episode.score}", True, WHITE)
        self.screen.blit(score_text, (20, 20))

if __name__ == "__main__":
    engine = GazeOfTheCosmosEngine()
    engine.run()
