import math
from PIL import Image, ImageDraw

NAME = "Coral Reef"
FPS = 6
W, H, N = 64, 32, 8


def _lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _fish(draw, x, y, facing, body, accent, large=False):
    s = 1 if facing > 0 else -1
    if large:
        draw.ellipse([x - 6, y - 3, x + 6, y + 3], fill=body)
        draw.polygon([(x - 5 * s, y), (x - 10 * s, y - 4), (x - 10 * s, y + 4)], fill=accent)
        draw.rectangle([x - 1, y - 3, x + 2, y + 3], fill=accent)
        draw.point((x + 4 * s, y - 1), fill=(18, 37, 55))
    else:
        draw.ellipse([x - 3, y - 1, x + 3, y + 1], fill=body)
        draw.polygon([(x - 2 * s, y), (x - 5 * s, y - 2), (x - 5 * s, y + 2)], fill=accent)


def _make(frame):
    image = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(image)
    for y in range(32):
        draw.line([(0, y), (63, y)], fill=_lerp((35, 154, 194), (5, 44, 93), y / 31))
    for x in (8, 27, 49):
        draw.polygon([(x, 0), (x + 5, 0), (x + 16, 26), (x + 10, 26)], fill=(53, 153, 172))
    draw.polygon([(0, 29), (8, 25), (18, 27), (28, 23), (39, 28), (51, 24), (63, 27), (63, 31), (0, 31)], fill=(147, 105, 75))
    draw.polygon([(0, 31), (0, 23), (5, 20), (9, 24), (12, 18), (16, 30)], fill=(181, 57, 92))
    draw.polygon([(47, 31), (50, 21), (53, 26), (56, 17), (59, 25), (63, 21), (63, 31)], fill=(211, 77, 76))
    draw.ellipse([20, 25, 31, 31], fill=(183, 102, 169))
    draw.arc([21, 25, 30, 31], 180, 360, fill=(242, 169, 108), width=1)
    p = math.tau * frame / N
    hero_x = 31 + round(4 * math.sin(p))
    hero_y = 13 + round(2 * math.cos(p))
    _fish(draw, hero_x, hero_y, 1, (244, 184, 76), (232, 83, 76), True)
    _fish(draw, 14 + round(3 * math.sin(p + 2)), 8, 1, (97, 204, 194), (45, 112, 161))
    _fish(draw, 51 + round(3 * math.sin(p + 4)), 9, -1, (217, 116, 178), (117, 66, 145))
    for i, x in enumerate((18, 39, 58)):
        y = 24 - ((frame * 2 + i * 6) % 20)
        if 1 < y < 25:
            draw.rectangle([x, y, x + 1, y + 1], outline=(158, 224, 222))
    return image


FRAMES = [_make(i) for i in range(N)]
