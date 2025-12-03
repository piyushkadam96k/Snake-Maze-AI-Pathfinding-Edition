import pygame
import random
import sys
import math
import numpy as np
from collections import deque

# ---------------------------
# Basic init and config
# ---------------------------
pygame.init()
# Audio pre-init for better timing
pygame.mixer.pre_init(44100, -16, 2, 512)
try:
    pygame.mixer.init()
except Exception:
    # If audio fails, continue without sound
    pass

BLOCK = 22
COLS = 30
ROWS = 20
WIDTH, HEIGHT = COLS * BLOCK, ROWS * BLOCK
FPS_BASE = 14  # base frames per second; multiplied by speed_mult
speed_mult = 1.0

FONT = pygame.font.SysFont("Consolas", 18)

# Colors and visual params
BG = (8, 12, 18)
GRID = (28, 38, 60)
NEON_HEAD = (80, 255, 140)
NEON_BODY_PALETTE = [
    (255, 140, 60),
    (255, 200, 60),
    (180, 100, 255),
    (60, 200, 255),
]
FOOD_BASE = (255, 80, 80)
WALL_COLOR = (90, 95, 120)
PATH_COLOR = (90, 255, 170)
TEXT = (230, 230, 240)

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Premium Neon Snake — Maze Play")
clock = pygame.time.Clock()

# ---------------------------
# Grid surface
# ---------------------------
grid_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
for x in range(0, WIDTH, BLOCK):
    pygame.draw.line(grid_surf, GRID + (110,), (x, 0), (x, HEIGHT))
for y in range(0, HEIGHT, BLOCK):
    pygame.draw.line(grid_surf, GRID + (110,), (0, y), (WIDTH, y))
# subtle checker
for y in range(ROWS):
    for x in range(COLS):
        if (x + y) % 2 == 0:
            s = pygame.Surface((BLOCK, BLOCK), pygame.SRCALPHA)
            s.fill((255, 255, 255, 6))
            grid_surf.blit(s, (x * BLOCK, y * BLOCK))

# ---------------------------
# Procedural sound helpers
# ---------------------------
def make_tone(freq, duration=0.12, volume=0.25):
    """Return a pygame Sound (stereo) of a sine tone."""
    try:
        sample_rate = 44100
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        wave = np.sin(2 * math.pi * freq * t) * (32767 * volume)
        stereo = np.column_stack((wave, wave)).astype(np.int16)
        return pygame.sndarray.make_sound(stereo)
    except Exception:
        return None

SND_MOVE = make_tone(300, 0.04, 0.12)
SND_EAT = make_tone(920, 0.11, 0.28)
SND_WRAP = make_tone(160, 0.09, 0.18)
SND_SPEED_UP = make_tone(760, 0.07, 0.18)
SND_SPEED_DOWN = make_tone(230, 0.07, 0.18)
SND_MAZE_ENTER = make_tone(520, 0.14, 0.26)
SND_MAZE_EXIT = make_tone(1200, 0.14, 0.28)
SND_INVALID = make_tone(160, 0.06, 0.18)

# safe play
def play(sound):
    try:
        if sound: sound.play()
    except Exception:
        pass

# ---------------------------
# Particle system
# ---------------------------
import time
class Particle:
    def __init__(self, pos, color, size=4, speed=2.5, life=0.6):
        self.x, self.y = pos
        self.size = size
        self.life = life
        self.max_life = life
        self.color = color
        angle = random.random() * math.tau
        self.vx = math.cos(angle) * speed * random.uniform(0.6, 1.2)
        self.vy = math.sin(angle) * speed * random.uniform(0.6, 1.2)

    def update(self, dt):
        self.x += self.vx * dt * 60
        self.y += self.vy * dt * 60
        self.life -= dt
        # small gravity-ish fade
        self.vy += 0.02 * dt * 60

    def draw(self, surf):
        if self.life <= 0:
            return
        alpha = max(0, int(255 * (self.life / self.max_life)))
        col = (self.color[0], self.color[1], self.color[2], alpha)
        s = pygame.Surface((int(self.size*2), int(self.size*2)), pygame.SRCALPHA)
        pygame.draw.circle(s, col, (int(self.size), int(self.size)), int(self.size))
        surf.blit(s, (int(self.x - self.size), int(self.y - self.size)))

particles = []

def update_particles(dt):
    for p in particles[:]:
        p.update(dt)
        if p.life <= 0:
            particles.remove(p)

def draw_particles():
    for p in particles:
        p.draw(screen)

# ---------------------------
# Pathfinding (A*)
# ---------------------------
def neighbors(cell):
    x,y = cell
    for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
        nx,ny = x+dx, y+dy
        if 0 <= nx < COLS and 0 <= ny < ROWS:
            yield (nx, ny)

