import pygame
import random
import sys
import numpy as np
from collections import deque

pygame.init()

# =============== CONFIG ===============
BLOCK = 22
COLS = 30
ROWS = 20
WIDTH, HEIGHT = COLS * BLOCK, ROWS * BLOCK
FPS = 14
speed_mult = 1.0

FONT = pygame.font.SysFont("Consolas", 20)

# Colors
BG = (10, 15, 25)
GRID = (40, 60, 80)

HEAD_COLOR = (50, 255, 80)   # neon green
BODY_COLORS = [
    (255, 200, 0),   # yellow
    (255, 150, 0),   # orange
    (255, 90, 0)     # deep orange/red
]

FOOD_COLOR = (255, 50, 50)
WALL_COLOR = (150, 150, 180)
START_COLOR = (90, 170, 255)
GOAL_COLOR = (255, 200, 40)
PATH_COLOR = (80, 255, 150)
TEXT_COLOR = (230, 230, 240)

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Snake Maze Final")
clock = pygame.time.Clock()

# =============== GRID DRAW ===============
grid_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
for x in range(0, WIDTH, BLOCK):
    pygame.draw.line(grid_surf, GRID + (100,), (x, 0), (x, HEIGHT))
for y in range(0, HEIGHT, BLOCK):
    pygame.draw.line(grid_surf, GRID + (100,), (0, y), (WIDTH, y))

# =============== SOUND ===============
pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.mixer.init()

def tone(freq, dur=0.10, vol=0.3):
    sr = 44100
    t = np.linspace(0, dur, int(sr * dur), False)
    wave = np.sin(2*np.pi*freq*t) * (30000*vol)
    stereo = np.column_stack((wave, wave)).astype(np.int16)
    return pygame.sndarray.make_sound(stereo)

snd_move = tone(300, 0.05, 0.2)
snd_eat  = tone(900, 0.12, 0.3)
snd_speed_up = tone(700, 0.08, 0.25)
snd_speed_down = tone(200, 0.08, 0.25)
snd_enter_maze = tone(500, 0.15, 0.3)
snd_exit_maze = tone(1200, 0.15, 0.3)
snd_blocked = tone(150, 0.08, 0.22)

# =============== PATHFINDING (A*) ===============
def neighbors(c):
    x, y = c
    for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
        nx, ny = x+dx, y+dy
        if 0 <= nx < COLS and 0 <= ny < ROWS:
            yield (nx, ny)

def a_star(start, goal, walls):
    open_ = {start}
    came = {}
    g = {start:0}
    f = {start:abs(start[0]-goal[0]) + abs(start[1]-goal[1])}

    while open_:
        cur = min(open_, key=lambda c:f.get(c,999999))

        if cur == goal:
            path=[]
            while cur in came:
                path.append(cur)
                cur = came[cur]
            return path[::-1]

        open_.remove(cur)
        for nb in neighbors(cur):
            if nb in walls:
                continue
            newg = g[cur] + 1
            if newg < g.get(nb, 999999):
                came[nb] = cur
                g[nb] = newg
                f[nb] = newg + abs(nb[0]-goal[0]) + abs(nb[1]-goal[1])
                open_.add(nb)
    return None

