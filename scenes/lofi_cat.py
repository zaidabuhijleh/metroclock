import math
from PIL import Image, ImageDraw

NAME = "Lofi Cat"
COLLECTION = "Cozy"
FPS = 6

W, H = 64, 32
N = 8

WALL_TOP = (25, 20, 55)
WALL_BOT = (68, 44, 70)
FLOOR = (88, 58, 38)
FLOOR_DARK = (62, 38, 22)
SHELF_WOOD = (108, 70, 42)
SHELF_EDGE = (142, 96, 60)
CASE_SHADE = (86, 55, 34)
WIN_FRAME = (155, 140, 122)
WIN_SKY = (0, 0, 0)
WIN_SKY_B = (0, 0, 0)
MOON = (228, 218, 172)
FP_STONE = (115, 105, 95)
FP_STONE_D = (88, 78, 70)
FP_MANTLE = (132, 108, 80)
FP_MANTLE_T = (165, 138, 105)
FP_CHIMNEY = (126, 98, 74)
FP_OPEN = (28, 20, 16)
FIRE_1 = (255, 225, 80)
FIRE_2 = (255, 145, 30)
FIRE_3 = (200, 55, 18)
EMBER = (90, 30, 10)
GLOW_FIRE = (255, 140, 40)
CAT_FUR = (170, 150, 126)
CAT_DARK = (116, 96, 74)
CAT_SHADOW = (136, 116, 94)
CAT_BELLY = (202, 182, 158)
CAT_FACE = (188, 168, 144)
CAT_NOSE = (238, 142, 142)
EYE_C = (72, 158, 112)
NOTE_C = (255, 200, 105)

FP_X1, FP_X2 = 20, 38
FP_Y1, FP_Y2 = 8, 21
FP_IN_X1, FP_IN_X2 = 22, 36
FP_IN_Y1, FP_IN_Y2 = 11, 21


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _draw_wall(draw, frame):
    gx = (FP_X1 + FP_X2) // 2
    gy = 18
    phase = 2.0 * math.pi * frame / N
    flicker = 0.10 * math.sin(phase)
    for y in range(22):
        for x in range(W):
            base = _lerp(WALL_TOP, WALL_BOT, y / 21)
            dist = ((x - gx) ** 2 + (y - gy) ** 2) ** 0.5
            if dist < 24:
                t = max(0.0, (1 - dist / 24) ** 1.8) * (0.45 + flicker)
                base = _lerp(base, GLOW_FIRE, t)
            draw.point((x, y), fill=base)


def _draw_bookcase(draw):
    draw.rectangle([0, 4, 15, 22], fill=CASE_SHADE)
    draw.rectangle([1, 5, 14, 21], fill=SHELF_WOOD)
    for y in [8, 13, 17, 21]:
        draw.line([(1, y), (14, y)], fill=SHELF_EDGE)

    rows = [
        (8, 3, [
            (1, 3, (188, 74, 68)), (2, 2, (88, 134, 194)), (1, 3, (196, 170, 82)),
            (2, 2, (82, 156, 96)), (1, 3, (170, 110, 194)), (2, 2, (212, 138, 84)),
            (1, 3, (90, 162, 172)), (2, 2, (204, 96, 142)), (1, 3, (104, 178, 214)),
            (1, 2, (156, 130, 90)),
        ]),
        (13, 4, [
            (2, 4, (214, 98, 84)), (1, 3, (102, 150, 206)), (2, 2, (180, 152, 72)),
            (1, 4, (96, 166, 108)), (2, 3, (196, 122, 202)), (1, 2, (224, 156, 94)),
            (2, 4, (84, 146, 188)), (1, 3, (214, 122, 72)), (2, 2, (126, 170, 108)),
        ]),
        (17, 3, [
            (1, 2, (96, 146, 198)), (1, 3, (206, 152, 74)), (2, 2, (86, 160, 108)),
            (1, 3, (188, 108, 196)), (2, 2, (220, 146, 88)), (1, 3, (92, 164, 176)),
            (2, 2, (198, 98, 136)), (1, 3, (108, 178, 214)), (1, 2, (176, 134, 96)),
            (2, 3, (120, 158, 90)),
        ]),
    ]
    for top, max_h, books in rows:
        x = 1
        for width, height, color in books:
            height = min(max_h, max(1, height))
            y1 = top - height
            draw.rectangle([x, y1, x + width - 1, top - 1], fill=color)
            draw.point((x, y1), fill=_lerp(color, (255, 255, 255), 0.2))
            x += width