def a_star(start, goal, blocked):
    if start == goal:
        return []
    open_set = {start}
    came = {}
    g = {start:0}
    f = {start: abs(start[0]-goal[0]) + abs(start[1]-goal[1])}
    while open_set:
        cur = min(open_set, key=lambda c: f.get(c, 10**9))
        if cur == goal:
            path=[]
            while cur in came:
                path.append(cur)
                cur = came[cur]
            path.reverse()
            return path
        open_set.remove(cur)
        for n in neighbors(cur):
            if n in blocked:
                continue
            tg = g[cur] + 1
            if tg < g.get(n, 10**9):
                came[n] = cur
                g[n] = tg
                f[n] = tg + abs(n[0]-goal[0]) + abs(n[1]-goal[1])
                open_set.add(n)
    return None

# ---------------------------
# Maze generator (random walls) — ensures solvable
# ---------------------------
maze_walls = set()
maze_start = (1,1)
maze_goal = (COLS-2, ROWS-2)
maze_path = []

def generate_maze():
    global maze_walls, maze_path
    attempts = 0
    while True:
        attempts += 1
        maze_walls = set()
        # border walls
        for x in range(COLS):
            maze_walls.add((x,0)); maze_walls.add((x,ROWS-1))
        for y in range(ROWS):
            maze_walls.add((0,y)); maze_walls.add((COLS-1,y))
        # random interior walls
        density = (COLS * ROWS) // 3
        for _ in range(density):
            x = random.randint(1, COLS-2)
            y = random.randint(1, ROWS-2)
            if (x,y) not in (maze_start, maze_goal):
                maze_walls.add((x,y))
        path = a_star(maze_start, maze_goal, maze_walls)
        if path:
            maze_path = path
            return
        if attempts > 250:
            # fallback simple border-only maze
            maze_walls = set()
            for x in range(COLS):
                maze_walls.add((x,0)); maze_walls.add((x,ROWS-1))
            for y in range(ROWS):
                maze_walls.add((0,y)); maze_walls.add((COLS-1,y))
            maze_path = a_star(maze_start, maze_goal, maze_walls) or []
            return

