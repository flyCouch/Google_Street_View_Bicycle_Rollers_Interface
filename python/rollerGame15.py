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
SCREEN_W, SCREEN_H = 1000, 600
SETTINGS_FILE = "settings.txt"

# --- GLOBAL DRAWING FUNCTIONS (Defined first to avoid NameError) ---
def draw_bicycle(surface, x, y, size, color, is_moving):
    height_shift = (size * 0.45) if is_moving else 0
    draw_y = y - height_shift
    # Shadow
    pygame.draw.ellipse(surface, (20, 40, 20), (x - size/2, y - size/8, size, size/4))
    # Frame & Wheels
    pygame.draw.line(surface, color, (x, draw_y), (x, draw_y - size), int(size/4))
    pygame.draw.line(surface, color, (x - size/2, draw_y - size*0.8), (x + size/2, draw_y - size*0.8), int(size/6))
    pygame.draw.ellipse(surface, (50, 50, 50), (x - size/6, draw_y - size/4, size/3, size/2))

def draw_tree(surface, x, y, size):
    # Trunk
    pygame.draw.rect(surface, (80, 50, 20), (int(x - size/6), int(y - size/2), int(size/3), int(size/2)))
    # Leaves
    pygame.draw.circle(surface, (20, 80, 20), (int(x), int(y - size * 0.7)), int(size/1.5))

