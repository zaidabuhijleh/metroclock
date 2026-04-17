import random
from PIL import Image, ImageDraw

NAME = "Winter Cabin"
FPS = 5

W, H = 64, 32

SKY         = ( 10,  15,  45)
STAR        = (215, 225, 255)
STAR_DIM    = ( 90, 100, 150)
SNOW_COLOR  = (230, 238, 255)
SNOW_DIM    = (155, 170, 215)
GROUND      = (190, 205, 238)
TREE_DARK   = (  0, 120,  30)   # bright enough to show
TREE_SNOW   = (205, 220, 250)
CABIN_WALL  = (200, 125,  65)   # much brighter warm brown
CABIN_ROOF  = (140,  90,  48)   # visible dark brown
ROOF_SNOW   = (215, 228, 252)
WIN_WARM    = (255, 205,  80)
WIN_GLOW    = (255, 165,  40)
CHIMNEY     = (100,  65,  35)
SMOKE       = (155, 158, 178)

_rng = random.Random(33)
_FLAKES = [(_rng.randint(0, W - 1), _rng.randint(0, H - 8))
           for _ in range(32)]
_STARS = [(x, y) for x in range(W) for y in range(12)
          if _rng.random() < 0.04]


def _draw_trees(draw):
    # (tip_x, tip_y, half_base, layers) — narrow at tip, wide at base
    trees = [(2, 17, 3, 4), (10, 19, 2, 3), (49, 16, 4, 5), (58, 19, 3, 4)]
    for tx, ty, hw, layers in trees:
        for layer in range(layers):
            y = ty + layer * 2
            half = max(1, 1 + layer * (hw - 1) // max(1, layers - 1))
            for x in range(tx - half, tx + half + 1):
                if 0 <= x < W and 0 <= y < H:
                    draw.point((x, y), fill=TREE_DARK)
                if 0 <= x < W and y + 1 < H:
                    c = TREE_SNOW if abs(x - tx) <= half // 2 else TREE_DARK
                    draw.point((x, y + 1), fill=c)


def _draw_cabin(draw):
    # Walls
    draw.rectangle([22, 18, 44, 26], fill=CABIN_WALL)
    # Roof triangle — builds from peak down
    for i in range(8):
        x0, x1 = 21 + i, 45 - i
        draw.line([(x0, 17 - i), (x1, 17 - i)], fill=CABIN_ROOF)
        draw.line([(x0, 17 - i), (x0 + 2, 17 - i)], fill=ROOF_SNOW)
    # Window — bright warm glow
    draw.rectangle([27, 20, 33, 24], fill=WIN_WARM)
    draw.rectangle([29, 21, 31, 23], fill=WIN_GLOW)
    # Door
    draw.rectangle([37, 21, 41, 26], fill=CABIN_ROOF)
    # Chimney
    draw.rectangle([38,  9, 41, 17], fill=CHIMNEY)


def _make_frame(frame):
    img = Image.new("RGB", (W, H), SKY)
    draw = ImageDraw.Draw(img)
    rng = random.Random(frame * 11)

    for sx, sy in _STARS:
        c = STAR if rng.random() < 0.82 else STAR_DIM
        draw.point((sx, sy), fill=c)

    # Ground / snow bank
    draw.rectangle([0, 26, W - 1, H - 1], fill=GROUND)
    for x in range(0, W, 4):
        bump = rng.randint(0, 2)
        draw.rectangle([x, 25 - bump, x + 3, 26], fill=GROUND)

    _draw_trees(draw)
    _draw_cabin(draw)

    # Warm glow spill on snow below window
    for dx in range(-1, 8):
        gx = 27 + dx
        if 0 <= gx < W:
            draw.point((gx, 27), fill=(180, 130, 50))

    # Chimney smoke
    smoke_x = 39 + (frame % 2)
    for dy in range(5):
        sy2 = 8 - dy - (frame % 3)
        if 0 <= sy2 < H:
            draw.point((smoke_x + (dy % 2), sy2), fill=SMOKE)

    for fx, fy in _FLAKES:
        y = (fy + frame * 2) % (H - 7)
        c = SNOW_COLOR if rng.random() < 0.72 else SNOW_DIM
        draw.point((fx, y), fill=c)

    return img


FRAMES = [_make_frame(f) for f in range(4)]
