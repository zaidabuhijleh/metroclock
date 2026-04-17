from PIL import Image, ImageDraw

NAME = "Beach"
FPS = 4

W, H = 64, 32

SKY_TOP    = ( 30, 100, 200)
SKY_BOT    = ( 80, 170, 230)
SUN_CORE   = (255, 245,  80)
SUN_HALO   = (255, 210,  50)
SAND_TOP   = (235, 195, 110)
SAND_BOT   = (210, 165,  80)
PALM_TRUNK = (150, 100,  45)
PALM_LEAF  = ( 40, 175,  55)
PALM_DARK  = ( 20, 110,  30)
COCONUT    = (120,  70,  25)
OCEAN_TOP  = ( 40, 120, 210)
OCEAN_BOT  = ( 10,  70, 160)
FOAM       = (235, 248, 255)
FOAM_DIM   = (160, 200, 240)


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _draw_sky(draw):
    for y in range(14):
        c = _lerp(SKY_TOP, SKY_BOT, y / 13)
        draw.line([(0, y), (W - 1, y)], fill=c)


def _draw_sun(draw):
    cx, cy = 55, 7
    draw.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=SUN_HALO)
    draw.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=SUN_CORE)


def _draw_ocean(draw, frame):
    for y in range(14, 21):
        c = _lerp(OCEAN_TOP, OCEAN_BOT, (y - 14) / 6)
        draw.line([(0, y), (W - 1, y)], fill=c)
    # Two wave crests, shifting each frame
    for wi, wy in enumerate([15, 18]):
        shift = (frame * 5 + wi * 18) % W
        for x in range(W):
            wx = (x + shift) % W
            if wx < 12:
                c = FOAM if wx < 6 else FOAM_DIM
                draw.point((x, wy), fill=c)
                draw.point((x, wy + 1), fill=FOAM_DIM if wx < 4 else OCEAN_TOP)


def _draw_beach(draw):
    for y in range(21, H):
        c = _lerp(SAND_TOP, SAND_BOT, (y - 21) / (H - 22))
        draw.line([(0, y), (W - 1, y)], fill=c)


def _draw_palm(draw, bx, by, lean, height):
    for i in range(height):
        tx = bx + int(lean * i / height)
        ty = by - i
        if 0 <= tx < W and 0 <= ty < H:
            draw.point((tx, ty), fill=PALM_TRUNK)
            if tx + 1 < W:
                draw.point((tx + 1, ty), fill=PALM_TRUNK)
    tip_x = bx + lean
    tip_y = by - height
    leaf_dirs = [(-8, -3), (-5, -6), (-1, -7), (3, -6), (6, -4), (8, -1), (7, 2), (-7, 2)]
    for i, (dx, dy) in enumerate(leaf_dirs):
        c = PALM_LEAF if i % 2 == 0 else PALM_DARK
        draw.line([(tip_x, tip_y), (tip_x + dx, tip_y + dy)], fill=c)
    for dx, dy in [(-2, 1), (1, 2), (3, 1)]:
        cx2, cy2 = tip_x + dx, tip_y + dy
        if 0 <= cx2 < W and 0 <= cy2 < H:
            draw.point((cx2, cy2), fill=COCONUT)


def _make_frame(frame):
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    _draw_sky(draw)
    _draw_sun(draw)
    _draw_ocean(draw, frame)
    _draw_beach(draw)
    _draw_palm(draw, bx=9,  by=20, lean=3,  height=12)
    _draw_palm(draw, bx=22, by=20, lean=-2, height=9)
    return img


FRAMES = [_make_frame(f) for f in range(4)]
