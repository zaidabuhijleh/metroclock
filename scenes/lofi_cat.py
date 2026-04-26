import math
from PIL import Image, ImageDraw

NAME = "Lofi Cat"
FPS = 6

W, H = 64, 32
N = 8

# Wall and floor
WALL_TOP = (25, 20, 55)
WALL_BOT = (68, 44, 70)
FLOOR = (88, 58, 38)
FLOOR_DARK = (62, 38, 22)

# Bookcase
SHELF_WOOD = (108, 70, 42)
SHELF_EDGE = (142, 96, 60)
CASE_SHADE = (86, 55, 34)

# Window
WIN_FRAME = (155, 140, 122)
WIN_SKY = (16, 20, 50)
WIN_SKY_B = (26, 32, 68)
MOON = (228, 218, 172)

# Fireplace
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

# Cat (panel-tuned: reduced bloom, stronger contrast)
CAT_FUR = (170, 150, 126)
CAT_DARK = (116, 96, 74)
CAT_SHADOW = (136, 116, 94)
CAT_BELLY = (202, 182, 158)
CAT_FACE = (188, 168, 144)
CAT_NOSE = (238, 142, 142)
EYE_C = (72, 158, 112)
CAT_OUTLINE = (86, 70, 56)

# Floating notes
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
    # full-height case on left
    draw.rectangle([0, 4, 15, 22], fill=CASE_SHADE)
    draw.rectangle([1, 5, 14, 21], fill=SHELF_WOOD)
    for y in [8, 13, 17, 21]:
        draw.line([(1, y), (14, y)], fill=SHELF_EDGE)

    shelves = [
        # (x, width, height, color)
        [(1, 1, 3, (180, 72, 64)), (3, 1, 4, (90, 130, 190)), (5, 2, 5, (190, 165, 78)), (8, 2, 3, (78, 152, 95)), (11, 1, 4, (170, 106, 190)), (13, 1, 2, (210, 135, 82))],
        [(1, 2, 4, (205, 92, 78)), (4, 1, 5, (92, 122, 195)), (6, 1, 3, (200, 170, 70)), (8, 2, 4, (72, 148, 88)), (11, 1, 5, (174, 108, 186)), (13, 1, 3, (212, 150, 88))],
        [(1, 1, 3, (166, 85, 60)), (3, 2, 2, (88, 136, 175)), (6, 1, 4, (200, 162, 78)), (8, 1, 3, (88, 140, 90)), (10, 2, 5, (130, 90, 168)), (13, 1, 4, (195, 126, 88))],
    ]
    shelf_tops = [8, 13, 17]
    for idx, books in enumerate(shelves):
        top = shelf_tops[idx]
        for bx, bw, bh, color in books:
            y1 = top - bh
            draw.rectangle([bx, y1, bx + bw - 1, top - 1], fill=color)
            draw.point((bx, y1), fill=_lerp(color, (255, 255, 255), 0.2))


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
        c = (200, 210, 240) if (frame + i) % 2 == 0 else (130, 148, 190)
        draw.point((sx, sy), fill=c)


