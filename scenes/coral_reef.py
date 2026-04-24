import math
from PIL import Image, ImageDraw

NAME = "Coral Reef"
FPS = 6

W, H = 64, 32
N = 8

WATER_TOP = (70, 190, 255)
WATER_MID = (35, 145, 230)
WATER_BOT = (15, 95, 185)
SAND = (230, 200, 120)
SAND_SHADE = (200, 165, 95)
CORAL_A = (255, 125, 120)
CORAL_B = (255, 180, 85)
CORAL_C = (190, 115, 255)
CORAL_D = (255, 95, 165)
CORAL_E = (255, 145, 210)
SEAWEED = (55, 200, 95)
SEAWEED_DARK = (25, 145, 70)
BUBBLE = (220, 250, 255)
FISH_Y = (255, 240, 100)
FISH_O = (255, 165, 70)
FISH_P = (255, 130, 210)
FISH_B = (120, 225, 255)


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _draw_water(draw):
    for y in range(0, 24):
        if y < 9:
            c = _lerp(WATER_TOP, WATER_MID, y / 8)
        else:
            c = _lerp(WATER_MID, WATER_BOT, (y - 9) / 14)
        draw.line([(0, y), (W - 1, y)], fill=c)


def _draw_coral_fan(draw, x, y, color):
    points = [(x, y), (x + 2, y - 6), (x + 5, y - 9), (x + 7, y - 6), (x + 8, y)]
    draw.polygon(points, fill=color)
    for dy in range(1, 8, 2):
        vein = (255, 220, 210)
        draw.line([(x + 4, y - dy), (x + 2 + (dy // 2), y - dy - 1)], fill=vein)
        draw.line([(x + 4, y - dy), (x + 6 - (dy // 2), y - dy - 1)], fill=vein)


def _draw_coral_branch(draw, x, y, color):
    draw.line([(x, y), (x, y - 6)], fill=color)
    draw.line([(x + 1, y), (x + 1, y - 5)], fill=color)
    draw.line([(x, y - 4), (x - 3, y - 7)], fill=color)
    draw.line([(x + 1, y - 3), (x + 4, y - 6)], fill=color)
    draw.line([(x, y - 6), (x - 2, y - 9)], fill=color)
    draw.line([(x + 1, y - 5), (x + 3, y - 8)], fill=color)


def _draw_coral_brain(draw, x, y, color):
    draw.ellipse([x, y - 6, x + 8, y], fill=color)
    line = (255, 205, 130)
    draw.arc([x + 1, y - 6, x + 7, y - 1], 0, 180, fill=line)
    draw.arc([x + 1, y - 5, x + 7, y], 180, 360, fill=line)
    draw.arc([x + 2, y - 6, x + 6, y], 90, 270, fill=line)


def _draw_tube_coral(draw, x, y):
    for i in range(3):
        tx = x + i * 2
        h = 4 + (i % 2)
        draw.rectangle([tx, y - h, tx + 1, y], fill=CORAL_E)
        draw.point((tx, y - h), fill=(255, 220, 235))


def _draw_floor(draw, frame):
    draw.rectangle([0, 24, W - 1, H - 1], fill=SAND)
    for x in range(0, W, 4):
        draw.point((x, 24 + (x % 2)), fill=SAND_SHADE)
        if (x + frame) % 8 == 0:
            draw.point((x + 1, 26), fill=SAND_SHADE)

    # coral clusters with clearer spacing
    _draw_coral_fan(draw, 2, 27, CORAL_A)
    _draw_coral_branch(draw, 14, 29, CORAL_B)
    _draw_coral_brain(draw, 23, 28, CORAL_C)
    _draw_tube_coral(draw, 34, 29)
    _draw_coral_branch(draw, 44, 29, CORAL_D)
    _draw_coral_fan(draw, 53, 28, CORAL_B)

    sparkle_pts = [(7, 21), (18, 20), (27, 22), (37, 22), (47, 21), (58, 22)]
    for i, (sx, sy) in enumerate(sparkle_pts):
        if (frame + i) % 2 == 0:
            draw.point((sx, sy), fill=(255, 235, 180))


def _draw_seaweed(draw, frame):
    phase = 2.0 * math.pi * frame / N
    # anchored away from the coral centers so overlap looks intentional.
    for idx, sx in enumerate([9, 19, 39, 58]):
        sway = int(round(1.6 * math.sin(phase + idx * 0.9)))
        draw.line([(sx, 24), (sx + sway, 16)], fill=SEAWEED)
        draw.line([(sx + 1, 24), (sx + 1 + sway, 17)], fill=SEAWEED_DARK)


def _draw_fish_shape(draw, x, y, color, size, facing=1):
    if size == 1:
        pts = [(x, y), (x + facing, y), (x - facing, y - 1), (x - facing, y + 1)]
    elif size == 2:
        pts = [
            (x, y), (x + facing, y), (x + 2 * facing, y),
            (x - facing, y - 1), (x - facing, y + 1),
            (x - 2 * facing, y),
        ]
    else:
        pts = [
            (x, y), (x + facing, y), (x + 2 * facing, y), (x + 3 * facing, y),
            (x - facing, y - 1), (x - facing, y + 1),
            (x - 2 * facing, y - 1), (x - 2 * facing, y + 1),
        ]
    for px, py in pts:
        if 0 <= px < W and 0 <= py < H:
            draw.point((px, py), fill=color)


def _draw_fish(draw, frame):
    phase = 2.0 * math.pi * frame / N

    specs = [
        (10 + int(8 * math.sin(phase + 0.1)), 8 + int(1 * math.cos(phase + 0.3)), FISH_Y, 2, 1),
        (29 + int(10 * math.sin(phase + 1.4)), 12 + int(2 * math.cos(phase + 0.4)), FISH_O, 3, -1),
        (50 + int(7 * math.sin(phase + 2.8)), 6 + int(1 * math.cos(phase + 2.2)), FISH_P, 2, 1),
        (20 + int(5 * math.sin(phase + 3.5)), 16 + int(1 * math.cos(phase + 1.9)), FISH_B, 1, -1),
        (42 + int(6 * math.sin(phase + 4.8)), 14 + int(1 * math.cos(phase + 0.7)), FISH_Y, 1, 1),
    ]
    for x, y, color, size, facing in specs:
        _draw_fish_shape(draw, x, y, color, size, facing)


def _draw_bubbles(draw, frame):
    phase = 2.0 * math.pi * frame / N
    cols = [6, 17, 31, 45, 57]
    for i, x in enumerate(cols):
        y = 22 - int(9 * (0.5 + 0.5 * math.sin(phase + i * 0.8)))
        if 2 <= y <= 23:
            draw.point((x, y), fill=BUBBLE)
            if (frame + i) % 2 == 0 and y - 1 >= 0:
                draw.point((x + 1, y - 1), fill=BUBBLE)


def _make_frame(frame):
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    _draw_water(draw)
    _draw_floor(draw, frame)
    _draw_seaweed(draw, frame)
    _draw_fish(draw, frame)
    _draw_bubbles(draw, frame)
    return img


FRAMES = [_make_frame(f) for f in range(N)]
