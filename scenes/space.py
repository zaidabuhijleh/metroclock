from PIL import Image, ImageDraw

NAME = "Coral Reef"
FPS = 6

W, H = 64, 32

WATER_TOP = (70, 190, 255)
WATER_MID = (35, 145, 230)
WATER_BOT = (15, 95, 185)
SAND = (230, 200, 120)
SAND_SHADE = (200, 165, 95)
CORAL_A = (255, 125, 120)
CORAL_B = (255, 180, 85)
CORAL_C = (190, 115, 255)
CORAL_D = (255, 95, 165)
SEAWEED = (55, 200, 95)
SEAWEED_DARK = (25, 145, 70)
BUBBLE = (220, 250, 255)
FISH_Y = (255, 240, 100)
FISH_O = (255, 165, 70)
FISH_P = (255, 130, 210)


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
        draw.line([(x + 4, y - dy), (x + 2 + (dy // 2), y - dy - 1)], fill=(255, 220, 210))
        draw.line([(x + 4, y - dy), (x + 6 - (dy // 2), y - dy - 1)], fill=(255, 220, 210))


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


def _draw_floor(draw, frame):
    draw.rectangle([0, 24, W - 1, H - 1], fill=SAND)
    for x in range(0, W, 4):
        draw.point((x, 24 + (x % 2)), fill=SAND_SHADE)
        if (x + frame) % 8 == 0:
            draw.point((x + 1, 26), fill=SAND_SHADE)

    # Organic coral formations.
    _draw_coral_fan(draw, 3, 27, CORAL_A)
    _draw_coral_branch(draw, 16, 29, CORAL_B)
    _draw_coral_brain(draw, 24, 28, CORAL_C)
    _draw_coral_branch(draw, 44, 29, CORAL_D)
    _draw_coral_fan(draw, 53, 28, CORAL_B)

    # tiny polyp sparkle
    sparkle_pts = [(7, 21), (19, 20), (27, 22), (47, 21), (58, 22)]
    for i, (sx, sy) in enumerate(sparkle_pts):
        if (frame + i) % 2 == 0:
            draw.point((sx, sy), fill=(255, 235, 180))

    # Seaweed strands
    for sx in [8, 18, 27, 46, 56]:
        sway = 1 if (frame + sx) % 2 == 0 else 0
        draw.line([(sx, 24), (sx + 1 + sway, 16)], fill=SEAWEED)
        draw.line([(sx + 1, 24), (sx + 2 + sway, 17)], fill=SEAWEED_DARK)


def _draw_fish(draw, frame):
    fish = [
        (8 + (frame * 2) % 70, 8, FISH_Y),
        (28 + (frame * 2) % 70, 13, FISH_O),
        (48 + (frame * 2) % 70, 6, FISH_P),
    ]
    for fx, fy, color in fish:
        x = fx % (W + 10) - 5
        if -4 <= x <= W - 1:
            draw.point((x, fy), fill=color)
            if x - 1 >= 0:
                draw.point((x - 1, fy), fill=color)
            if x + 1 < W:
                draw.point((x + 1, fy), fill=color)
            if x - 2 >= 0:
                draw.point((x - 2, fy - 1), fill=color)
                draw.point((x - 2, fy + 1), fill=color)


def _draw_bubbles(draw, frame):
    cols = [6, 16, 29, 45, 57]
    for i, x in enumerate(cols):
        y = 23 - ((frame + i * 2) % 16)
        if 2 <= y <= 23:
            draw.point((x, y), fill=BUBBLE)
            if y - 1 >= 0 and (frame + i) % 2 == 0:
                draw.point((x + 1, y - 1), fill=BUBBLE)


def _make_frame(frame):
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    _draw_water(draw)
    _draw_floor(draw, frame)
    _draw_fish(draw, frame)
    _draw_bubbles(draw, frame)
    return img


FRAMES = [_make_frame(f) for f in range(6)]