def load_sensitivity():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return max(20.0, min(float(f.read().strip()), 150.0))
        except: return 60.0
    return 60.0

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
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Impact", 32)
        self.state = "MENU"
        self.num_humans = 1
        self.p1 = Rider((0, 255, 100))
        self.p2 = Rider((0, 150, 255))
        self.sensitivity = load_sensitivity()
        self.slider_rect = pygame.Rect(SCREEN_W - 270, 25, 200, 10)
        self.dragging = False
        self.npcs, self.obstacles, self.trees, self.clouds = [], [], [], []

    def setup_race(self):
        self.p1.z = 0; self.p1.score = 0; self.p1.scored_ids.clear()
        self.p2.z = 0; self.p2.score = 0; self.p2.scored_ids.clear()
        self.npcs = []
        for i in range(12):
            n = Rider((random.randint(50,255), random.randint(50,255), random.randint(50,255)))
            n.id = f"n{i}"; n.lane_idx = random.randint(0,4); n.speed = random.uniform(6, 12); n.z = random.randint(1000, 6000)
            self.npcs.append(n)
        self.obstacles = [{'id':f'o{i}', 'lane':random.randint(0,4), 'z':random.randint(2000,10000), 'color':(255,50,50)} for i in range(6)]
        self.trees = [{'x': random.choice([-1, 1]) * random.randint(850, 1200), 'z': i*450} for i in range(25)]
        self.clouds = [[random.randint(0, SCREEN_W), random.randint(20, 150), random.uniform(0.1, 0.4), random.randint(40, 70)] for _ in range(6)]

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
            if c[0] > SCREEN_W + 100: c[0] = -100

        active = [self.p1] if self.num_humans == 1 else [self.p1, self.p2]
        cam_z = self.p1.z

        for p in active:
            if now < p.crash_until: p.speed *= 0.85
            else:
                p.speed = (p.speed * 0.9) + ((p.pulses * self.sensitivity) * 0.1)
                p.pulses = 0
            p.z += p.speed

            if now >= p.crash_until:
                # NPC Collisions/Passes
                for n in self.npcs:
                    if p.lane_idx == n.lane_idx and abs(p.z - n.z) < 50:
                        p.crash_until = now + 1.2; p.speed = 0; n.z += 6000
                    elif p.lane_idx != n.lane_idx and p.z > n.z and n.id not in p.scored_ids:
                        p.score += 500; p.scored_ids.add(n.id)
                # Obstacles
                for o in self.obstacles:
                    if p.lane_idx == o['lane'] and abs(p.z - o['z']) < 60:
                        p.crash_until = now + 1.2; p.speed = 0; o['z'] += 8000
                # Overtake Bonus
                if self.num_humans == 2:
                    other = self.p2 if p == self.p1 else self.p1
                    if p.lane_idx != other.lane_idx and p.z > other.z and "pp" not in p.scored_ids:
                        p.score += 1000; p.scored_ids.add("pp")
                        if "pp" in other.scored_ids: other.scored_ids.remove("pp")

        # Recycling Logic
        for n in self.npcs:
            n.z += n.speed
            if cam_z - n.z > 50: 
                n.z = cam_z + random.randint(4000, 8000); n.lane_idx = random.randint(0,4)
                for p in active: p.scored_ids.discard(n.id)
        for o in self.obstacles:
            if cam_z - o['z'] > 50: 
                o['z'] = cam_z + random.randint(5000, 10000); o['lane'] = random.randint(0,4)
                o['color'] = (random.randint(100,255), random.randint(100,255), random.randint(100,255))
        for t in self.trees:
            if cam_z - t['z'] > 100: t['z'] += 11000

    def draw_game(self):
        self.screen.fill((135, 206, 235)) 
        for c in self.clouds: pygame.draw.circle(self.screen, (255, 255, 255), (int(c[0]), int(c[1])), c[3])
        pygame.draw.circle(self.screen, (255, 255, 0), (120, 100), 55)
        pygame.draw.rect(self.screen, (34, 139, 34), (0, 300, SCREEN_W, 300))
        pygame.draw.polygon(self.screen, (40, 40, 40), [(495, 300), (505, 300), (SCREEN_W-50, 600), (50, 600)])

        active = [self.p1] if self.num_humans == 1 else [self.p1, self.p2]
        all_objs = sorted(self.trees + self.npcs + self.obstacles + active, key=lambda x: x.z if hasattr(x, 'z') else x['z'], reverse=True)

        for obj in all_objs:
            rel_z = (obj.z if hasattr(obj, 'z') else obj['z']) - self.p1.z
            if rel_z < -100 or rel_z > 8500: continue
            scale = 200 / (max(1, rel_z) + 200)
            
            if isinstance(obj, dict) and 'lane' in obj: # Obstacle
                x = SCREEN_W//2 + ((obj['lane'] - 2) * 200 * scale)
                pygame.draw.rect(self.screen, obj['color'], (int(x-85*scale), int(300+(300*scale)-35*scale), int(170*scale), int(70*scale)))
            elif isinstance(obj, dict): # Tree
                draw_tree(self.screen, SCREEN_W//2 + (obj['x']*scale), 300 + (300*scale), 220*scale)
            else: # Rider
                x = SCREEN_W//2 + ((obj.lane_idx - 2) * 200 * scale)
                draw_bicycle(self.screen, int(x), int(300 + (300 * scale)), 130*scale, obj.color, obj.speed > 0.5)

        # HUD
        score_c = (50, 255, 50)
        self.screen.blit(self.font.render(f"P1: {self.p1.score}", True, score_c), (25, 25))
        if self.num_humans == 2: self.screen.blit(self.font.render(f"P2: {self.p2.score}", True, score_c), (25, 70))
        # Slider
        hx = self.slider_rect.left + ((self.sensitivity - 20.0) / 130.0) * self.slider_rect.width
        pygame.draw.rect(self.screen, (70, 70, 70), self.slider_rect)
        pygame.draw.rect(self.screen, (220, 220, 220), (int(hx-10), 15, 20, 30))
        self.screen.blit(self.font.render(f"SENSITIVITY: {int(self.sensitivity)}", True, (0,0,0)), (SCREEN_W-270, 50))

    def run(self):
        threading.Thread(target=self.serial_thread, args=(SERIAL_PORT_1, self.p1), daemon=True).start()
        threading.Thread(target=self.serial_thread, args=(SERIAL_PORT_2, self.p2), daemon=True).start()
        while True:
            now = time.time(); mx, my = pygame.mouse.get_pos(); m_down = pygame.mouse.get_pressed()[0]
            for event in pygame.event.get():
                if event.type == pygame.QUIT: 
                    with open(SETTINGS_FILE, "w") as f: f.write(str(round(self.sensitivity, 2)))
                    return
                if event.type == pygame.KEYDOWN:
                    if self.state == "MENU":
                        if event.key == pygame.K_1: self.num_humans = 1
                        if event.key == pygame.K_2: self.num_humans = 2
                        if event.key == pygame.K_RETURN: self.setup_race(); self.state = "PLAYING"
                    elif self.state == "PLAYING":
                        if event.key == pygame.K_LEFT: self.p1.lane_idx = max(0, self.p1.lane_idx-1)
                        if event.key == pygame.K_RIGHT: self.p1.lane_idx = min(4, self.p1.lane_idx+1)
                        if event.key == pygame.K_a: self.p2.lane_idx = max(0, self.p2.lane_idx-1)
                        if event.key == pygame.K_d: self.p2.lane_idx = min(4, self.p2.lane_idx+1)
            
            if m_down and self.slider_rect.inflate(20,40).collidepoint(mx,my): self.dragging = True
            elif not m_down: self.dragging = False
            if self.dragging:
                val = (max(self.slider_rect.left, min(mx, self.slider_rect.right)) - self.slider_rect.left) / self.slider_rect.width
                self.sensitivity = 20.0 + (val * 130.0)

            if self.state == "PLAYING":
                keys = pygame.key.get_pressed()
                if keys[pygame.K_UP]: self.p1.pulses += 4
                if keys[pygame.K_w]: self.p2.pulses += 4
                self.update_game(now); self.draw_game()
            else: self.draw_menu()
            pygame.display.flip(); self.clock.tick(60)

    def draw_menu(self):
        self.screen.fill((30, 30, 60))
        self.screen.blit(self.font.render(f"PLAYERS: {self.num_humans} (Press 1 or 2)", True, (200,200,200)), (350, 250))
        self.screen.blit(self.font.render("PRESS ENTER TO RACE", True, (50,255,50)), (350, 300))

if __name__ == "__main__":
    RollerGame().run()