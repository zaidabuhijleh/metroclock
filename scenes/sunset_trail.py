from PIL import Image, ImageDraw

NAME = "Sunset Trail"
FPS = 6

W, H = 64, 32
N = 6

SKY_TOP = (80, 140, 255)
SKY_MID = (255, 160, 90)
SKY_BOT = (255, 210, 130)
SUN = (255, 210, 90)
SUN_CORE = (255, 245, 150)
HILL_BACK = (110, 190, 105)
HILL_FRONT = (75, 150, 70)
TRUNK = (205, 120, 50)
LEAF = (35, 165, 65)
LEAF_DARK = (20, 120, 45)
PATH = (214, 176, 110)
PATH_EDGE = (170, 128, 74)
SHRUB_A = (50, 145, 62)
SHRUB_B = (32, 116, 50)
FLOWER_A = (255, 120, 180)
FLOWER_B = (255, 255, 130)


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _draw_sky(draw):
    for y in range(0, 12):
        draw.line([(0, y), (W - 1, y)], fill=_lerp(SKY_TOP, SKY_MID, y / 11))
    for y in range(12, 22):
        draw.line([(0, y), (W - 1, y)], fill=_lerp(SKY_MID, SKY_BOT, (y - 12) / 9))


def _draw_tree(draw, tx, base_y, canopy_w):
    draw.line([(tx, base_y - 8), (tx, base_y + 1)], fill=TRUNK)
    if tx + 1 < W:
        draw.line([(tx + 1, base_y - 7), (tx + 1, base_y + 1)], fill=TRUNK)

    # Flatter, wider canopy so it reads less like a lollipop.
    profile = [canopy_w - 2, canopy_w, canopy_w + 1, canopy_w + 1, canopy_w - 1, canopy_w - 3]
    top = base_y - 11
    for row, spread in enumerate(profile):
        y = top + row
        spread = max(2, spread)
        for x in range(tx - spread, tx + spread + 1):
            if 0 <= x < W:
                if abs(x - tx) == spread and row in (0, len(profile) - 1):
                    continue
                color = LEAF if (x + y + row) % 2 == 0 else LEAF_DARK
                draw.point((x, y), fill=color)


def _draw_ground(draw, frame):
    back = [(0, 20), (8, 18), (16, 19), (25, 17), (35, 19), (46, 18), (55, 19), (63, 18), (63, 32), (0, 32)]
    front = [(0, 24), (10, 22), (20, 24), (30, 21), (40, 24), (50, 22), (63, 24), (63, 32), (0, 32)]
    draw.polygon(back, fill=HILL_BACK)
    draw.polygon(front, fill=HILL_FRONT)

    # Clearer trail perspective and edge definition.
    path = [(22, 32), (27, 27), (29, 24), (32, 23), (35, 24), (37, 27), (42, 32)]
    draw.polygon(path, fill=PATH)
    draw.line([(22, 32), (27, 27), (29, 24), (32, 23)], fill=PATH_EDGE)
    draw.line([(42, 32), (37, 27), (35, 24), (32, 23)], fill=PATH_EDGE)
    draw.line([(28, 30), (32, 26)], fill=(225, 195, 130))
    draw.line([(36, 30), (33, 26)], fill=(225, 195, 130))

    # Shrubs for foreground detail.
    shrubs = [(5, 24), (13, 25), (18, 23), (46, 24), (52, 23), (59, 25)]
    for i, (sx, sy) in enumerate(shrubs):
        c = SHRUB_A if (i + frame) % 2 == 0 else SHRUB_B
        draw.line([(sx - 1, sy), (sx + 1, sy)], fill=c)
        draw.point((sx, sy - 1), fill=c)

    # Flower twinkle.
    flowers = [(6, 25), (12, 27), (20, 26), (45, 26), (54, 25), (58, 27)]
    for i, (fx, fy) in enumerate(flowers):
        color = FLOWER_A if (frame + i) % 2 == 0 else FLOWER_B
        draw.point((fx, fy), fill=color)


def _make_frame(frame):
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    _draw_sky(draw)
    sun_shift = 1 if frame in (1, 2, 4, 5) else 0
    draw.ellipse([47, 5, 58, 16], fill=SUN)
    draw.ellipse([50 - sun_shift, 8, 55 + sun_shift, 13], fill=SUN_CORE)

    _draw_ground(draw, frame)
    _draw_tree(draw, 8, 24, 4)
    _draw_tree(draw, 17, 25, 3)
    _draw_tree(draw, 48, 24, 5)
    _draw_tree(draw, 57, 25, 3)
    _draw_tree(draw, 32, 23, 6)
    return img


FRAMES = [_make_frame(f) for f in range(N)]