def _draw_window(draw, frame):
    wx1, wy1, wx2, wy2 = 42, 2, 63, 18
    draw.rectangle([wx1, wy1, wx2, wy2], fill=WIN_FRAME)
    for y in range(wy1 + 1, wy2):
        t = (y - wy1 - 1) / (wy2 - wy1 - 2)
        draw.line([(wx1 + 1, y), (wx2 - 1, y)], fill=_lerp(WIN_SKY, WIN_SKY_B, t))
    draw.ellipse([55, 4, 61, 10], fill=MOON)
    draw.line([(52, wy1 + 1), (52, wy2 - 1)], fill=(125, 112, 98))
    draw.line([(wx1 + 1, 11), (wx2 - 1, 11)], fill=(125, 112, 98))
    stars = [(44, 5), (48, 7), (50, 4), (45, 13), (58, 14), (47, 16), (62, 6)]
    for i, (sx, sy) in enumerate(stars):
        color = (200, 210, 240) if (frame + i) % 2 == 0 else (130, 148, 190)
        draw.point((sx, sy), fill=color)


def _draw_fireplace(draw, frame):
    for y in range(FP_Y1, FP_Y2 + 1):
        for x in range(FP_X1, FP_X2 + 1):
            if FP_IN_X1 <= x <= FP_IN_X2 and y >= FP_IN_Y1:
                continue
            brick_row = (y - FP_Y1) // 2
            brick_col = (x - FP_X1 + (brick_row % 2) * 3) // 4
            draw.point((x, y), fill=FP_STONE if brick_col % 2 == 0 else FP_STONE_D)

    draw.rectangle([FP_X1 - 1, FP_Y1 - 1, FP_X2 + 1, FP_Y1 + 1], fill=FP_MANTLE)
    draw.line([(FP_X1 - 1, FP_Y1 - 1), (FP_X2 + 1, FP_Y1 - 1)], fill=FP_MANTLE_T)
    draw.rectangle([27, 0, 31, FP_Y1 - 2], fill=FP_CHIMNEY)
    draw.line([(27, 0), (31, 0)], fill=FP_MANTLE_T)
    draw.rectangle([22, FP_Y1 - 3, 23, FP_Y1 - 2], fill=(185, 160, 110))
    draw.point((22, FP_Y1 - 4), fill=(255, 205, 120))
    draw.rectangle([29, FP_Y1 - 3, 30, FP_Y1 - 2], fill=(145, 95, 70))
    draw.point((30, FP_Y1 - 3), fill=(210, 185, 145))
    draw.rectangle([34, FP_Y1 - 3, 35, FP_Y1 - 2], fill=(78, 132, 185))
    draw.rectangle([FP_IN_X1, FP_IN_Y1, FP_IN_X2, FP_IN_Y2], fill=FP_OPEN)

    phase = 2.0 * math.pi * frame / N
    for offset in range(14):
        x = FP_IN_X1 + 1 + offset
        if x > FP_IN_X2 - 1:
            break
        height = 2 + int(2 + 1.6 * math.sin(phase + offset * 0.62))
        for dy in range(height):
            y = FP_IN_Y2 - dy
            if FP_IN_Y1 < y <= FP_IN_Y2:
                t = dy / max(1, height - 1)
                base = FIRE_3 if dy < 2 else FIRE_2
                draw.point((x, y), fill=_lerp(base, FIRE_1, t))
        draw.point((x, FP_IN_Y2), fill=EMBER)


