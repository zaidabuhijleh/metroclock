import random
from PIL import Image, ImageDraw

NAME = "Alpine Cabin"
FPS = 4

W, H = 64, 32

SKY_TOP = (90, 175, 255)
SKY_BOT = (190, 230, 255)
SUN = (255, 225, 120)
SUN_GLOW = (255, 245, 170)
MOUNTAIN_BACK = (180, 210, 245)
MOUNTAIN_FRONT = (140, 185, 235)
SNOW = (235, 245, 255)
SNOW_SHADE = (195, 220, 250)
TREE = (35, 150, 70)
TREE_DARK = (20, 105, 52)
CABIN_WALL = (225, 120, 55)
CABIN_WALL_SHADE = (190, 92, 40)
ROOF = (110, 55, 25)
ROOF_HILITE = (250, 250, 255)
WINDOW = (255, 225, 120)
WINDOW_HOT = (255, 170, 50)
SMOKE = (170, 185, 210)

_rng = random.Random(11)
_SPARKLES = [(_rng.randint(0, W - 1), _rng.randint(18, H - 1)) for _ in range(20)]


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _draw_sky(draw):
    for y in range(0, 18):
        c = _lerp(SKY_TOP, SKY_BOT, y / 17)
        draw.line([(0, y), (W - 1, y)], fill=c)


def _draw_mountains(draw):
    # Back ridge
    ridge = [(0, 18), (8, 13), (15, 16), (24, 11), (34, 15), (43, 10), (52, 14), (63, 12), (63, 20), (0, 20)]
    draw.polygon(ridge, fill=MOUNTAIN_BACK)
    # Front ridge
    front = [(0, 21), (9, 17), (18, 20), (27, 16), (38, 19), (49, 15), (63, 18), (63, 24), (0, 24)]
    draw.polygon(front, fill=MOUNTAIN_FRONT)
    for x in range(0, W, 5):
        y = 20 + (x % 3)
        draw.point((x, y), fill=SNOW)


def _draw_tree(draw, tx, base_y, half):
    for row in range(4):
        y = base_y - row * 2
        spread = max(1, half - row)
        color = TREE if row % 2 == 0 else TREE_DARK
        draw.line([(tx - spread, y), (tx + spread, y)], fill=color)
    draw.line([(tx, base_y + 1), (tx, base_y + 2)], fill=ROOF)


def _draw_cabin(draw):
    # Body
    draw.rectangle([23, 19, 45, 28], fill=CABIN_WALL)
    draw.rectangle([35, 19, 45, 28], fill=CABIN_WALL_SHADE)

    # Roof with strong snow edge for readability.
    draw.polygon([(20, 19), (32, 10), (48, 19)], fill=ROOF)
    draw.line([(20, 19), (32, 10)], fill=ROOF_HILITE)
    draw.line([(21, 19), (33, 10)], fill=ROOF_HILITE)
    draw.line([(32, 10), (48, 19)], fill=(200, 220, 245))
    draw.line([(21, 20), (47, 20)], fill=(75, 35, 15))

    # Door and window
    draw.rectangle([37, 22, 41, 28], fill=ROOF)
    draw.rectangle([27, 21, 33, 25], fill=WINDOW)
    draw.rectangle([29, 22, 31, 24], fill=WINDOW_HOT)

    # Chimney
    draw.rectangle([39, 12, 41, 18], fill=ROOF)


def _draw_snow_ground(draw, frame):
    draw.rectangle([0, 24, W - 1, H - 1], fill=SNOW)
    for x in range(0, W, 4):
        bump = (x + frame) % 3
        draw.point((x, 23 - bump), fill=SNOW_SHADE)

    for sx, sy in _SPARKLES:
        if (sx + sy + frame) % 4 == 0:
            draw.point((sx, sy), fill=SNOW)


def _make_frame(frame):
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    _draw_sky(draw)
    draw.ellipse([5, 3, 15, 13], fill=SUN)
    draw.ellipse([7, 5, 13, 11], fill=SUN_GLOW)

    _draw_mountains(draw)
    _draw_tree(draw, 7, 24, 4)
    _draw_tree(draw, 15, 25, 3)
    _draw_tree(draw, 51, 24, 4)
    _draw_tree(draw, 58, 25, 3)
    _draw_cabin(draw)
    _draw_snow_ground(draw, frame)

    smoke_x = 40 + (frame % 2)
    for i in range(4):
        y = 11 - i - (frame % 2)
        if y >= 0:
            draw.point((smoke_x + (i % 2), y), fill=SMOKE)

    return img


FRAMES = [_make_frame(f) for f in range(4)]
