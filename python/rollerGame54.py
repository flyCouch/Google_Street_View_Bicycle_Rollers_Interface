import pygame
import serial
import threading
import random
import time
import os
import array

# --- CONFIG ---
SERIAL_PORT_1 = 'COM4'
SERIAL_PORT_2 = 'COM5' 
BAUD_RATE = 9600
BASE_W, BASE_H = 1000, 600
WIDE_W = 1800  

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(SCRIPT_DIR, "settings.txt")

# --- SOUND GENERATOR ---
def generate_beep(frequency, duration=0.1, volume=0.1):
    sample_rate = 44100
    n_samples = int(sample_rate * duration)
    buf = array.array('h', [0] * n_samples)
    for i in range(n_samples):
        t = float(i) / sample_rate
        fade = (n_samples - i) / n_samples
        buf[i] = int(volume * 32767 * fade * (0.5 * (1.0 if (i % (sample_rate//frequency) < sample_rate//(2*frequency)) else -1.0)))
    return pygame.mixer.Sound(buf)

def play_chord(freqs, vol=0.1):
    for f in freqs:
        generate_beep(f, duration=0.4, volume=vol).play()

# --- DRAWING FUNCTIONS ---
def draw_bicycle(surface, x, y, size, color, speed, is_moving):
    height_shift = (size * 0.45) if is_moving else 0
    draw_y = y - height_shift
    pygame.draw.ellipse(surface, (20, 40, 20), (x - size/2, y - size/8, size, size/4))
    arm_color = (170, 170, 170)
    bar_width = size * 0.6  
    bar_y = draw_y - size * 0.8
    pygame.draw.line(surface, arm_color, (x - bar_width/2, bar_y), (x + bar_width/2, bar_y), int(size/6))
    glow_factor = min(255, int(speed * 8.0)) 
    hand_color = (255, max(0, 255 - glow_factor), max(0, 255 - glow_factor))
    hand_size = max(1, int(size / 15)) 
    pygame.draw.circle(surface, hand_color, (int(x - bar_width/2), int(bar_y)), hand_size)
    pygame.draw.circle(surface, hand_color, (int(x + bar_width/2), int(bar_y)), hand_size)
    pygame.draw.ellipse(surface, (50, 50, 50), (x - size/6, draw_y - size/4, size/3, size/2))
    pygame.draw.line(surface, color, (x, draw_y), (x, draw_y - size), int(size/4))

def draw_tree(surface, x, y, size):
    pygame.draw.rect(surface, (80, 50, 20), (int(x - size/6), int(y - size/2), int(size/3), int(size/2)))
    pygame.draw.circle(surface, (20, 80, 20), (int(x), int(y - size * 0.7)), int(size/1.5))

def save_settings(sens, obs, npc):
    try:
        with open(SETTINGS_FILE, "w") as f:
            f.write(f"{float(sens)}\n{int(obs)}\n{int(npc)}")
    except: pass

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                lines = [l.strip() for l in f.readlines() if l.strip()]
                if len(lines) >= 3:
                    return float(lines[0]), int(float(lines[1])), int(float(lines[2]))
        except: pass
    return 60.0, 6, 5

class Rider:
    def __init__(self, color, name="Player", bell_pitch=880, chord_freqs=[261, 329, 392]):
        self.name = name
        self.color = color
        self.lane_idx = 2
        self.z = 0; self.speed = 0; self.score = 0
        self.crash_until = 0; self.pulses = 0        
        self.scored_ids = set() 
        self.bell_pitch = bell_pitch
        self.chord_freqs = chord_freqs

class RollerGame:
    def __init__(self):
        pygame.init()
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        self.screen = pygame.display.set_mode((BASE_W, BASE_H), pygame.RESIZABLE)
        self.virtual_surface = pygame.Surface((BASE_W, BASE_H))
        self.is_fullscreen = False
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Impact", 22)
        self.state = "MENU"
        self.num_humans = 1
        
        # P1 (Left View) | P2 (Right View)
        self.p1 = Rider((0, 255, 100), "P1", bell_pitch=1000, chord_freqs=[523, 659, 783])
        self.p2 = Rider((0, 150, 255), "P2", bell_pitch=800, chord_freqs=[392, 493, 587])
        
        self.sensitivity, self.obs_quantity, self.npc_quantity = load_settings()
        self.update_ui_rects()
        self.dragging_sens = self.dragging_obs = self.dragging_npc = False
        self.npcs, self.obstacles, self.trees, self.clouds = [], [], [], []

    def update_ui_rects(self):
        vw = WIDE_W if self.num_humans == 2 else BASE_W
        self.sens_rect = pygame.Rect(vw - 220, 25, 180, 8)
        self.obs_rect = pygame.Rect(vw - 220, 75, 180, 8)
        self.npc_rect = pygame.Rect(vw - 220, 125, 180, 8)

    def setup_race(self):
        random.seed(time.time())
        current_w = WIDE_W if self.num_humans == 2 else BASE_W
        self.virtual_surface = pygame.Surface((current_w, BASE_H))
        self.update_ui_rects()
        self.p1.z = 0; self.p1.score = 0; self.p1.scored_ids.clear()
        self.p2.z = 0; self.p2.score = 0; self.p2.scored_ids.clear()
        self.npcs = []
        for i in range(int(self.npc_quantity)):
            n = Rider((random.randint(50,255), random.randint(50,255), random.randint(50,255)))
            n.id = f"n{i}"; n.lane_idx = random.randint(0,4); n.speed = random.uniform(4, 16); n.z = random.randint(1000, 6000)
            self.npcs.append(n)
        self.obstacles = [{'id':f'o{i}', 'lane':random.randint(0,4), 'z':random.randint(2000,10000), 'color':(random.randint(50,255),random.randint(50,255),random.randint(50,255))} for i in range(int(self.obs_quantity))]
        self.trees = [{'x': random.choice([-1, 1]) * random.randint(850, 1600), 'z': i*450} for i in range(25)]
        self.clouds = [[random.randint(0, current_w), random.randint(20, 250), random.uniform(0.1, 0.4), random.randint(70, 120)] for _ in range(8)]

    def serial_thread(self, port, player):
        try:
            ser = serial.Serial(port, BAUD_RATE, timeout=0.001)
            while True:
                line = ser.readline().decode('utf-8').strip()
                if line == "1": player.pulses += 1
        except: pass

    def update_game(self, now):
        cur_w = self.virtual_surface.get_width()
        for c in self.clouds:
            c[0] += c[2]
            if c[0] > cur_w + 100: c[0] = -100
        
        active = [self.p1] if self.num_humans == 1 else [self.p1, self.p2]
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
                    elif p.z > n.z and n.id not in p.scored_ids:
                        p.score += 500
                        p.scored_ids.add(n.id)
                        generate_beep(p.bell_pitch).play()
                
                if self.num_humans == 2:
                    other = self.p2 if p == self.p1 else self.p1
                    if p.z > other.z and other.name not in p.scored_ids:
                        p.score += 1000
                        p.scored_ids.add(other.name)
                        play_chord(p.chord_freqs)
                    if p.z < other.z and other.name in p.scored_ids:
                        p.scored_ids.remove(other.name)

                for o in self.obstacles:
                    if p.lane_idx == o['lane'] and abs(p.z - o['z']) < 60:
                        p.crash_until = now + 1.2; p.speed = 0; o['z'] += 8000

        lead_z = max(self.p1.z, self.p2.z)
        for n in self.npcs:
            n.z += n.speed
            if lead_z - n.z > 500: 
                n.z = lead_z + random.randint(4000, 8000)
                self.p1.scored_ids.discard(n.id)
                self.p2.scored_ids.discard(n.id)
        for o in self.obstacles:
            if lead_z - o['z'] > 500: o['z'] = lead_z + random.randint(5000, 10000)
        for t in self.trees:
            if lead_z - t['z'] > 1000: t['z'] += 11000

    def draw_view(self, target_player):
        view_w = self.virtual_surface.get_width()
        view = pygame.Surface((view_w, BASE_H))
        view.fill((135, 206, 235)) 
        for c in self.clouds: pygame.draw.circle(view, (255, 255, 255), (int(c[0]), int(c[1])), c[3])
        pygame.draw.rect(view, (34, 139, 34), (0, 300, view_w, 300))
        pygame.draw.polygon(view, (40, 40, 40), [(view_w//2-10, 300), (view_w//2+10, 300), (view_w-20, 600), (20, 600)])
        
        active_riders = [self.p1] if self.num_humans == 1 else [self.p1, self.p2]
        all_objs = sorted(self.trees + self.npcs + self.obstacles + active_riders, 
                          key=lambda x: x.z if hasattr(x, 'z') else x['z'], reverse=True)
        
        for obj in all_objs:
            rel_z = (obj.z if hasattr(obj, 'z') else obj['z']) - target_player.z
            if rel_z < -100 or rel_z > 8500: continue
            scale = 200 / (max(1, rel_z) + 200)

            if isinstance(obj, dict):
                if 'lane' in obj: 
                    x_screen = view_w//2 + ((obj['lane'] - 2) * 200 * scale)
                    w = 170 * scale
                    pygame.draw.rect(view, obj['color'], (int(x_screen-w/2), int(300+(300*scale)-35*scale), int(w), int(70*scale)))
                else: 
                    draw_tree(view, view_w//2 + (obj['x']*scale), 300 + (300*scale), 220*scale)
            else: 
                x_screen = view_w//2 + ((obj.lane_idx - 2) * 200 * scale)
                draw_bicycle(view, int(x_screen), int(300 + (300 * scale)), 130*scale, obj.color, obj.speed, obj.speed > 0.5)
        return view

    def draw_game(self):
        cur_w = self.virtual_surface.get_width()
        if self.num_humans == 1:
            self.virtual_surface.blit(self.draw_view(self.p1), (0, 0))
        else:
            v1 = self.draw_view(self.p1)
            v2 = self.draw_view(self.p2)
            slice_w = cur_w // 2
            self.virtual_surface.blit(v1, (0, 0), (cur_w//2 - slice_w//2, 0, slice_w, BASE_H))
            self.virtual_surface.blit(v2, (cur_w//2, 0), (cur_w//2 - slice_w//2, 0, slice_w, BASE_H))
            pygame.draw.line(self.virtual_surface, (0, 0, 0), (cur_w//2, 0), (cur_w//2, BASE_H), 5)

        self.draw_slider(self.virtual_surface, self.sens_rect, self.sensitivity, 20, 150, "SENS")
        self.draw_slider(self.virtual_surface, self.obs_rect, self.obs_quantity, 0, 10, "BLOCKS")
        self.draw_slider(self.virtual_surface, self.npc_rect, self.npc_quantity, 0, 11, "RANDOMS")
        
        self.virtual_surface.blit(self.font.render(f"P1: {self.p1.score}", True, (0, 80, 0)), (25, 25))
        if self.num_humans == 2: 
            self.virtual_surface.blit(self.font.render(f"P2: {self.p2.score}", True, (0, 0, 80)), (cur_w//2 + 25, 25))

    def draw_slider(self, surf, rect, val, v_min, v_max, label):
        hx = rect.left + ((val - v_min) / (v_max - v_min)) * rect.width
        pygame.draw.rect(surf, (70, 70, 70), rect)
        pygame.draw.rect(surf, (220, 220, 220), (int(hx-6), rect.top-6, 12, 20))
        txt = self.font.render(f"{label}: {int(val)}", True, (0,0,0))
        surf.blit(txt, (rect.left, rect.bottom + 2))

    def run(self):
        threading.Thread(target=self.serial_thread, args=(SERIAL_PORT_1, self.p1), daemon=True).start()
        threading.Thread(target=self.serial_thread, args=(SERIAL_PORT_2, self.p2), daemon=True).start()
        while True:
            now = time.time()
            sw, sh = self.screen.get_size()
            vw = self.virtual_surface.get_width()
            raw_mx, raw_my = pygame.mouse.get_pos()
            mx, my = raw_mx * (vw / sw), raw_my * (BASE_H / sh)
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    save_settings(self.sensitivity, self.obs_quantity, self.npc_quantity)
                    return
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_f:
                        self.is_fullscreen = not self.is_fullscreen
                        if self.is_fullscreen: self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                        else: self.screen = pygame.display.set_mode((BASE_W, BASE_H), pygame.RESIZABLE)
                    
                    if self.state == "MENU":
                        if event.key == pygame.K_1: self.num_humans = 1; self.setup_race()
                        if event.key == pygame.K_2: self.num_humans = 2; self.setup_race()
                        if event.key == pygame.K_RETURN: self.state = "PLAYING"
                    elif self.state == "PLAYING":
                        # KEY CHANGE: WASD = P1 (Left), Arrows = P2 (Right)
                        if self.num_humans == 1:
                            if event.key in [pygame.K_LEFT, pygame.K_a]: self.p1.lane_idx = max(0, self.p1.lane_idx - 1)
                            if event.key in [pygame.K_RIGHT, pygame.K_d]: self.p1.lane_idx = min(4, self.p1.lane_idx + 1)
                        else:
                            if event.key == pygame.K_a: self.p1.lane_idx = max(0, self.p1.lane_idx - 1)
                            if event.key == pygame.K_d: self.p1.lane_idx = min(4, self.p1.lane_idx + 1)
                            if event.key == pygame.K_LEFT: self.p2.lane_idx = max(0, self.p2.lane_idx - 1)
                            if event.key == pygame.K_RIGHT: self.p2.lane_idx = min(4, self.p2.lane_idx + 1)

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
                if self.num_humans == 1:
                    if keys[pygame.K_UP] or keys[pygame.K_w]: self.p1.pulses += 4
                else:
                    # KEY CHANGE: W = P1 speed, Up Arrow = P2 speed
                    if keys[pygame.K_w]: self.p1.pulses += 4
                    if keys[pygame.K_UP]: self.p2.pulses += 4
                
                self.update_game(now); self.draw_game()
            else: 
                self.virtual_surface.fill((30, 30, 60))
                self.virtual_surface.blit(self.font.render(f"PLAYERS: {self.num_humans} (Press 1 or 2)", True, (200,200,200)), (vw//2 - 100, 250))
                self.virtual_surface.blit(self.font.render("PRESS ENTER TO RACE | F for Fullscreen", True, (50,255,50)), (vw//2 - 150, 300))

            scaled_surf = pygame.transform.smoothscale(self.virtual_surface, (sw, sh))
            self.screen.blit(scaled_surf, (0, 0))
            pygame.display.flip(); self.clock.tick(60)

if __name__ == "__main__":
    RollerGame().run()