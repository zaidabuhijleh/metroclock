import random
from PIL import Image, ImageDraw

NAME = "Winter Cabin"
FPS = 5

W, H = 64, 32

SKY        = (8,  12,  35)
STAR       = (200, 215, 255)
STAR_DIM   = (80,  90, 140)
SNOW_COLOR = (220, 230, 255)
SNOW_DIM   = (160, 175, 210)
GROUND     = (180, 195, 230)
GROUND_SHADOW=(130,145,180)
TREE_DARK  = (15,  30,  20)
TREE_SNOW  = (200, 215, 245)
CABIN_WALL = (90,  55,  30)
CABIN_ROOF = (50,  35,  20)
ROOF_SNOW  = (200, 215, 245)
WINDOW_WARM= (255, 200,  80)
WINDOW_GLOW= (255, 160,  40)
CHIMNEY    = (60,  40,  25)
SMOKE      = (140, 140, 160)

_rng = random.Random(33)

# Snowflake starting positions: (x, y)
_FLAKES = [(_rng.randint(0, W - 1), _rng.randint(0, H - 8))
           for _ in range(30)]

_STARS = [(x, y) for x in range(W) for y in range(10)
          if _rng.random() < 0.04]


def _draw_trees(draw):
    trees = [(2, 18, 3, 4), (10, 20, 2, 3), (48, 17, 4, 5), (57, 20, 3, 4)]
    for tx, ty, hw, layers in trees:
        for layer in range(layers):
            y = ty + layer * 2
            half = max(1, hw - layer + 1)
            # dark trunk at base, snow cap on top half of each layer
            for x in range(tx - half, tx + half + 1):
                if 0 <= x < W and 0 <= y < H:
                    draw.point((x, y), fill=TREE_DARK)
                if 0 <= x < W and y + 1 < H and abs(x - tx) <= max(0, half - 1):
                    c = TREE_SNOW if abs(x - tx) <= half // 2 else TREE_DARK
                    draw.point((x, y + 1), fill=c)


def _draw_cabin(draw):
    # Walls
    draw.rectangle([22, 19, 42, 27], fill=CABIN_WALL)
    # Roof (triangle approximation)
    for i in range(7):
        x0 = 20 + i
        x1 = 44 - i
        draw.line([(x0, 18 - i), (x1, 18 - i)], fill=CABIN_ROOF)
    # Roof snow
    for i in range(7):
        x0 = 20 + i
        x1 = 44 - i
        draw.line([(x0, 18 - i), (min(x0 + 2, x1), 18 - i)], fill=ROOF_SNOW)
    # Window
    draw.rectangle([28, 21, 33, 25], fill=WINDOW_WARM)
    draw.rectangle([29, 22, 32, 24], fill=WINDOW_GLOW)
    # Door
    draw.rectangle([36, 22, 40, 27], fill=CABIN_ROOF)
    # Chimney
    draw.rectangle([38, 11, 41, 18], fill=CHIMNEY)


def _make_frame(frame):
    img = Image.new("RGB", (W, H), SKY)
    draw = ImageDraw.Draw(img)

    rng = random.Random(frame * 11)

    # Stars
    for sx, sy in _STARS:
        c = STAR if rng.random() < 0.8 else STAR_DIM
        draw.point((sx, sy), fill=c)

    # Ground / snow bank
    draw.rectangle([0, 27, W - 1, H - 1], fill=GROUND)
    for x in range(0, W, 4):
        bump = rng.randint(0, 2)
        draw.rectangle([x, 26 - bump, x + 3, 27], fill=GROUND)

    _draw_trees(draw)
    _draw_cabin(draw)

    # Chimney smoke
    smoke_x = 39 + (frame % 2)
    for dy in range(4):
        sy2 = 10 - dy - (frame % 3)
        if 0 <= sy2 < H:
            draw.point((smoke_x + (dy % 2), sy2), fill=SMOKE)

    # Snowflakes falling — 4 frame cycle, each flake drops 2px per frame
    for fx, fy in _FLAKES:
        y = (fy + frame * 2) % (H - 7)
        c = SNOW_COLOR if rng.random() < 0.7 else SNOW_DIM
        draw.point((fx, y), fill=c)

    return img


FRAMES = [_make_frame(f) for f in range(4)]
