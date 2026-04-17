import random
from PIL import Image, ImageDraw

NAME = "City Night"
FPS = 3

W, H = 64, 32

# Visible dark blue sky so building silhouettes read against it
SKY        = ( 20,  28,  80)
MOON       = (248, 242, 200)
MOON_GREY  = (185, 178, 135)
# Buildings near-black — clear silhouette against blue sky
BUILDING_A = (  5,   6,  14)
BUILDING_B = (  7,   8,  18)
WIN_WARM   = (255, 215,  90)
WIN_DIM    = (195, 150,  55)
WIN_OFF    = (  3,   4,  10)
STAR_BRIGHT= (235, 235, 255)
STAR_DIM   = (105, 108, 148)

_rng = random.Random(42)
# Stars only in sky area (above tallest building — ~20 rows from top)
_STARS = [(x, y) for x in range(W) for y in range(H - 20)
          if _rng.random() < 0.04]

# Buildings: (left_x, width, height) — heights varied so skyline reads
_BUILDINGS = [
    ( 0,  6, 12), ( 6,  5,  8), (11,  7, 16), (18,  5, 10),
    (23,  8, 19), (31,  5,  7), (36,  6, 13), (42,  5,  9),
    (47,  7, 15), (54,  5, 11), (59,  5, 18),
]

_rng2 = random.Random(7)

def _gen_windows(bx, bw, bh):
    wins = []
    for row in range(2, bh - 1, 4):
        for col in range(1, bw - 1, 3):
            if _rng2.random() < 0.65:
                wins.append((bx + col, H - bh + row))
    return wins

_ALL_WINDOWS = []
for bx, bw, bh in _BUILDINGS:
    _ALL_WINDOWS.extend(_gen_windows(bx, bw, bh))

_rng3 = random.Random(99)
_FLICKER = {w for w in _ALL_WINDOWS if _rng3.random() < 0.18}


def _make_frame(frame):
    img = Image.new("RGB", (W, H), SKY)
    draw = ImageDraw.Draw(img)
    rng = random.Random(frame * 17)

    # Stars in sky region
    for sx, sy in _STARS:
        c = STAR_BRIGHT if rng.random() < 0.75 else STAR_DIM
        draw.point((sx, sy), fill=c)

    # Moon
    draw.ellipse([45, 2, 54, 11], fill=MOON)
    draw.ellipse([48, 2, 55,  9], fill=MOON_GREY)

    # Buildings as dark silhouettes against the visible blue sky
    for bx, bw, bh in _BUILDINGS:
        c = BUILDING_A if bx % 2 == 0 else BUILDING_B
        draw.rectangle([bx, H - bh, bx + bw - 1, H - 1], fill=c)

    # Windows — 2×1 for visibility
    for wx, wy in _ALL_WINDOWS:
        if (wx, wy) in _FLICKER:
            c = WIN_WARM if rng.random() < 0.55 else WIN_OFF
        else:
            c = WIN_WARM if rng.random() < 0.82 else WIN_DIM
        draw.rectangle([wx, wy, wx + 1, wy], fill=c)

    return img


FRAMES = [_make_frame(f) for f in range(4)]
