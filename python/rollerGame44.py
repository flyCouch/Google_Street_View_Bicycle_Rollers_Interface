import pygame
import serial
import threading
import random
import time
import os

# --- CONFIG ---
SERIAL_PORT_1 = 'COM4'
SERIAL_PORT_2 = 'COM5' 
BAUD_RATE = 9600
BASE_W, BASE_H = 1000, 600

# Use absolute path to ensure settings.txt is always in the script's folder
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(SCRIPT_DIR, "settings.txt")

# --- GLOBAL DRAWING FUNCTIONS ---
def draw_bicycle(surface, x, y, size, color, speed, is_moving):
    height_shift = (size * 0.45) if is_moving else 0
    draw_y = y - height_shift
    pygame.draw.ellipse(surface, (20, 40, 20), (x - size/2, y - size/8, size, size/4))
    arm_color = (170, 170, 170)
    bar_width = size * 0.6  
    bar_y = draw_y - size * 0.8
    pygame.draw.line(surface, arm_color, (x - bar_width/2, bar_y), (x + bar_width/2, bar_y), int(size/6))
    glow_factor = min(255, int(speed * 2.5)) 
    hand_color = (255, max(0, 255 - glow_factor), max(0, 255 - glow_factor))
    hand_size = max(1, int(size / 15)) 
    pygame.draw.circle(surface, hand_color, (int(x - bar_width/2), int(bar_y)), hand_size)
    pygame.draw.circle(surface, hand_color, (int(x + bar_width/2), int(bar_y)), hand_size)
    pygame.draw.ellipse(surface, (50, 50, 50), (x - size/6, draw_y - size/4, size/3, size/2))
    pygame.draw.line(surface, color, (x, draw_y), (x, draw_y - size), int(size/4))

def draw_tree(surface, x, y, size):
    pygame.draw.rect(surface, (80, 50, 20), (int(x - size/6), int(y - size/2), int(size/3), int(size/2)))
    pygame.draw.circle(surface, (20, 80, 20), (int(x), int(y - size * 0.7)), int(size/1.5))

# --- SETTINGS MANAGEMENT ---
def save_settings(sens, obs, npc):
    """Saves values to the disk immediately."""
    try:
        with open(SETTINGS_FILE, "w") as f:
            f.write(f"{float(sens)}\n{int(obs)}\n{int(npc)}")
    except Exception as e:
        print(f"Save error: {e}")

