from PIL import Image, ImageDraw

NAME = "Beach"
FPS = 4

W, H = 64, 32

# Palette
SKY_TOP    = (10,  40, 100)
SKY_BOT    = (40, 100, 180)
SUN_CORE   = (255, 240, 80)
SUN_HALO   = (255, 200, 60)
SAND       = (210, 175, 100)
SAND_DARK  = (180, 145,  75)
PALM_TRUNK = (120,  80,  30)
PALM_LEAF  = ( 30, 130,  40)
PALM_DARK  = ( 20,  90,  25)
COCONUT    = ( 90,  55,  20)
OCEAN_DEEP = ( 10,  70, 160)
OCEAN_MID  = ( 20, 100, 190)
OCEAN_LITE = ( 60, 140, 210)
FOAM       = (220, 235, 255)
FOAM_DIM   = (160, 185, 220)


def _lerp_color(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _draw_sky(draw):
    for y in range(18):
        t = y / 17
        c = _lerp_color(SKY_TOP, SKY_BOT, t)
        draw.line([(0, y), (W - 1, y)], fill=c)


def _draw_sun(draw):
    cx, cy = 54, 5
    for r, c in [(5, SUN_HALO), (3, SUN_CORE)]:
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c)


def _draw_palm(draw, base_x, base_y, lean, height):
    x, y = base_x, base_y
    for i in range(height):
        tx = x + int(lean * i / height)
        ty = y - i
        if 0 <= tx < W and 0 <= ty < H:
            draw.point((tx, ty), fill=PALM_TRUNK)
            draw.point((tx + 1, ty), fill=PALM_TRUNK)
    # Crown
    tip_x = x + lean
    tip_y = y - height
    leaf_dirs = [(-6, -3), (-4, -5), (0, -6), (4, -5), (6, -3), (5, 0), (-5, 0)]
    for i, (dx, dy) in enumerate(leaf_dirs):
        c = PALM_LEAF if i % 2 == 0 else PALM_DARK
        draw.line([(tip_x, tip_y), (tip_x + dx, tip_y + dy)], fill=c)
    # Coconuts
    for dx, dy in [(-2, 1), (1, 1), (2, 3)]:
        cx2, cy2 = tip_x + dx, tip_y + dy
        if 0 <= cx2 < W and 0 <= cy2 < H:
            draw.point((cx2, cy2), fill=COCONUT)


def _draw_ocean(draw, frame):
    # Ocean base rows 18-24
    for y in range(18, 25):
        t = (y - 18) / 6
        c = _lerp_color(OCEAN_LITE, OCEAN_DEEP, t)
        draw.line([(0, y), (W - 1, y)], fill=c)

    # 3 wave crests, each shifts right each frame
    for wave_i, base_x in enumerate([0, 22, 44]):
        shift = (frame * 3 + wave_i * 8) % W
        y_wave = 19 + wave_i
        for x in range(W):
            wx = (x + shift) % W
            # Foam crest is a ~6px wide bump
            if wx < 6:
                intensity = 1.0 - wx / 6
                c = FOAM if intensity > 0.5 else FOAM_DIM
                draw.point((x, y_wave), fill=c)


def _draw_beach(draw):
    for y in range(25, H):
        t = (y - 25) / (H - 25 - 1) if H - 25 > 1 else 0
        c = _lerp_color(SAND, SAND_DARK, t * 0.4)
        draw.line([(0, y), (W - 1, y)], fill=c)


def _make_frame(frame):
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    _draw_sky(draw)
    _draw_sun(draw)
    _draw_ocean(draw, frame)
    _draw_beach(draw)
    _draw_palm(draw, base_x=8,  base_y=24, lean=2,  height=11)
    _draw_palm(draw, base_x=18, base_y=24, lean=-1, height=8)
    return img


FRAMES = [_make_frame(f) for f in range(3)]