# =============== SNAKE SETUP ===============
snake = deque()
snake.appendleft((COLS//4, ROWS//2))
snake.append((COLS//4-1, ROWS//2))
snake.append((COLS//4-2, ROWS//2))

manual_dir = None
auto_mode = True
score = 0

def free_cell(blocked):
    cells = [(x,y) for x in range(COLS) for y in range(ROWS) if (x,y) not in blocked]
    return random.choice(cells) if cells else None

food = free_cell(set(snake))

# =============== MAZE MODE ===============
puzzle_mode = False
maze_walls = set()
maze_start = (1,1)
maze_goal = (COLS-2, ROWS-2)
maze_path = []

def make_maze():
    """Generate solvable maze."""
    global maze_walls, maze_path
    attempts = 0

    while attempts < 300:
        attempts += 1
        maze_walls = set()

        # borders
        for x in range(COLS):
            maze_walls.add((x,0))
            maze_walls.add((x,ROWS-1))
        for y in range(ROWS):
            maze_walls.add((0,y))
            maze_walls.add((COLS-1,y))

        # random walls
        for _ in range((COLS*ROWS)//3):
            x = random.randint(1,COLS-2)
            y = random.randint(1,ROWS-2)
            if (x,y) not in (maze_start, maze_goal):
                maze_walls.add((x,y))

        p = a_star(maze_start, maze_goal, maze_walls)
        if p:
            maze_path = p
            return

    # fallback simple maze
    maze_walls = set()
    for x in range(COLS):
        maze_walls.add((x,0))
        maze_walls.add((x,ROWS-1))
    for y in range(ROWS):
        maze_walls.add((0,y))
        maze_walls.add((COLS-1,y))
    maze_path = a_star(maze_start, maze_goal, maze_walls) or []

def reset_maze_play():
    global snake, manual_dir, score, food
    snake.clear()
    snake.appendleft(maze_start)
    snake.append((maze_start[0]+1, maze_start[1]))

    score = 0
    manual_dir = None
    blocked = set(snake)|maze_walls
    food = free_cell(blocked)

# =============== SNAKE STEP (NORMAL) ===============
def snake_normal_step():
    global snake, food, score, manual_dir
    hx, hy = snake[0]

    if auto_mode:
        blocked = set(list(snake)[:-1])
        path = a_star((hx,hy), food, blocked)
        nxt = path[0] if path else ((hx+1)%COLS, hy)
    else:
        if manual_dir is None:
            dx, dy = (1,0)
        else:
            dx, dy = manual_dir
        nxt = ((hx+dx)%COLS, (hy+dy)%ROWS)

    try: snd_move.play()
    except: pass

    snake.appendleft(nxt)
    if nxt == food:
        snd_eat.play()
        score += 1
        food = free_cell(set(snake))
    else:
        snake.pop()

# =============== SNAKE STEP (MAZE) ===============
def snake_maze_step():
    global snake, food, score, manual_dir

    hx, hy = snake[1]

    if auto_mode:
        blocked = set(list(snake)[:-1]) | maze_walls
        path = a_star((hx,hy), food, blocked)
        if not path:
            make_maze()
            reset_maze_play()
            return
        nxt = path[0]
    else:
        if manual_dir is None:
            return
        dx, dy = manual_dir
        cand = (hx+dx, hy+dy)
        if cand in maze_walls or not (0<=cand[0]<COLS and 0<=cand[1]<ROWS):
            snd_blocked.play()
            return
        nxt = cand

    snd_move.play()

    snake.appendleft(nxt)
    if nxt == food:
        snd_eat.play()
        score += 1
        blocked = set(snake)|maze_walls
        food = free_cell(blocked)
    else:
        snake.pop()

# =============== DRAW ===============
def draw_snake():
    for i, cell in enumerate(snake):
        px, py = cell[0]*BLOCK, cell[1]*BLOCK
        if i == 0:
            color = HEAD_COLOR
            pygame.draw.circle(screen, color, (px+BLOCK//2, py+BLOCK//2), BLOCK//2-2)
        else:
            color = BODY_COLORS[(i % len(BODY_COLORS))]
            pygame.draw.circle(screen, color, (px+BLOCK//2, py+BLOCK//2), BLOCK//2-3)

def draw_normal():
    screen.fill(BG)
    screen.blit(grid_surf,(0,0))

    if food:
        pygame.draw.circle(screen, FOOD_COLOR,
                           (food[0]*BLOCK+BLOCK//2, food[1]*BLOCK+BLOCK//2),
                           BLOCK//2-3)
    draw_snake()

    txt = FONT.render(f"NORMAL | Score:{score} | Speed:{speed_mult:.1f} | TAB=Auto/Manual | M=Maze",
                      True, TEXT_COLOR)
    screen.blit(txt,(8,8))

def draw_maze():
    screen.fill(BG)
    screen.blit(grid_surf,(0,0))

    for w in maze_walls:
        pygame.draw.rect(screen, WALL_COLOR, (w[0]*BLOCK, w[1]*BLOCK, BLOCK, BLOCK))

    pygame.draw.rect(screen, START_COLOR,
                     (maze_start[0]*BLOCK+4, maze_start[1]*BLOCK+4, BLOCK-8, BLOCK-8))
    pygame.draw.rect(screen, GOAL_COLOR,
                     (maze_goal[0]*BLOCK+4, maze_goal[1]*BLOCK+4, BLOCK-8, BLOCK-8))

    if food:
        pygame.draw.circle(screen, FOOD_COLOR,
                           (food[0]*BLOCK+BLOCK//2, food[1]*BLOCK+BLOCK//2),
                           BLOCK//2-3)

    draw_snake()

    txt = FONT.render(f"MAZE PLAY | Score:{score} | Speed:{speed_mult:.1f} | TAB=Auto/Manual | R=Regen | M=Exit",
                      True, TEXT_COLOR)
    screen.blit(txt,(8,8))

# =============== MAIN LOOP ===============
make_maze()

running = True
while running:
    tick_val = max(1, int(FPS * speed_mult))
    clock.tick(tick_val)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.KEYDOWN:

            # Quit
            if event.key == pygame.K_ESCAPE:
                running = False

            # Speed
            if event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                speed_mult = min(5.0, speed_mult+0.2)
                snd_speed_up.play()

            if event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                speed_mult = max(0.3, speed_mult-0.2)
                snd_speed_down.play()

            # Toggle maze play
            if event.key == pygame.K_m:
                puzzle_mode = not puzzle_mode
                if puzzle_mode:
                    snd_enter_maze.play()
                    make_maze()
                    reset_maze_play()
                else:
                    snd_exit_maze.play()
                    snake = deque()
                    snake.appendleft((COLS//4, ROWS//2))
                    snake.append((COLS//4-1, ROWS//2))
                    snake.append((COLS//4-2, ROWS//2))
                    food = free_cell(set(snake))
                    score = 0
                    manual_dir = None

            # Reset normal or maze
            if event.key == pygame.K_r:
                if puzzle_mode:
                    make_maze()
                    reset_maze_play()
                else:
                    snake = deque()
                    snake.appendleft((COLS//4, ROWS//2))
                    snake.append((COLS//4-1, ROWS//2))
                    snake.append((COLS//4-2, ROWS//2))
                    food = free_cell(set(snake))
                    score = 0
                    manual_dir = None

            # Auto/manual toggle
            if event.key == pygame.K_TAB:
                auto_mode = not auto_mode

            # Movement
            if event.key == pygame.K_UP:
                manual_dir = (0,-1)
            if event.key == pygame.K_DOWN:
                manual_dir = (0,1)
            if event.key == pygame.K_LEFT:
                manual_dir = (-1,0)
            if event.key == pygame.K_RIGHT:
                manual_dir = (1,0)

    # Update
    if puzzle_mode:
        snake_maze_step()
        draw_maze()
    else:
        snake_normal_step()
        draw_normal()

    pygame.display.flip()

pygame.quit()
sys.exit()
