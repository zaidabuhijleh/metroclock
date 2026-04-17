import random
from PIL import Image, ImageDraw

NAME = "City Night"
FPS = 3

W, H = 64, 32

SKY        = (5,   8,  20)
MOON       = (240, 235, 190)
MOON_GREY  = (180, 175, 130)
BUILDING   = (15,  18,  35)
BUILDING2  = (20,  24,  45)
WIN_WARM   = (255, 210, 100)
WIN_DIM    = (180, 140,  60)
WIN_OFF    = (25,  30,  55)
STAR_BRIGHT= (220, 220, 255)
STAR_DIM   = (100, 100, 140)

_rng = random.Random(42)

# Star field — fixed positions, brightness varies per frame
_STARS = [(x, y) for x in range(W) for y in range(H - 16)
          if _rng.random() < 0.025]

# Buildings: (left_x, width, height)
_BUILDINGS = [
    (0,  7, 14), (7,  5, 10), (12, 8, 18), (20, 6, 12),
    (26, 9, 20), (35, 5,  9), (40, 7, 15), (47, 6, 11),
    (53, 5, 17), (58, 6, 13),
]

# Windows per building: offsets relative to building top-left (col, row)
_rng2 = random.Random(7)

def _gen_windows(bx, bw, bh):
    wins = []
    for row in range(1, bh - 1, 3):
        for col in range(1, bw - 1, 3):
            if _rng2.random() < 0.6:
                wins.append((bx + col, H - bh + row))
    return wins

_ALL_WINDOWS = []
for bx, bw, bh in _BUILDINGS:
    _ALL_WINDOWS.extend(_gen_windows(bx, bw, bh))

_rng3 = random.Random(99)
_FLICKER_SET = {w for w in _ALL_WINDOWS if _rng3.random() < 0.15}


def _make_frame(frame):
    img = Image.new("RGB", (W, H), SKY)
    draw = ImageDraw.Draw(img)

    rng = random.Random(frame * 13)

    # Stars
    for sx, sy in _STARS:
        c = STAR_BRIGHT if rng.random() < 0.7 else STAR_DIM
        draw.point((sx, sy), fill=c)

    # Moon
    draw.ellipse([48, 2, 56, 10], fill=MOON)
    draw.ellipse([51, 2, 57,  8], fill=MOON_GREY)   # crater suggestion

    # Buildings
    for bx, bw, bh in _BUILDINGS:
        c = BUILDING if bx % 2 == 0 else BUILDING2
        draw.rectangle([bx, H - bh, bx + bw - 1, H - 1], fill=c)

    # Windows
    for wx, wy in _ALL_WINDOWS:
        if (wx, wy) in _FLICKER_SET:
            c = WIN_WARM if rng.random() < 0.55 else WIN_OFF
        else:
            c = WIN_WARM if rng.random() < 0.85 else WIN_DIM
        draw.point((wx, wy), fill=c)

    return img


FRAMES = [_make_frame(f) for f in range(4)]
