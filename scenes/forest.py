from PIL import Image, ImageDraw

NAME = "Sunset Trail"
FPS = 5

W, H = 64, 32

SKY_TOP = (80, 140, 255)
SKY_MID = (255, 160, 90)
SKY_BOT = (255, 210, 130)
SUN = (255, 210, 90)
SUN_CORE = (255, 245, 150)
HILL_BACK = (110, 190, 105)
HILL_FRONT = (75, 150, 70)
TRUNK = (205, 120, 50)
BRANCH = (245, 185, 95)
LEAF = (35, 165, 65)
LEAF_DARK = (20, 120, 45)
PATH = (220, 180, 110)
PATH_EDGE = (175, 130, 72)
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

    draw.line([(tx - 3, base_y - 5), (tx + 3, base_y - 6)], fill=BRANCH)
    draw.line([(tx - 2, base_y - 3), (tx + 4, base_y - 4)], fill=BRANCH)

    left = tx - canopy_w // 2
    right = tx + canopy_w // 2
    top = base_y - 12
    for y in range(top, base_y - 4):
        for x in range(left, right + 1):
            if 0 <= x < W:
                color = LEAF if (x + y) % 2 == 0 else LEAF_DARK
                draw.point((x, y), fill=color)


def _draw_ground(draw, frame):
    back = [(0, 20), (8, 18), (16, 19), (25, 17), (35, 19), (46, 18), (55, 19), (63, 18), (63, 32), (0, 32)]
    draw.polygon(back, fill=HILL_BACK)
    front = [(0, 24), (10, 22), (20, 24), (30, 21), (40, 24), (50, 22), (63, 24), (63, 32), (0, 32)]
    draw.polygon(front, fill=HILL_FRONT)

    path = [(24, 32), (30, 25), (36, 32)]
    draw.polygon(path, fill=PATH)
    draw.line([(30, 25), (24, 32)], fill=PATH_EDGE)
    draw.line([(30, 25), (36, 32)], fill=PATH_EDGE)

    # Tiny flower twinkle.
    flowers = [(6, 23), (12, 25), (46, 24), (54, 23), (58, 25)]
    for i, (fx, fy) in enumerate(flowers):
        color = FLOWER_A if (frame + i) % 2 == 0 else FLOWER_B
        draw.point((fx, fy), fill=color)


def _make_frame(frame):
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    _draw_sky(draw)
    draw.ellipse([47, 5, 58, 16], fill=SUN)
    draw.ellipse([50, 8, 55, 13], fill=SUN_CORE)

    _draw_ground(draw, frame)
    _draw_tree(draw, 8, 24, 7)
    _draw_tree(draw, 17, 25, 6)
    _draw_tree(draw, 48, 24, 8)
    _draw_tree(draw, 57, 25, 6)
    _draw_tree(draw, 32, 23, 10)
    return img


FRAMES = [_make_frame(f) for f in range(5)]
