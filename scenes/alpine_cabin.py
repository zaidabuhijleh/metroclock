from PIL import Image, ImageDraw

NAME = "Alpine Cabin"
FPS = 6

W, H = 64, 32
N = 6

SKY_TOP = (90, 175, 255)
SKY_BOT = (190, 230, 255)
SUN = (255, 225, 120)
SUN_GLOW = (255, 245, 170)
MOUNTAIN_BACK = (180, 210, 245)
MOUNTAIN_FRONT = (140, 185, 235)
SNOW = (235, 245, 255)
SNOW_SHADE = (195, 220, 250)
TREE = (35, 150, 70)
TREE_DARK = (20, 105, 52)
TREE_TRUNK = (205, 120, 50)
CABIN_WALL = (225, 120, 55)
CABIN_WALL_SHADE = (190, 92, 40)
ROOF = (110, 55, 25)
ROOF_HILITE = (250, 250, 255)
WINDOW = (255, 225, 120)
WINDOW_HOT = (255, 170, 50)
SMOKE = (170, 185, 210)

_SMOKE_SWAY = [0, 1, 2, 1, 0, -1]


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _draw_sky(draw):
    for y in range(0, 18):
        c = _lerp(SKY_TOP, SKY_BOT, y / 17)
        draw.line([(0, y), (W - 1, y)], fill=c)


def _draw_mountains(draw):
    back = [(0, 18), (8, 13), (15, 16), (24, 11), (34, 15), (43, 10), (52, 14), (63, 12), (63, 20), (0, 20)]
    front = [(0, 21), (9, 17), (18, 20), (27, 16), (38, 19), (49, 15), (63, 18), (63, 24), (0, 24)]
    draw.polygon(back, fill=MOUNTAIN_BACK)
    draw.polygon(front, fill=MOUNTAIN_FRONT)
    for x in range(0, W, 5):
        draw.point((x, 20 + (x % 3)), fill=SNOW)


def _draw_pine(draw, tx, base_y, spread):
    trunk_top = base_y - 8
    draw.line([(tx, trunk_top), (tx, base_y + 1)], fill=TREE_TRUNK)
    if tx + 1 < W:
        draw.line([(tx + 1, trunk_top + 1), (tx + 1, base_y + 1)], fill=TREE_TRUNK)

    # Horizontal leafy tiers for a cleaner pine look.
    tiers = [spread + 1, spread, spread - 1, spread - 2]
    for i, sw in enumerate(tiers):
        y = base_y - 2 - i * 2
        sw = max(1, sw)
        color = TREE if i % 2 == 0 else TREE_DARK
        draw.line([(tx - sw, y), (tx + sw, y)], fill=color)
        if sw > 1 and y - 1 >= 0:
            draw.line([(tx - (sw - 1), y - 1), (tx + (sw - 1), y - 1)], fill=TREE_DARK)


def _draw_cabin(draw):
    draw.rectangle([23, 19, 45, 28], fill=CABIN_WALL)
    draw.rectangle([35, 19, 45, 28], fill=CABIN_WALL_SHADE)

    draw.polygon([(20, 19), (32, 10), (48, 19)], fill=ROOF)
    draw.line([(20, 19), (32, 10)], fill=ROOF_HILITE)
    draw.line([(21, 19), (33, 10)], fill=ROOF_HILITE)
    draw.line([(32, 10), (48, 19)], fill=(200, 220, 245))
    draw.line([(21, 20), (47, 20)], fill=(75, 35, 15))

    draw.rectangle([37, 22, 41, 28], fill=ROOF)
    draw.rectangle([27, 21, 33, 25], fill=WINDOW)
    draw.rectangle([29, 22, 31, 24], fill=WINDOW_HOT)
    draw.rectangle([39, 12, 41, 18], fill=ROOF)


def _draw_ground(draw, frame):
    draw.rectangle([0, 24, W - 1, H - 1], fill=SNOW)

    # Texture bands and footprints-like compression for depth.
    for y in [25, 27, 29]:
        shade = _lerp(SNOW_SHADE, SNOW, (y - 24) / 6)
        draw.line([(0, y), (W - 1, y)], fill=shade)

    for x in range(0, W, 3):
        bump = (x + frame) % 3
        if bump == 0:
            draw.point((x, 24), fill=SNOW_SHADE)
        elif bump == 1 and x + 1 < W:
            draw.point((x + 1, 25), fill=SNOW_SHADE)
        else:
            draw.point((x, 26), fill=SNOW_SHADE)

    for x in range(2, W, 8):
        y = 30 + ((x + frame) % 2)
        if y < H:
            draw.point((x, y), fill=SNOW_SHADE)
            if x + 1 < W:
                draw.point((x + 1, y), fill=SNOW_SHADE)


def _draw_smoke(draw, frame):
    sway = _SMOKE_SWAY[frame % N]
    for i in range(4):
        x = 40 + sway + (i % 2)
        y = 11 - i - (1 if frame % 2 == 0 else 0)
        if 0 <= x < W and 0 <= y < H:
            draw.point((x, y), fill=SMOKE)


def _make_frame(frame):
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    _draw_sky(draw)
    glow_shift = 1 if frame in (1, 2, 4, 5) else 0
    draw.ellipse([5, 3, 15, 13], fill=SUN)
    draw.ellipse([7 - glow_shift, 5, 13 + glow_shift, 11], fill=SUN_GLOW)

    _draw_mountains(draw)
    _draw_pine(draw, 7, 24, 4)
    _draw_pine(draw, 15, 25, 3)
    _draw_pine(draw, 51, 24, 4)
    _draw_pine(draw, 58, 25, 3)
    _draw_cabin(draw)
    _draw_ground(draw, frame)
    _draw_smoke(draw, frame)

    return img


FRAMES = [_make_frame(f) for f in range(N)]
