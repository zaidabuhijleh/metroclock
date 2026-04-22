import random
from PIL import Image, ImageDraw

NAME = "City Night"
FPS = 3

W, H = 64, 32

SKY_TOP      = (12, 16, 46)
SKY_BOTTOM   = (30, 16, 34)
MOON         = (248, 242, 200)
MOON_SHADOW  = (185, 178, 135)
BUILDING_A   = (14, 16, 28)
BUILDING_B   = (20, 22, 36)
BUILDING_EDGE = (42, 46, 76)
WIN_WARM     = (255, 215, 90)
WIN_DIM      = (195, 150, 55)
WIN_OFF      = (16, 18, 28)
STAR_BRIGHT  = (235, 235, 255)
STAR_DIM     = (105, 108, 148)
GROUND       = (8, 8, 16)

_rng = random.Random(42)
_STARS = [(x, y) for x in range(W) for y in range(12) if _rng.random() < 0.035]

_BUILDINGS = [
    (0, 8, 11), (8, 6, 8), (14, 8, 15), (22, 6, 10),
    (28, 9, 20), (37, 7, 9), (44, 7, 13), (51, 6, 11), (57, 7, 17),
]

_rng2 = random.Random(7)


def _gen_windows(bx, bw, bh):
    windows = []
    top = H - bh
    for row in range(top + 2, H - 2, 4):
        for col in range(bx + 1, bx + bw - 2, 3):
            if _rng2.random() < 0.72:
                windows.append((col, row))
    return windows


_ALL_WINDOWS = []
for bx, bw, bh in _BUILDINGS:
    _ALL_WINDOWS.extend(_gen_windows(bx, bw, bh))

_rng3 = random.Random(99)
_FLICKER = {window for window in _ALL_WINDOWS if _rng3.random() < 0.2}


def _draw_sky(draw):
    for y in range(H):
        t = y / max(1, H - 1)
        color = (
            int(SKY_TOP[0] * (1 - t) + SKY_BOTTOM[0] * t),
            int(SKY_TOP[1] * (1 - t) + SKY_BOTTOM[1] * t),
            int(SKY_TOP[2] * (1 - t) + SKY_BOTTOM[2] * t),
        )
        draw.line([(0, y), (W - 1, y)], fill=color)


def _make_frame(frame):
    img = Image.new("RGB", (W, H), SKY_TOP)
    draw = ImageDraw.Draw(img)
    rng = random.Random(frame * 17)

    _draw_sky(draw)

    for sx, sy in _STARS:
        draw.point((sx, sy), fill=STAR_BRIGHT if rng.random() < 0.75 else STAR_DIM)

    draw.ellipse([46, 2, 55, 11], fill=MOON)
    draw.ellipse([49, 2, 56, 9], fill=MOON_SHADOW)

    for bx, bw, bh in _BUILDINGS:
        color = BUILDING_A if (bx // 2) % 2 == 0 else BUILDING_B
        top = H - bh
        draw.rectangle([bx, top, bx + bw - 1, H - 1], fill=color)
        draw.line([(bx, top), (bx + bw - 1, top)], fill=BUILDING_EDGE)
        if bw >= 7:
            draw.line([(bx + bw - 1, top), (bx + bw - 1, H - 1)], fill=BUILDING_EDGE)

    for wx, wy in _ALL_WINDOWS:
        if (wx, wy) in _FLICKER:
            color = WIN_WARM if rng.random() < 0.5 else WIN_OFF
        else:
            color = WIN_WARM if rng.random() < 0.84 else WIN_DIM
        draw.rectangle([wx, wy, wx + 1, wy], fill=color)

    draw.rectangle([0, H - 2, W - 1, H - 1], fill=GROUND)
    return img


FRAMES = [_make_frame(frame) for frame in range(4)]