def load_settings():
    """Loads values or returns defaults (60, 6, 5)."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                lines = [l.strip() for l in f.readlines() if l.strip()]
                if len(lines) >= 3:
                    return float(lines[0]), int(float(lines[1])), int(float(lines[2]))
        except: pass
    return 60.0, 6, 5

class Rider:
    def __init__(self, color):
        self.color = color
        self.lane_idx = 2
        self.z = 0; self.speed = 0; self.score = 0
        self.crash_until = 0; self.pulses = 0        
        self.scored_ids = set() 

class RollerGame:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((BASE_W, BASE_H), pygame.RESIZABLE)
        self.virtual_surface = pygame.Surface((BASE_W, BASE_H))
        self.is_fullscreen = False
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Impact", 22)
        self.state = "MENU"
        self.num_humans = 1
        self.p1 = Rider((0, 255, 100)); self.p2 = Rider((0, 150, 255))
        
        # Load persistent settings
        self.sensitivity, self.obs_quantity, self.npc_quantity = load_settings()
        
        # UI Rects
        self.sens_rect = pygame.Rect(BASE_W - 220, 25, 180, 8)
        self.obs_rect = pygame.Rect(BASE_W - 220, 75, 180, 8)
        self.npc_rect = pygame.Rect(BASE_W - 220, 125, 180, 8)
        self.dragging_sens = self.dragging_obs = self.dragging_npc = False
        self.npcs, self.obstacles, self.trees, self.clouds = [], [], [], []

    def toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        if self.is_fullscreen: self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else: self.screen = pygame.display.set_mode((BASE_W, BASE_H), pygame.RESIZABLE)

    def setup_race(self):
        random.seed(time.time())
        self.p1.z = 0; self.p1.score = 0; self.p1.scored_ids.clear()
        self.p2.z = 0; self.p2.score = 0; self.p2.scored_ids.clear()
        self.npcs = []
        for i in range(int(self.npc_quantity)):
            n = Rider((random.randint(50,255), random.randint(50,255), random.randint(50,255)))
            n.id = f"n{i}"; n.lane_idx = random.randint(0,4); n.speed = random.uniform(4, 16); n.z = random.randint(1000, 6000)
            self.npcs.append(n)
        self.obstacles = [{'id':f'o{i}', 'lane':random.randint(0,4), 'z':random.randint(2000,10000), 'color':(random.randint(50,255),random.randint(50,255),random.randint(50,255))} for i in range(int(self.obs_quantity))]
        self.trees = [{'x': random.choice([-1, 1]) * random.randint(850, 1200), 'z': i*450} for i in range(25)]
        self.clouds = [[random.randint(0, BASE_W), random.randint(20, 280), random.uniform(0.05, 0.15), random.randint(70, 120)] for _ in range(6)]

    def serial_thread(self, port, player):
        try:
            ser = serial.Serial(port, BAUD_RATE, timeout=0.001)
            while True:
                line = ser.readline().decode('utf-8').strip()
                if line == "1": player.pulses += 1
        except: pass

    def update_game(self, now):
        for c in self.clouds:
            c[0] += c[2]
            if c[0] > BASE_W + 100: c[0] = -100
        active = [self.p1] if self.num_humans == 1 else [self.p1, self.p2]
        cam_z = self.p1.z
        for p in active:
            if now < p.crash_until: p.speed *= 0.85
            else:
                p.speed = (p.speed * 0.9) + ((p.pulses * self.sensitivity) * 0.1)
                p.pulses = 0
            p.z += p.speed
            if now >= p.crash_until:
                for n in self.npcs:
                    if p.lane_idx == n.lane_idx and abs(p.z - n.z) < 50:
                        p.crash_until = now + 1.2; p.speed = 0; n.z += 6000
                    elif p.lane_idx != n.lane_idx and p.z > n.z and n.id not in p.scored_ids:
                        p.score += 500; p.scored_ids.add(n.id)
                for o in self.obstacles:
                    if p.lane_idx == o['lane'] and abs(p.z - o['z']) < 60:
                        p.crash_until = now + 1.2; p.speed = 0; o['z'] += 8000
        for n in self.npcs:
            n.z += n.speed
            if cam_z - n.z > 50: 
                n.z = cam_z + random.randint(4000, 8000); n.lane_idx = random.randint(0,4)
                for p in active: p.scored_ids.discard(n.id)
        for o in self.obstacles:
            if cam_z - o['z'] > 50: o['z'] = cam_z + random.randint(5000, 10000); o['lane'] = random.randint(0,4)
        for t in self.trees:
            if cam_z - t['z'] > 100: t['z'] += 11000

    def draw_game(self):
        surf = self.virtual_surface
        surf.fill((135, 206, 235)) 
        for c in self.clouds: pygame.draw.circle(surf, (255, 255, 255), (int(c[0]), int(c[1])), c[3])
        pygame.draw.circle(surf, (255, 255, 0), (120, 100), 55)
        pygame.draw.rect(surf, (34, 139, 34), (0, 300, BASE_W, 300))
        pygame.draw.polygon(surf, (40, 40, 40), [(495, 300), (505, 300), (BASE_W-50, 600), (50, 600)])
        active = [self.p1] if self.num_humans == 1 else [self.p1, self.p2]
        all_objs = sorted(self.trees + self.npcs + self.obstacles + active, key=lambda x: x.z if hasattr(x, 'z') else x['z'], reverse=True)
        for obj in all_objs:
            rel_z = (obj.z if hasattr(obj, 'z') else obj['z']) - self.p1.z
            if rel_z < -100 or rel_z > 8500: continue
            scale = 200 / (max(1, rel_z) + 200)
            if isinstance(obj, dict) and 'lane' in obj: 
                x = BASE_W//2 + ((obj['lane'] - 2) * 200 * scale)
                w = 170 * scale
                pygame.draw.rect(surf, obj['color'], (int(x-w/2), int(300+(300*scale)-35*scale), int(w), int(70*scale)))
            elif isinstance(obj, dict): 
                draw_tree(surf, BASE_W//2 + (obj['x']*scale), 300 + (300*scale), 220*scale)
            else: 
                x = BASE_W//2 + ((obj.lane_idx - 2) * 200 * scale)
                draw_bicycle(surf, int(x), int(300 + (300 * scale)), 130*scale, obj.color, obj.speed, obj.speed > 0.5)
        
        self.draw_slider(surf, self.sens_rect, self.sensitivity, 20, 150, "SENS")
        self.draw_slider(surf, self.obs_rect, self.obs_quantity, 0, 10, "BLOCKS")
        self.draw_slider(surf, self.npc_rect, self.npc_quantity, 0, 11, "RANDOMS")
        
        surf.blit(self.font.render(f"P1: {self.p1.score}", True, (0, 100, 0)), (25, 25))
        if self.num_humans == 2: surf.blit(self.font.render(f"P2: {self.p2.score}", True, (0, 0, 100)), (25, 55))

    def draw_slider(self, surf, rect, val, v_min, v_max, label):
        hx = rect.left + ((val - v_min) / (v_max - v_min)) * rect.width
        pygame.draw.rect(surf, (70, 70, 70), rect)
        pygame.draw.rect(surf, (220, 220, 220), (int(hx-6), rect.top-6, 12, 20))
        surf.blit(self.font.render(f"{label}: {int(val)}", True, (0,0,0)), (rect.left, rect.bottom + 2))

    def run(self):
        threading.Thread(target=self.serial_thread, args=(SERIAL_PORT_1, self.p1), daemon=True).start()
        threading.Thread(target=self.serial_thread, args=(SERIAL_PORT_2, self.p2), daemon=True).start()
        while True:
            now = time.time()
            sw, sh = self.screen.get_size()
            raw_mx, raw_my = pygame.mouse.get_pos()
            mx, my = raw_mx * (BASE_W / sw), raw_my * (BASE_H / sh)
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    save_settings(self.sensitivity, self.obs_quantity, self.npc_quantity)
                    return
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_f: self.toggle_fullscreen()
                    if self.state == "MENU":
                        if event.key == pygame.K_1: self.num_humans = 1
                        if event.key == pygame.K_2: self.num_humans = 2
                        if event.key == pygame.K_RETURN: self.setup_race(); self.state = "PLAYING"
                    elif self.state == "PLAYING":
                        if event.key == pygame.K_LEFT: self.p1.lane_idx = max(0, self.p1.lane_idx-1)
                        if event.key == pygame.K_RIGHT: self.p1.lane_idx = min(4, self.p1.lane_idx+1)
                        if event.key == pygame.K_a: self.p2.lane_idx = max(0, self.p2.lane_idx-1)
                        if event.key == pygame.K_d: self.p2.lane_idx = min(4, self.p2.lane_idx+1)

                if event.type == pygame.MOUSEBUTTONDOWN and self.state == "PLAYING":
                    if self.sens_rect.inflate(10,30).collidepoint(mx,my): self.dragging_sens = True
                    if self.obs_rect.inflate(10,30).collidepoint(mx,my): self.dragging_obs = True
                    if self.npc_rect.inflate(10,30).collidepoint(mx,my): self.dragging_npc = True
                
                if event.type == pygame.MOUSEBUTTONUP:
                    if self.dragging_sens or self.dragging_obs or self.dragging_npc:
                        save_settings(self.sensitivity, self.obs_quantity, self.npc_quantity)
                        if not self.dragging_sens: self.setup_race()
                    self.dragging_sens = self.dragging_obs = self.dragging_npc = False

            if self.state == "PLAYING":
                if self.dragging_sens:
                    self.sensitivity = 20.0 + ((max(self.sens_rect.left, min(mx, self.sens_rect.right)) - self.sens_rect.left) / self.sens_rect.width) * 130.0
                if self.dragging_obs:
                    self.obs_quantity = int(0 + ((max(self.obs_rect.left, min(mx, self.obs_rect.right)) - self.obs_rect.left) / self.obs_rect.width) * 10)
                if self.dragging_npc:
                    self.npc_quantity = int(0 + ((max(self.npc_rect.left, min(mx, self.npc_rect.right)) - self.npc_rect.left) / self.npc_rect.width) * 11)

                keys = pygame.key.get_pressed()
                if keys[pygame.K_UP]: self.p1.pulses += 4
                if keys[pygame.K_w]: self.p2.pulses += 4
                self.update_game(now); self.draw_game()
            else: 
                self.virtual_surface.fill((30, 30, 60))
                self.virtual_surface.blit(self.font.render(f"PLAYERS: {self.num_humans} (Press 1 or 2)", True, (200,200,200)), (350, 250))
                self.virtual_surface.blit(self.font.render("PRESS ENTER TO RACE | F for Fullscreen", True, (50,255,50)), (310, 300))

            scaled_surf = pygame.transform.smoothscale(self.virtual_surface, (sw, sh))
            self.screen.blit(scaled_surf, (0, 0))
            pygame.display.flip(); self.clock.tick(60)

if __name__ == "__main__":
    RollerGame().run()