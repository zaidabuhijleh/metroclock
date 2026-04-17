import random
from PIL import Image, ImageDraw

NAME = "City Night"
FPS = 3

W, H = 64, 32

SKY        = (  2,   4,  15)
MOON       = (245, 240, 195)
MOON_GREY  = (190, 182, 140)
BUILDING_A = ( 28,  32,  60)
BUILDING_B = ( 22,  26,  50)
WIN_WARM   = (255, 215, 100)
WIN_DIM    = (200, 155,  60)
WIN_OFF    = ( 15,  18,  38)
STAR_BRIGHT= (230, 230, 255)
STAR_DIM   = (110, 110, 150)

_rng = random.Random(42)
_STARS = [(x, y) for x in range(W) for y in range(H - 18)
          if _rng.random() < 0.035]

# Buildings: (left_x, width, height)
_BUILDINGS = [
    ( 0,  6, 13), ( 6,  5,  9), (11,  7, 17), (18,  5, 11),
    (23,  8, 20), (31,  5,  8), (36,  6, 14), (42,  5, 10),
    (47,  7, 16), (54,  5, 12), (59,  5, 19),
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

    # Stars
    for sx, sy in _STARS:
        c = STAR_BRIGHT if rng.random() < 0.72 else STAR_DIM
        draw.point((sx, sy), fill=c)

    # Moon — crescent effect with offset dark circle
    draw.ellipse([45, 2, 54, 11], fill=MOON)
    draw.ellipse([48, 2, 55,  9], fill=MOON_GREY)

    # Buildings — clearly distinguishable from near-black sky
    for bx, bw, bh in _BUILDINGS:
        c = BUILDING_A if bx % 2 == 0 else BUILDING_B
        draw.rectangle([bx, H - bh, bx + bw - 1, H - 1], fill=c)

    # Windows — 2×1 rectangles for visibility
    for wx, wy in _ALL_WINDOWS:
        if (wx, wy) in _FLICKER:
            c = WIN_WARM if rng.random() < 0.55 else WIN_OFF
        else:
            c = WIN_WARM if rng.random() < 0.80 else WIN_DIM
        draw.rectangle([wx, wy, wx + 1, wy], fill=c)

    return img


FRAMES = [_make_frame(f) for f in range(4)]