def _draw_floor(draw):
    draw.rectangle([0, 22, W - 1, H - 1], fill=FLOOR)
    for y in range(24, H, 5):
        draw.line([(0, y), (W - 1, y)], fill=FLOOR_DARK)
    for x in range(0, W, 14):
        draw.line([(x, 22), (x, H - 1)], fill=FLOOR_DARK)
    draw.line([(0, 22), (W - 1, 22)], fill=FLOOR_DARK)


def _draw_cat(draw, frame):
    draw.ellipse([26, 24, 47, 30], fill=CAT_FUR)
    draw.ellipse([30, 25, 43, 29], fill=CAT_BELLY)
    draw.ellipse([27, 28, 33, 31], fill=CAT_SHADOW)
    draw.ellipse([33, 28, 39, 31], fill=CAT_FUR)
    draw.ellipse([42, 20, 53, 27], fill=CAT_FACE)
    draw.polygon([(44, 21), (44, 19), (46, 21)], fill=CAT_FUR)
    draw.polygon([(49, 21), (51, 19), (51, 21)], fill=CAT_FUR)

    if frame in (4, 5):
        draw.line([(46, 23), (47, 23)], fill=CAT_DARK)
        draw.line([(49, 23), (50, 23)], fill=CAT_DARK)
    else:
        draw.point((46, 23), fill=EYE_C)
        draw.point((49, 23), fill=EYE_C)
        draw.point((47, 23), fill=(45, 38, 34))
        draw.point((50, 23), fill=(45, 38, 34))

    draw.point((48, 24), fill=CAT_NOSE)
    whisker = (210, 198, 175)
    draw.line([(43, 24), (46, 24)], fill=whisker)
    draw.line([(43, 25), (46, 25)], fill=whisker)
    draw.line([(50, 24), (53, 24)], fill=whisker)
    draw.line([(50, 25), (53, 25)], fill=whisker)
    draw.ellipse([40, 28, 46, 31], fill=CAT_FUR)
    draw.ellipse([45, 28, 51, 31], fill=CAT_SHADOW)

    tails = [
        [(27, 27), (23, 26), (21, 23), (21, 20)],
        [(27, 27), (23, 26), (22, 24), (21, 21)],
        [(27, 27), (24, 27), (22, 25), (22, 22)],
        [(27, 27), (24, 27), (23, 25), (22, 23)],
        [(27, 27), (23, 26), (21, 23), (21, 20)],
        [(27, 27), (22, 25), (21, 22), (21, 19)],
        [(27, 27), (23, 26), (22, 24), (21, 21)],
        [(27, 27), (24, 27), (22, 25), (22, 22)],
    ]
    points = tails[frame % N]
    draw.line(points, fill=CAT_FUR)
    draw.line([(x, y + 1) for x, y in points if y + 1 < H], fill=CAT_SHADOW)


def _draw_notes(draw, frame):
    for i, (x, base_y) in enumerate([(32, 16), (36, 14)]):
        y = base_y - (frame + i * 3) % 7
        if 5 <= y <= 20:
            t = ((frame + i * 3) % 7) / 6
            color = _lerp(NOTE_C, WALL_TOP, t * 0.7)
            draw.point((x, y), fill=color)
            draw.point((x + 1, y), fill=color)
            draw.point((x + 1, y - 1), fill=color)


def _make_frame(frame):
    image = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(image)
    _draw_wall(draw, frame)
    _draw_bookcase(draw)
    _draw_fireplace(draw, frame)
    _draw_window(draw, frame)
    _draw_floor(draw)
    _draw_cat(draw, frame)
    _draw_notes(draw, frame)
    return image


FRAMES = [_make_frame(frame) for frame in range(N)]