def _draw_fireplace(draw, frame):
    for y in range(FP_Y1, FP_Y2 + 1):
        for x in range(FP_X1, FP_X2 + 1):
            if FP_IN_X1 <= x <= FP_IN_X2 and y >= FP_IN_Y1:
                continue
            brick_row = (y - FP_Y1) // 2
            brick_col = (x - FP_X1 + (brick_row % 2) * 3) // 4
            c = FP_STONE if brick_col % 2 == 0 else FP_STONE_D
            draw.point((x, y), fill=c)

    draw.rectangle([FP_X1 - 1, FP_Y1 - 1, FP_X2 + 1, FP_Y1 + 1], fill=FP_MANTLE)
    draw.line([(FP_X1 - 1, FP_Y1 - 1), (FP_X2 + 1, FP_Y1 - 1)], fill=FP_MANTLE_T)
    draw.rectangle([27, 0, 31, FP_Y1 - 2], fill=FP_CHIMNEY)
    draw.line([(27, 0), (31, 0)], fill=FP_MANTLE_T)

    # mantle knick-knacks
    draw.rectangle([22, FP_Y1 - 3, 23, FP_Y1 - 2], fill=(185, 160, 110))
    draw.point((22, FP_Y1 - 4), fill=(255, 205, 120))
    draw.rectangle([29, FP_Y1 - 3, 30, FP_Y1 - 2], fill=(145, 95, 70))
    draw.point((30, FP_Y1 - 3), fill=(210, 185, 145))
    draw.rectangle([34, FP_Y1 - 3, 35, FP_Y1 - 2], fill=(78, 132, 185))

    draw.rectangle([FP_IN_X1, FP_IN_Y1, FP_IN_X2, FP_IN_Y2], fill=FP_OPEN)

    phase = 2.0 * math.pi * frame / N
    for ox in range(0, 14):
        fx = FP_IN_X1 + 1 + ox
        if fx > FP_IN_X2 - 1:
            break
        h = 2 + int(2 + 1.6 * math.sin(phase + ox * 0.62))
        for dy in range(h):
            fy = FP_IN_Y2 - dy
            if FP_IN_Y1 < fy <= FP_IN_Y2:
                t = dy / max(1, h - 1)
                base = FIRE_3 if dy < 2 else FIRE_2
                flame = _lerp(base, FIRE_1, t)
                draw.point((fx, fy), fill=flame)
        draw.point((fx, FP_IN_Y2), fill=EMBER)


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
    # Softer ears
    draw.polygon([(44, 21), (44, 19), (46, 21)], fill=CAT_FUR)
    draw.polygon([(49, 21), (51, 19), (51, 21)], fill=CAT_FUR)

    blink = frame in (4, 5)
    if blink:
        draw.line([(46, 23), (47, 23)], fill=CAT_DARK)
        draw.line([(49, 23), (50, 23)], fill=CAT_DARK)
    else:
        draw.point((46, 23), fill=EYE_C)
        draw.point((49, 23), fill=EYE_C)
        draw.point((47, 23), fill=(45, 38, 34))
        draw.point((50, 23), fill=(45, 38, 34))

    draw.point((48, 24), fill=CAT_NOSE)
    whisk = (210, 198, 175)
    draw.line([(43, 24), (46, 24)], fill=whisk)
    draw.line([(43, 25), (46, 25)], fill=whisk)
    draw.line([(50, 24), (53, 24)], fill=whisk)
    draw.line([(50, 25), (53, 25)], fill=whisk)

    draw.ellipse([40, 28, 46, 31], fill=CAT_FUR)
    draw.ellipse([45, 28, 51, 31], fill=CAT_SHADOW)

    # thicker tail
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
    pts = tails[frame % N]
    draw.line(pts, fill=CAT_FUR, width=1)
    draw.line([(x, y + 1) for (x, y) in pts if y + 1 < H], fill=CAT_SHADOW, width=1)

    # Explicit outline so the silhouette survives panel bloom.
    for p in [
        (26, 27), (27, 25), (30, 24), (34, 24), (39, 24), (43, 24), (46, 25), (47, 27),
        (52, 24), (51, 20), (46, 20), (42, 22), (41, 26), (51, 29), (46, 30), (39, 30),
        (31, 30), (27, 29), (22, 23), (21, 20)
    ]:
        x, y = p
        if 0 <= x < W and 0 <= y < H:
            draw.point((x, y), fill=CAT_OUTLINE)


def _draw_notes(draw, frame):
    for i, (nx, base_y) in enumerate([(32, 16), (36, 14)]):
        ny = base_y - (frame + i * 3) % 7
        if 5 <= ny <= 20:
            t = ((frame + i * 3) % 7) / 6
            c = _lerp(NOTE_C, WALL_TOP, t * 0.7)
            draw.point((nx, ny), fill=c)
            draw.point((nx + 1, ny), fill=c)
            draw.point((nx + 1, ny - 1), fill=c)


def _make_frame(frame):
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    _draw_wall(draw, frame)
    _draw_bookcase(draw)
    _draw_fireplace(draw, frame)
    _draw_window(draw, frame)
    _draw_floor(draw)
    _draw_cat(draw, frame)
    _draw_notes(draw, frame)
    return img


FRAMES = [_make_frame(f) for f in range(N)]
