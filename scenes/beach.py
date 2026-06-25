import math
from PIL import Image, ImageDraw

NAME = "Beach"
FPS = 6
W, H, N = 64, 32, 8


def _lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _palm(draw, frame):
    trunk = [(5, 31), (7, 24), (9, 18), (12, 13), (14, 9)]
    draw.line(trunk, fill=(91, 48, 35), width=3)
    draw.line([(7, 29), (9, 22), (12, 15)], fill=(154, 83, 46))
    sway = round(math.sin(math.tau * frame / N))
    crown = (14 + sway, 9)
    leaves = [(-13, -3), (-10, -7), (-4, -8), (4, -7), (11, -4), (14, 0), (9, 4), (-8, 3)]
    for i, (dx, dy) in enumerate(leaves):
        end = (crown[0] + dx, crown[1] + dy)
        draw.line([crown, end], fill=(12, 82, 61) if i % 2 else (19, 118, 66), width=2)
    draw.rectangle([12 + sway, 9, 15 + sway, 11], fill=(83, 48, 31))


def _make(frame):
    image = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(image)
    sky_a, sky_b = (19, 72, 143), (89, 179, 211)
    for y in range(18):
        draw.line([(0, y), (63, y)], fill=_lerp(sky_a, sky_b, y / 17))
    draw.ellipse([49, 3, 59, 13], fill=(255, 218, 96))
    draw.ellipse([52, 6, 57, 11], fill=(255, 245, 174))
    draw.polygon([(35, 17), (42, 13), (49, 16), (55, 14), (63, 17)], fill=(43, 92, 99))
    for y in range(17, 26):
        draw.line([(0, y), (63, y)], fill=_lerp((27, 132, 176), (10, 61, 124), (y - 17) / 8))
    # A diagonal shore creates depth and keeps the center open.
    draw.polygon([(0, 27), (18, 25), (35, 24), (52, 25), (63, 27), (63, 31), (0, 31)], fill=(225, 174, 91))
    draw.line([(0, 26), (18, 24), (35, 23), (52, 24), (63, 26)], fill=(238, 249, 230), width=2)
    shift = frame % 4
    for x in range(-8 + shift * 3, 64, 18):
        draw.line([(x, 20), (x + 8, 20)], fill=(93, 203, 213))
        draw.line([(x + 4, 23), (x + 11, 23)], fill=(177, 232, 225))
    _palm(draw, frame)
    # Foreground shells are clustered, not flickering.
    draw.rectangle([47, 28, 50, 29], fill=(205, 91, 75))
    draw.point((49, 27), fill=(245, 141, 104))
    for bx, by in ((25, 6), (31, 8)):
        wing = -1 if frame in (1, 2, 5, 6) else 0
        draw.line([(bx - 2, by + wing), (bx, by), (bx + 2, by + wing)], fill=(226, 239, 237))
    return image


FRAMES = [_make(i) for i in range(N)]
