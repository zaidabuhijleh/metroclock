import random
from PIL import Image, ImageDraw

NAME = "City Night"
FPS = 3

W, H = 64, 32

BLACK = (0, 0, 0)
SKY_BLUE = (0, 0, 85)
BUILDING_FILL = (0, 0, 85)
BUILDING_EDGE = (0, 170, 255)
BUILDING_TOP = (170, 255, 255)
WIN_WARM = (255, 170, 0)
WIN_BRIGHT = (255, 255, 85)
WIN_OFF = (0, 0, 0)
MOON = (255, 255, 170)
STAR = (255, 255, 255)
STAR_DIM = (0, 0, 170)

_BUILDINGS = [
    (0, 7, 11), (7, 6, 15), (13, 8, 9), (21, 7, 18),
    (28, 8, 13), (36, 7, 16), (43, 6, 10), (49, 8, 14), (57, 7, 19),
]

_rng = random.Random(42)
_STARS = [(x, y) for x in range(W) for y in range(10) if _rng.random() < 0.025]

_rng2 = random.Random(7)


def _windows_for_building(bx, bw, bh):
    top = H - bh
    windows = []
    for y in range(top + 3, H - 3, 4):
        for x in range(bx + 2, bx + bw - 2, 3):
            if _rng2.random() < 0.72:
                windows.append((x, y))
    return windows


_WINDOWS = []
for building in _BUILDINGS:
    _WINDOWS.extend(_windows_for_building(*building))

_rng3 = random.Random(99)
_FLICKER = {window for window in _WINDOWS if _rng3.random() < 0.22}


def _draw_building(draw, bx, bw, bh):
    top = H - bh
    draw.rectangle([bx, top, bx + bw - 1, H - 1], fill=BUILDING_FILL)
    draw.line([(bx, top), (bx + bw - 1, top)], fill=BUILDING_TOP)
    draw.line([(bx, top), (bx, H - 1)], fill=BUILDING_EDGE)
    draw.line([(bx + bw - 1, top), (bx + bw - 1, H - 1)], fill=BUILDING_EDGE)

    # A few antenna/spire details make the blocks read as buildings.
    if bh >= 15:
        mid = bx + bw // 2
        draw.line([(mid, max(0, top - 3)), (mid, top - 1)], fill=BUILDING_TOP)
        draw.point((mid, max(0, top - 4)), fill=STAR)


def _make_frame(frame):
    img = Image.new("RGB", (W, H), BLACK)
    draw = ImageDraw.Draw(img)
    rng = random.Random(frame * 17)

    # Sparse sky pixels are safer than a dim full-screen fill on this panel.
    for y in range(0, 12, 3):
        draw.line([(0, y), (W - 1, y)], fill=SKY_BLUE)

    for sx, sy in _STARS:
        draw.point((sx, sy), fill=STAR if rng.random() < 0.7 else STAR_DIM)

    draw.ellipse([47, 2, 55, 10], fill=MOON)
    draw.ellipse([50, 2, 56, 8], fill=BLACK)

    for building in _BUILDINGS:
        _draw_building(draw, *building)

    for wx, wy in _WINDOWS:
        if (wx, wy) in _FLICKER and rng.random() < 0.45:
            color = WIN_OFF
        else:
            color = WIN_BRIGHT if rng.random() < 0.45 else WIN_WARM
        draw.rectangle([wx, wy, wx + 1, wy], fill=color)

    draw.line([(0, H - 1), (W - 1, H - 1)], fill=BUILDING_EDGE)
    return img


FRAMES = [_make_frame(frame) for frame in range(4)]
