import math
from PIL import Image, ImageDraw

NAME = "Lofi Cat"
FPS = 6
W, H, N = 64, 32, 8


def _lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _make(frame):
    image = Image.new("RGB", (W, H), (27, 22, 48))
    draw = ImageDraw.Draw(image)
    p = math.tau * frame / N
    # Stable grouped firelight, without full-screen flicker.
    for radius in range(22, 3, -3):
        color = _lerp((37, 25, 51), (111, 55, 48), (22 - radius) / 22)
        draw.ellipse([23 - radius, 20 - radius // 2, 23 + radius, 20 + radius // 2], fill=color)
    draw.rectangle([0, 3, 13, 23], fill=(72, 48, 43))
    for y in (8, 14, 20):
        draw.line([(0, y), (13, y)], fill=(131, 79, 50), width=2)
    books = ((2, 5, (176, 73, 77)), (5, 5, (66, 113, 153)), (8, 5, (189, 145, 69)), (2, 11, (79, 137, 98)), (6, 11, (157, 89, 159)), (10, 11, (190, 111, 68)), (1, 17, (67, 128, 158)), (5, 17, (192, 91, 111)), (9, 17, (113, 145, 81)))
    for x, y, c in books:
        draw.rectangle([x, y, x + 2, y + 3], fill=c)
    # Moonlit window is a cool counterweight to the hearth.
    draw.rectangle([43, 2, 63, 18], fill=(99, 86, 91))
    draw.rectangle([45, 4, 61, 16], fill=(8, 17, 40))
    draw.line([(53, 4), (53, 16)], fill=(80, 75, 89))
    draw.ellipse([55, 5, 60, 10], fill=(226, 213, 166))
    for sx, sy in ((47, 6), (50, 12), (58, 14)):
        draw.point((sx, sy), fill=(150, 174, 206))
    draw.rectangle([17, 8, 35, 23], fill=(87, 72, 67))
    draw.rectangle([15, 7, 37, 9], fill=(130, 94, 68))
    draw.rectangle([20, 11, 33, 23], fill=(25, 19, 22))
    flame_h = 5 + round(2 * math.sin(p))
    draw.polygon([(22, 22), (25, 22 - flame_h), (27, 19), (29, 22 - flame_h + 1), (32, 22)], fill=(211, 67, 33))
    draw.polygon([(24, 22), (26, 22 - flame_h + 2), (28, 20), (30, 22)], fill=(255, 154, 47))
    draw.rectangle([0, 23, 63, 31], fill=(62, 38, 34))
    draw.line([(0, 24), (63, 24)], fill=(91, 53, 40))
    draw.ellipse([25, 25, 55, 31], fill=(74, 43, 48))
    # Large clean cat silhouette, separated from the furniture.
    draw.ellipse([31, 22, 50, 30], fill=(163, 133, 110))
    draw.ellipse([43, 19, 55, 27], fill=(185, 154, 128))
    draw.polygon([(45, 21), (46, 17), (49, 21)], fill=(174, 141, 116))
    draw.polygon([(51, 21), (54, 18), (54, 22)], fill=(174, 141, 116))
    blink = frame in (4, 5)
    if blink:
        draw.line([(47, 23), (48, 23)], fill=(55, 47, 45))
        draw.line([(51, 23), (52, 23)], fill=(55, 47, 45))
    else:
        draw.rectangle([47, 22, 48, 23], fill=(79, 170, 124))
        draw.rectangle([51, 22, 52, 23], fill=(79, 170, 124))
    draw.point((50, 24), fill=(226, 125, 126))
    tail = [(32, 27), (27, 28), (23, 26), (22 + round(2 * math.sin(p)), 23)]
    draw.line(tail, fill=(163, 133, 110), width=2)
    return image


FRAMES = [_make(i) for i in range(N)]
