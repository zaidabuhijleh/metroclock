import math
from PIL import Image, ImageDraw

NAME = "Alpine Cabin"
FPS = 6
W, H, N = 64, 32, 8


def _lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _pine(draw, x, base, height, color):
    draw.rectangle([x, base - height, x + 1, base], fill=(72, 50, 45))
    for y, spread in ((base - 4, 5), (base - 8, 4), (base - 12, 3), (base - height + 2, 2)):
        draw.polygon([(x, y - 5), (x - spread, y + 2), (x + spread, y + 2)], fill=color)


def _make(frame):
    image = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(image)
    for y in range(19):
        draw.line([(0, y), (63, y)], fill=_lerp((29, 66, 126), (128, 167, 196), y / 18))
    draw.ellipse([7, 3, 14, 10], fill=(236, 219, 167))
    draw.polygon([(0, 20), (11, 9), (20, 18), (31, 6), (42, 17), (52, 9), (63, 18), (63, 25), (0, 25)], fill=(73, 101, 139))
    draw.polygon([(0, 21), (11, 9), (15, 14), (20, 18), (31, 6), (35, 12), (42, 17), (52, 9), (56, 14), (63, 18)], fill=(203, 219, 225))
    draw.polygon([(0, 24), (15, 17), (26, 22), (39, 15), (52, 21), (63, 18), (63, 28), (0, 28)], fill=(48, 76, 105))
    # Cabin sits on the snow plane instead of being buried by it.
    draw.rectangle([24, 19, 45, 28], fill=(139, 68, 43))
    draw.rectangle([25, 20, 34, 28], fill=(171, 82, 47))
    draw.polygon([(21, 19), (33, 11), (48, 19)], fill=(57, 40, 42))
    draw.line([(22, 18), (33, 10), (47, 18)], fill=(225, 230, 225), width=2)
    draw.rectangle([28, 21, 33, 25], fill=(255, 195, 87))
    draw.rectangle([38, 22, 42, 28], fill=(71, 43, 38))
    draw.rectangle([39, 13, 41, 18], fill=(68, 47, 47))
    draw.rectangle([0, 28, 63, 31], fill=(210, 224, 229))
    draw.polygon([(0, 27), (18, 25), (35, 27), (50, 25), (63, 27), (63, 31), (0, 31)], fill=(230, 238, 237))
    _pine(draw, 6, 30, 19, (19, 63, 60))
    _pine(draw, 56, 30, 21, (14, 53, 55))
    _pine(draw, 14, 28, 13, (28, 77, 66))
    p = math.tau * frame / N
    for i in range(3):
        x = 40 + round(2 * math.sin(p + i))
        y = 11 - i * 3 - round(2 * math.sin(p + i * 1.4))
        shade = [(121, 134, 151), (158, 170, 181), (197, 205, 209)][i]
        draw.ellipse([x - i, y - 1, x + i + 2, y + 1], fill=shade)
    return image


FRAMES = [_make(i) for i in range(N)]
