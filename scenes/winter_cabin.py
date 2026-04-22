import random
from PIL import Image, ImageDraw

NAME = "Winter Cabin"
FPS = 5

W, H = 64, 32

BLACK = (0, 0, 0)
SKY = (0, 0, 85)
STAR = (255, 255, 255)
STAR_DIM = (0, 0, 170)
SNOW = (170, 255, 255)
SNOW_BRIGHT = (255, 255, 255)
SNOW_DIM = (85, 170, 255)
TREE = (0, 170, 0)
TREE_DARK = (0, 85, 0)
CABIN = (255, 85, 0)
CABIN_DARK = (170, 0, 0)
ROOF = (85, 0, 0)
ROOF_SNOW = (255, 255, 255)
WINDOW = (255, 255, 85)
WINDOW_HOT = (255, 170, 0)
SMOKE = (170, 170, 255)

_rng = random.Random(33)
_FLAKES = [(_rng.randint(0, W - 1), _rng.randint(0, H - 9)) for _ in range(24)]
_STARS = [(x, y) for x in range(W) for y in range(10) if _rng.random() < 0.035]


def _draw_tree(draw, tx, base_y, half):
    for row in range(4):
        y = base_y - row * 3
        spread = max(1, half - row)
        color = TREE if row % 2 == 0 else TREE_DARK
        draw.line([(tx - spread, y), (tx + spread, y)], fill=color)
        draw.line([(tx - max(1, spread - 1), y - 1), (tx + max(1, spread - 1), y - 1)], fill=color)
    draw.line([(tx, base_y + 1), (tx, base_y + 3)], fill=CABIN_DARK)


def _draw_cabin(draw):
    # Cabin body.
    draw.rectangle([22, 18, 45, 26], fill=CABIN)
    draw.rectangle([36, 18, 45, 26], fill=CABIN_DARK)

    # Dark roof mass first, then bright snow slopes on top.
    roof_rows = [
        (32, 8, 32),
        (29, 10, 35),
        (26, 12, 38),
        (23, 14, 41),
        (20, 16, 46),
    ]
    for _, y, _ in roof_rows:
        draw.line([(20, y + 1), (46, y + 1)], fill=ROOF)
    for _, y, _ in roof_rows:
        left = 32 - (y - 8) * 2
        right = 32 + (y - 8) * 2
        left = max(19, left)
        right = min(47, right)
        draw.line([(left, y), (right, y)], fill=ROOF)
        draw.point((left, y), fill=ROOF_SNOW)
        draw.point((left + 1, y), fill=ROOF_SNOW)
        draw.point((right, y), fill=ROOF_SNOW)

    # Bright eave line and warm window make roof/body separation obvious.
    draw.line([(19, 17), (47, 17)], fill=ROOF_SNOW)
    draw.line([(20, 18), (46, 18)], fill=ROOF)
    draw.rectangle([27, 20, 33, 24], fill=WINDOW)
    draw.rectangle([29, 21, 31, 23], fill=WINDOW_HOT)
    draw.rectangle([38, 21, 42, 26], fill=ROOF)
    draw.rectangle([39, 9, 41, 16], fill=ROOF)


def _make_frame(frame):
    img = Image.new("RGB", (W, H), BLACK)
    draw = ImageDraw.Draw(img)
    rng = random.Random(frame * 11)

    for y in range(0, 12, 3):
        draw.line([(0, y), (W - 1, y)], fill=SKY)

    for sx, sy in _STARS:
        draw.point((sx, sy), fill=STAR if rng.random() < 0.75 else STAR_DIM)

    draw.rectangle([0, 26, W - 1, H - 1], fill=SNOW)
    for x in range(0, W, 4):
        draw.point((x, 25 - rng.randint(0, 2)), fill=SNOW_BRIGHT)

    for tree in [(3, 24, 4), (12, 25, 3), (51, 24, 5), (60, 25, 4)]:
        _draw_tree(draw, *tree)

    _draw_cabin(draw)

    for dx in range(8):
        draw.point((27 + dx, 27), fill=WINDOW_HOT)

    smoke_x = 40 + (frame % 2)
    for dy in range(5):
        sy = 8 - dy - (frame % 3)
        if 0 <= sy < H:
            draw.point((smoke_x + (dy % 2), sy), fill=SMOKE)

    for fx, fy in _FLAKES:
        y = (fy + frame * 2) % (H - 7)
        draw.point((fx, y), fill=SNOW_BRIGHT if rng.random() < 0.75 else SNOW_DIM)

    return img


FRAMES = [_make_frame(frame) for frame in range(4)]