# ---------------------------
# Game state
# ---------------------------
snake = deque()
snake.appendleft((COLS//4, ROWS//2))
snake.append((COLS//4-1, ROWS//2))
snake.append((COLS//4-2, ROWS//2))

manual_dir = None
auto_mode = True
score = 0
food = None

def free_cells(blocked):
    return [(x,y) for x in range(COLS) for y in range(ROWS) if (x,y) not in blocked]

def place_food_avoiding(blocked):
    choices = free_cells(blocked)
    return random.choice(choices) if choices else None

def reset_normal():
    global snake, manual_dir, score, food
    snake.clear()
    snake.appendleft((COLS//4, ROWS//2))
    snake.append((COLS//4-1, ROWS//2))
    snake.append((COLS//4-2, ROWS//2))
    manual_dir = None
    score = 0
    food = place_food_avoiding(set(snake))

# Maze play setup
def setup_maze_play():
    global snake, manual_dir, score, food
    snake.clear()
    snake.appendleft(maze_start)
    # small trailing
    if maze_start[0]+1 < COLS and (maze_start[0]+1, maze_start[1]) not in maze_walls:
        snake.append((maze_start[0]+1, maze_start[1]))
    score = 0
    manual_dir = None
    blocked = set(snake) | maze_walls
    food = place_food_avoiding(blocked)

# initialize
reset_normal()
generate_maze()

# ---------------------------
# Animated food (glow/pulse/sparkle)
# ---------------------------
import time
def draw_animated_food():
    if food is None:
        return
    fx = food[0] * BLOCK + BLOCK//2
    fy = food[1] * BLOCK + BLOCK//2
    t = pygame.time.get_ticks() * 0.003
    pulse = (math.sin(t*2.0) * 0.15 + 1.0)  # 0.85..1.15
    radius = int((BLOCK//2 - 4) * pulse)
    # color cycle
    r = int(220 + 35 * math.sin(t*2.3))
    g = int(70 + 60 * math.sin(t*1.6))
    b = int(70 + 60 * math.sin(t*2.9))
    col = (max(0,min(255,r)), max(0,min(255,g)), max(0,min(255,b)))

    # glow surface
    glow_size = radius*3
    glow = pygame.Surface((glow_size, glow_size), pygame.SRCALPHA)
    pygame.draw.circle(glow, (col[0], col[1], col[2], 90), (glow_size//2, glow_size//2), radius+8)
    screen.blit(glow, (fx - glow_size//2, fy - glow_size//2), special_flags=pygame.BLEND_ADD)

    # main circle
    pygame.draw.circle(screen, col, (fx, fy), radius)

    # sparkle
    sparkle_angle = t * 4.0
    sx = fx + int(math.cos(sparkle_angle) * (radius*0.6))
    sy = fy + int(math.sin(sparkle_angle) * (radius*0.6))
    pygame.draw.circle(screen, (255,255,255), (sx, sy), max(1, radius//6))

# ---------------------------
# Add trail particle (neon) at head position
# ---------------------------
def spawn_trail():
    hx, hy = snake[0]
    px = hx * BLOCK + BLOCK//2
    py = hy * BLOCK + BLOCK//2
    # pick color from palette
    col = random.choice(NEON_BODY_PALETTE)
    particles.append(Particle((px, py), col, size=3.2, speed=0.9, life=0.28))

# ---------------------------
# Movement steps
# ---------------------------
def snake_step_normal():
    """Normal world: wrapping allowed (immortal)."""
    global snake, score, food, manual_dir
    hx, hy = snake[0]
    wrapped = False

    if auto_mode:
        blocked = set(list(snake)[:-1])  # allow stepping into tail
        path = a_star((hx,hy), food, blocked) if food is not None else None
        if path:
            nxt = path[0]
        else:
            nxt = ((hx + 1) % COLS, hy)
            wrapped = ((hx + 1) % COLS != hx + 1)
    else:
        if manual_dir is None:
            dx, dy = (1, 0)
        else:
            dx, dy = manual_dir
        nx = (hx + dx) % COLS
        ny = (hy + dy) % ROWS
        nxt = (nx, ny)
        wrapped = (nx != hx + dx or ny != hy + dy)

    # sound + trail
    play(SND_MOVE)
    spawn_trail()

    # move
    snake.appendleft(nxt)
    if nxt == food:
        play(SND_EAT)
        # eat burst particles
        fx = nxt[0]*BLOCK + BLOCK//2
        fy = nxt[1]*BLOCK + BLOCK//2
        for _ in range(22):
            c = random.choice(NEON_BODY_PALETTE)
            particles.append(Particle((fx, fy), c, size=random.uniform(2,5), speed=random.uniform(1.2,3.6), life=random.uniform(0.35,0.85)))
        score += 1
        blocked = set(snake)
        food = place_food_avoiding(blocked)
    else:
        snake.pop()

    if wrapped:
        play(SND_WRAP)

def snake_step_maze():
    """Maze play: no wrapping, walls block movement. Snake starts at maze_start."""
    global snake, score, food, manual_dir
    hx, hy = snake[0]

    if auto_mode:
        blocked = set(list(snake)[:-1]) | maze_walls
        path = a_star((hx,hy), food, blocked) if food is not None else None
        if not path:
            # regenerate if path disappeared
            generate_maze()
            setup_maze_play()
            return
        nxt = path[0]
    else:
        if manual_dir is None:
            return  # don't move until player presses a key
        dx, dy = manual_dir
        cand = (hx + dx, hy + dy)
        # invalid if wall or outside
        if cand in maze_walls or not (0 <= cand[0] < COLS and 0 <= cand[1] < ROWS):
            play(SND_INVALID)
            return
        nxt = cand

    # sound + trail
    play(SND_MOVE)
    spawn_trail()

    # move
    snake.appendleft(nxt)
    if nxt == food:
        play(SND_EAT)
        fx = nxt[0]*BLOCK + BLOCK//2
        fy = nxt[1]*BLOCK + BLOCK//2
        for _ in range(24):
            c = random.choice(NEON_BODY_PALETTE)
            particles.append(Particle((fx, fy), c, size=random.uniform(2,5), speed=random.uniform(1.2,3.8), life=random.uniform(0.35,0.9)))
        score += 1
        blocked = set(snake) | maze_walls
        food = place_food_avoiding(blocked)
        if food is None:
            # completed: regenerate maze
            generate_maze()
            setup_maze_play()
            play(SND_MAZE_EXIT)
    else:
        snake.pop()

# attach helper used above but declared later
def setup_maze_play():
    global snake, manual_dir, score, food
    snake.clear()
    snake.appendleft(maze_start)
    if maze_start[0]+1 < COLS and (maze_start[0]+1, maze_start[1]) not in maze_walls:
        snake.append((maze_start[0]+1, maze_start[1]))
    score = 0
    manual_dir = None
    blocked = set(snake) | maze_walls
    food = place_food_avoiding(blocked)

# ---------------------------
# Drawing functions
# ---------------------------
def draw_snake():
    # head glow
    for i, seg in enumerate(snake):
        px = seg[0]*BLOCK + BLOCK//2
        py = seg[1]*BLOCK + BLOCK//2
        if i == 0:
            # head bright neon with glow
            glow = pygame.Surface((BLOCK*2, BLOCK*2), pygame.SRCALPHA)
            pygame.draw.circle(glow, (NEON_HEAD[0], NEON_HEAD[1], NEON_HEAD[2], 110), (BLOCK, BLOCK), BLOCK//2)
            screen.blit(glow, (px - BLOCK, py - BLOCK), special_flags=pygame.BLEND_ADD)
            pygame.draw.circle(screen, NEON_HEAD, (px, py), BLOCK//2 - 3)
            pygame.draw.circle(screen, (255,255,255), (px, py), 2)  # glossy dot
        else:
            # body: dot gradient picks color by index and size fades a bit
            col = NEON_BODY_PALETTE[i % len(NEON_BODY_PALETTE)]
            size = BLOCK//2 - 5
            pygame.draw.circle(screen, col, (px, py), size)

def draw_normal():
    screen.fill(BG)
    screen.blit(grid_surf, (0,0))
    if food:
        draw_animated_food()
    draw_snake()
    draw_particles()
    txt = FONT.render(f"NORMAL | Score:{score} | Speed:{speed_mult:.2f}x | TAB=Auto/Manual | M=Maze", True, TEXT)
    screen.blit(txt, (8,8))

def draw_maze():
    screen.fill(BG)
    screen.blit(grid_surf, (0,0))
    # walls
    for w in maze_walls:
        pygame.draw.rect(screen, WALL_COLOR, (w[0]*BLOCK, w[1]*BLOCK, BLOCK, BLOCK))
    # path (optional visual)
    for p in maze_path:
        pygame.draw.rect(screen, PATH_COLOR, (p[0]*BLOCK+6, p[1]*BLOCK+6, BLOCK-12, BLOCK-12), border_radius=3)
    # start / goal markers
    pygame.draw.rect(screen, (80,160,255), (maze_start[0]*BLOCK+4, maze_start[1]*BLOCK+4, BLOCK-8, BLOCK-8))
    pygame.draw.rect(screen, (255,200,40), (maze_goal[0]*BLOCK+4, maze_goal[1]*BLOCK+4, BLOCK-8, BLOCK-8))
    # food & snake & particles
    if food:
        draw_animated_food()
    draw_snake()
    draw_particles()
    txt = FONT.render(f"MAZE PLAY | Score:{score} | Speed:{speed_mult:.2f}x | TAB=Auto/Manual | R=Regen | M=Exit", True, TEXT)
    screen.blit(txt, (8,8))

# ---------------------------
# Main loop
# ---------------------------
puzzle_mode = False
running = True

# ensure initial food
if food is None:
    food = place_food_avoiding(set(snake))

while running:
    # tick according to speed multiplier
    tick_val = max(1, int(FPS_BASE * speed_mult))
    dt = clock.tick(tick_val) / 1000.0

    # update particles (dt seconds)
    update_particles(dt)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.KEYDOWN:
            # quit
            if event.key == pygame.K_ESCAPE:
                running = False

            # speed controls (handle keypad as well)
            if event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                speed_mult = min(6.0, speed_mult + 0.25)
                play(SND_SPEED_UP)
            if event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                speed_mult = max(0.25, speed_mult - 0.25)
                play(SND_SPEED_DOWN)

            # toggle maze play
            if event.key == pygame.K_m:
                puzzle_mode = not puzzle_mode
                if puzzle_mode:
                    play(SND_MAZE_ENTER)
                    generate_maze()
                    setup_maze_play()
                else:
                    play(SND_MAZE_EXIT)
                    reset_normal()

            # regen / reset
            if event.key == pygame.K_r:
                if puzzle_mode:
                    generate_maze()
                    setup_maze_play()
                else:
                    reset_normal()

            # toggle auto/manual (note uppercase K_TAB)
            if event.key == pygame.K_TAB:
                auto_mode = not auto_mode

            # movement keys (work in both modes; in maze they respect walls)
            if event.key == pygame.K_UP:
                manual_dir = (0, -1)
            if event.key == pygame.K_DOWN:
                manual_dir = (0, 1)
            if event.key == pygame.K_LEFT:
                manual_dir = (-1, 0)
            if event.key == pygame.K_RIGHT:
                manual_dir = (1, 0)

    # update game state
    if puzzle_mode:
        # ensure food exists in maze
        if food is None:
            blocked = set(snake) | maze_walls
            food = place_food_avoiding(blocked)
            if food is None:
                generate_maze()
                setup_maze_play()
        snake_step_maze()
        draw_maze()
    else:
        if food is None:
            food = place_food_avoiding(set(snake))
        snake_step_normal()
        draw_normal()

    pygame.display.flip()

pygame.quit()
sys.exit()
