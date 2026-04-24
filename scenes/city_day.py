from PIL import Image, ImageDraw

NAME = "City Day"
FPS = 6

W, H = 64, 32
N = 8

SKY_TOP = (95, 175, 255)
SKY_BOT = (185, 228, 255)
SUN_OUTER = (255, 220, 90)
SUN_INNER = (255, 250, 200)
CLOUD_HI = (255, 255, 255)
CLOUD_LO = (220, 235, 250)
PLAZA = (200, 194, 184)
PLAZA_SHADE = (165, 160, 152)
GRASS = (112, 186, 112)
TREE_LEAF = (58, 160, 85)
TREE_TRUNK = (145, 92, 55)

_BLDGS = [
    (0, 8, 12, (146, 138, 128)),
    (7, 9, 17, (110, 124, 146)),
    (15, 7, 10, (176, 164, 148)),
    (21, 11, 15, (124, 138, 158)),
    (31, 8, 11, (163, 150, 136)),
    (38, 10, 18, (98, 114, 137)),
    (47, 9, 13, (147, 142, 132)),
    (55, 9, 9, (135, 154, 171)),
]

WIN_LIT = (248, 236, 150)
WIN_DIM = (188, 211, 238)

SHIRT_A = (230, 92, 72)
SHIRT_B = (74, 136, 230)
SHIRT_C = (244, 168, 72)
PANTS = (70, 78, 96)
SKIN = (236, 196, 158)

_PACE = [0, 1, 2, 3, 4, 3, 2, 1]
_GAIT = [0, 1, 2, 1, 0, -1, -2, -1]


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _draw_sky(draw):
    for y in range(16):
        draw.line([(0, y), (W - 1, y)], fill=_lerp(SKY_TOP, SKY_BOT, y / 15))


def _draw_sun(draw):
    draw.ellipse([48, 2, 62, 16], fill=SUN_OUTER)
    draw.ellipse([51, 5, 59, 13], fill=SUN_INNER)


def _draw_cloud(draw, cx, cy, r):
    draw.ellipse([cx - r, cy - r // 2, cx + r, cy + r // 2], fill=CLOUD_HI)
    draw.ellipse([cx - r + 2, cy - r, cx + r - 2, cy + 2], fill=CLOUD_HI)
    draw.ellipse([cx - r // 2 - 2, cy, cx + r // 2 + 2, cy + r // 2 + 2], fill=CLOUD_LO)


def _draw_buildings(draw):
    base_y = 23
    for bx, bw, bh, color in _BLDGS:
        top = base_y - bh
        draw.rectangle([bx, top, bx + bw - 1, base_y], fill=color)
        draw.line([(bx, top), (bx + bw - 1, top)], fill=_lerp(color, (255, 255, 255), 0.25))
        draw.line([(bx, top), (bx, base_y)], fill=_lerp(color, (0, 0, 0), 0.2))
        for wy in range(top + 2, base_y - 1, 3):
            for wx in range(bx + 1, bx + bw - 1, 3):
                wc = WIN_LIT if (wx + wy) % 3 != 0 else WIN_DIM
                draw.point((wx, wy), fill=wc)


def _draw_plaza(draw):
    draw.rectangle([0, 23, W - 1, 31], fill=PLAZA)
    draw.line([(0, 23), (W - 1, 23)], fill=PLAZA_SHADE)
    for x in range(0, W, 8):
        draw.line([(x, 23), (x, 31)], fill=PLAZA_SHADE)
    draw.rectangle([0, 19, W - 1, 22], fill=GRASS)

    # small trees / planters
    for tx in [8, 20, 44, 56]:
        draw.line([(tx, 21), (tx, 18)], fill=TREE_TRUNK)
        draw.line([(tx - 1, 20), (tx + 1, 20)], fill=TREE_LEAF)
        draw.line([(tx - 2, 19), (tx + 2, 19)], fill=TREE_LEAF)
        draw.point((tx, 18), fill=TREE_LEAF)


def _draw_person(draw, x, ground_y, shirt, frame_index):
    step = _GAIT[frame_index % N]

    # head
    draw.point((x, ground_y - 5), fill=SKIN)
    draw.point((x + 1, ground_y - 5), fill=SKIN)
    # torso
    draw.line([(x, ground_y - 4), (x, ground_y - 2)], fill=shirt)
    draw.line([(x + 1, ground_y - 4), (x + 1, ground_y - 2)], fill=shirt)
    # arms
    draw.point((x - 1, ground_y - 3), fill=shirt)
    draw.point((x + 2, ground_y - 3), fill=shirt)
    # legs
    draw.point((x, ground_y - 1), fill=PANTS)
    draw.point((x + 1, ground_y - 1), fill=PANTS)
    lx = x - 1 if step > 0 else x
    rx = x + 2 if step < 0 else x + 1
    draw.point((lx, ground_y), fill=PANTS)
    draw.point((rx, ground_y), fill=PANTS)


def _draw_walkers(draw, frame):
    p1 = 7 + _PACE[frame % N]
    p2 = 27 + _PACE[(frame + 2) % N]
    p3 = 51 - _PACE[(frame + 4) % N]
    y = 30
    _draw_person(draw, p1, y, SHIRT_A, frame)
    _draw_person(draw, p2, y, SHIRT_B, (frame + 2) % N)
    _draw_person(draw, p3, y, SHIRT_C, (frame + 4) % N)

    # tiny pigeon moving around the plaza
    px = 36 + _GAIT[(frame + 1) % N]
    draw.point((px, 30), fill=(110, 118, 134))
    draw.point((px + 1, 30), fill=(90, 98, 112))


def _make_frame(frame):
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    _draw_sky(draw)
    _draw_sun(draw)
    _draw_cloud(draw, 12 + _GAIT[(frame + 1) % N], 6, 6)
    _draw_cloud(draw, 33 + _GAIT[(frame + 5) % N], 4, 5)
    _draw_buildings(draw)
    _draw_plaza(draw)
    _draw_walkers(draw, frame)
    return img


FRAMES = [_make_frame(f) for f in range(N)]
