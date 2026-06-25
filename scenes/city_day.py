import math
from PIL import Image, ImageDraw

NAME = "City Day"
FPS = 6
W, H, N = 64, 32, 8


def _lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _person(draw, x, y, color, step):
    draw.rectangle([x, y - 5, x + 1, y - 4], fill=(229, 178, 137))
    draw.rectangle([x - 1, y - 3, x + 2, y - 1], fill=color)
    draw.point((x - (step > 0), y), fill=(38, 49, 72))
    draw.point((x + 1 + (step < 0), y), fill=(38, 49, 72))


def _make(frame):
    image = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(image)
    for y in range(18):
        draw.line([(0, y), (63, y)], fill=_lerp((55, 133, 215), (169, 215, 233), y / 17))
    draw.ellipse([51, 2, 61, 12], fill=(255, 218, 103))
    cloud_x = (frame - 3) % 12
    draw.rectangle([4 + cloud_x, 5, 16 + cloud_x, 7], fill=(224, 240, 241))
    draw.rectangle([8 + cloud_x, 3, 13 + cloud_x, 7], fill=(241, 248, 243))
    buildings = [
        (0, 10, 12, (62, 82, 113)), (9, 7, 8, (114, 99, 115)),
        (15, 12, 14, (55, 74, 103)), (28, 8, 10, (132, 107, 101)),
        (36, 14, 17, (58, 78, 111)), (50, 8, 11, (104, 105, 121)), (58, 6, 9, (52, 70, 99)),
    ]
    for x, width, height, color in buildings:
        top = 22 - height
        draw.rectangle([x, top, x + width, 22], fill=color)
        draw.line([(x, top), (x + width, top)], fill=_lerp(color, (255, 255, 255), .28))
        for wy in range(top + 2, 21, 4):
            for wx in range(x + 2, x + width, 4):
                draw.rectangle([wx, wy, wx + 1, wy + 1], fill=(239, 210, 121))
    # Tree canopy frames the skyline while the promenade stays readable.
    draw.rectangle([0, 21, 63, 23], fill=(46, 124, 77))
    for tx in (5, 57):
        draw.rectangle([tx, 17, tx + 2, 25], fill=(90, 59, 45))
        draw.ellipse([tx - 6, 13, tx + 8, 20], fill=(29, 105, 65))
        draw.ellipse([tx - 3, 11, tx + 6, 18], fill=(43, 137, 75))
    draw.polygon([(0, 24), (63, 24), (63, 31), (0, 31)], fill=(181, 171, 151))
    draw.polygon([(20, 24), (44, 24), (53, 31), (11, 31)], fill=(211, 198, 171))
    draw.line([(32, 24), (32, 31)], fill=(165, 153, 137))
    phase = math.tau * frame / N
    _person(draw, 18 + round(3 * math.sin(phase)), 30, (210, 70, 68), 1 if frame < 4 else -1)
    _person(draw, 43 + round(3 * math.sin(phase + math.pi)), 29, (55, 111, 190), -1 if frame < 4 else 1)
    return image


FRAMES = [_make(i) for i in range(N)]
