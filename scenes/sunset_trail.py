import math
from PIL import Image, ImageDraw

NAME = "Sunset Trail"
COLLECTION = "Places"
FPS = 6
W, H, N = 64, 32, 8


def _lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _tree(draw, x, base, scale, sway):
    draw.polygon([(x - 2, base), (x, base - 13 * scale), (x + 3, base)], fill=(70, 45, 39))
    crown = (x + sway, base - 12 * scale)
    draw.ellipse([crown[0] - 7 * scale, crown[1] - 7 * scale, crown[0] + 7 * scale, crown[1] + 3 * scale], fill=(25, 67, 54))
    draw.ellipse([crown[0] - 5 * scale, crown[1] - 9 * scale, crown[0] + 3 * scale, crown[1]], fill=(37, 92, 60))


def _make(frame):
    image = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(image)
    colors = ((42, 44, 111), (197, 72, 102), (250, 145, 83), (255, 205, 112))
    for y in range(21):
        section = min(2, y // 7)
        draw.line([(0, y), (63, y)], fill=_lerp(colors[section], colors[section + 1], (y % 7) / 6))
    draw.ellipse([28, 9, 38, 19], fill=(255, 207, 112))
    draw.ellipse([31, 12, 36, 17], fill=(255, 238, 157))
    draw.polygon([(0, 21), (10, 17), (20, 20), (31, 16), (42, 20), (53, 17), (63, 20), (63, 31), (0, 31)], fill=(52, 91, 68))
    draw.polygon([(0, 25), (13, 21), (25, 23), (39, 21), (52, 24), (63, 21), (63, 31), (0, 31)], fill=(31, 65, 52))
    # The trail is now the focal axis and remains unobstructed.
    draw.polygon([(23, 31), (28, 27), (30, 23), (33, 20), (36, 23), (39, 27), (45, 31)], fill=(205, 139, 82))
    draw.line([(24, 31), (29, 27), (31, 23), (33, 20)], fill=(239, 183, 105))
    draw.line([(44, 31), (38, 27), (35, 23), (33, 20)], fill=(139, 87, 65))
    sway = round(math.sin(math.tau * frame / N))
    _tree(draw, 7, 29, 1, sway)
    _tree(draw, 56, 29, 1, -sway)
    _tree(draw, 17, 26, .65, 0)
    _tree(draw, 48, 26, .65, 0)
    for x, color in ((13, (224, 101, 103)), (19, (242, 183, 94)), (50, (222, 93, 137)), (55, (244, 190, 103))):
        draw.rectangle([x, 28, x + 1, 29], fill=color)
    return image


FRAMES = [_make(i) for i in range(N)]
