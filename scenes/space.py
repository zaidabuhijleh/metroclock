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
SEAWEED = (55, 200, 95)
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


def _draw_floor(draw):
    draw.rectangle([0, 24, W - 1, H - 1], fill=SAND)
    for x in range(0, W, 4):
        draw.point((x, 24 + (x % 2)), fill=SAND_SHADE)

    # Coral blocks
    draw.rectangle([4, 20, 10, 27], fill=CORAL_A)
    draw.rectangle([14, 22, 20, 28], fill=CORAL_B)
    draw.rectangle([24, 19, 30, 27], fill=CORAL_C)
    draw.rectangle([42, 21, 49, 29], fill=CORAL_A)
    draw.rectangle([53, 20, 60, 28], fill=CORAL_B)

    # Seaweed strands
    for sx in [8, 18, 27, 46, 56]:
        draw.line([(sx, 24), (sx + 1, 16)], fill=SEAWEED)
        draw.line([(sx + 1, 24), (sx + 2, 17)], fill=SEAWEED)


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
    _draw_floor(draw)
    _draw_fish(draw, frame)
    _draw_bubbles(draw, frame)
    return img


FRAMES = [_make_frame(f) for f in range(6)]
