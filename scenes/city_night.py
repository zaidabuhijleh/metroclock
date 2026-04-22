from PIL import Image, ImageDraw

NAME = "City Day"
FPS = 4

W, H = 64, 32

SKY_TOP = (70, 170, 255)
SKY_BOT = (165, 225, 255)
SUN_OUTER = (255, 210, 90)
SUN_INNER = (255, 245, 150)
CLOUD = (240, 250, 255)
BUILDING_A = (80, 140, 220)
BUILDING_B = (120, 175, 235)
BUILDING_C = (95, 160, 245)
WINDOW = (220, 245, 255)
WINDOW_DIM = (170, 210, 245)
ROAD = (130, 130, 150)
ROAD_STRIPE = (240, 240, 220)

_BUILDINGS = [
    (0, 7, 10), (7, 8, 15), (15, 7, 11), (22, 9, 18),
    (31, 7, 13), (38, 8, 16), (46, 7, 12), (53, 11, 20),
]


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _draw_sky(draw):
    for y in range(0, 20):
        c = _lerp(SKY_TOP, SKY_BOT, y / 19)
        draw.line([(0, y), (W - 1, y)], fill=c)


def _draw_cloud(draw, x, y, w):
    draw.ellipse([x, y, x + w, y + 4], fill=CLOUD)
    draw.ellipse([x + 2, y - 2, x + w - 2, y + 3], fill=CLOUD)


def _draw_buildings(draw):
    colors = [BUILDING_A, BUILDING_B, BUILDING_C]
    for i, (bx, bw, bh) in enumerate(_BUILDINGS):
        top = H - 4 - bh
        fill = colors[i % len(colors)]
        draw.rectangle([bx, top, bx + bw - 1, H - 5], fill=fill)
        draw.line([(bx, top), (bx + bw - 1, top)], fill=(210, 240, 255))
        for wy in range(top + 2, H - 7, 3):
            for wx in range(bx + 1, bx + bw - 1, 3):
                color = WINDOW if (wx + wy) % 2 == 0 else WINDOW_DIM
                draw.point((wx, wy), fill=color)
                if wx + 1 < bx + bw - 1:
                    draw.point((wx + 1, wy), fill=color)


def _draw_road(draw, frame):
    draw.rectangle([0, H - 4, W - 1, H - 1], fill=ROAD)
    shift = (frame * 3) % 10
    for x in range(-10, W + 10, 10):
        draw.rectangle([x + shift, H - 3, x + shift + 4, H - 2], fill=ROAD_STRIPE)


def _make_frame(frame):
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    _draw_sky(draw)
    draw.ellipse([48, 2, 60, 14], fill=SUN_OUTER)
    draw.ellipse([51, 5, 57, 11], fill=SUN_INNER)

    _draw_cloud(draw, 4 + (frame % 3), 5, 10)
    _draw_cloud(draw, 22 + ((frame + 1) % 3), 3, 12)

    _draw_buildings(draw)
    _draw_road(draw, frame)
    return img


FRAMES = [_make_frame(f) for f in range(4)]
