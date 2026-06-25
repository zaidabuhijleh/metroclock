import math

from PIL import Image, ImageDraw

NAME = "Rainy Nook"
COLLECTION = "Cozy"
FPS = 6
W, H, N = 64, 32, 12


def _make(frame):
    image = Image.new("RGB", (W, H), (25, 24, 43))
    draw = ImageDraw.Draw(image)
    phase = math.tau * frame / N

    # Warm wall and a cool window balance the composition.
    for y in range(23):
        color = (42 + y, 34 + y // 2, 55 + y // 3)
        draw.line([(0, y), (63, y)], fill=color)

    draw.rectangle([3, 3, 31, 21], fill=(91, 75, 75))
    draw.rectangle([5, 5, 29, 19], fill=(15, 31, 57))
    draw.line([(17, 5), (17, 19)], fill=(70, 75, 91), width=2)
    draw.line([(5, 12), (29, 12)], fill=(70, 75, 91), width=2)

    # Raindrops travel in wrapped lanes, producing a clean seamless loop.
    for i, x in enumerate((7, 11, 15, 20, 24, 28)):
        y = 5 + ((frame * 2 + i * 4) % 13)
        draw.line([(x, y), (x - 1, min(18, y + 2))], fill=(76, 126, 170))
    draw.line([(6, 18), (13, 17), (19, 18), (28, 16)], fill=(41, 76, 112))

    # Lamp glow is stable; only the tiny flame breathes.
    draw.ellipse([30, 7, 58, 27], fill=(78, 53, 55))
    draw.ellipse([35, 10, 55, 25], fill=(118, 72, 52))
    draw.rectangle([45, 11, 47, 24], fill=(75, 48, 39))
    draw.polygon([(39, 12), (53, 12), (49, 6), (43, 6)], fill=(225, 151, 75))
    draw.line([(41, 11), (51, 11)], fill=(255, 203, 109))
    glow = round(math.sin(phase))
    draw.rectangle([45, 7 - glow, 47, 9], fill=(255, 220, 126))

    draw.rectangle([0, 23, 63, 31], fill=(63, 42, 38))
    draw.line([(0, 24), (63, 24)], fill=(91, 56, 44))
    draw.ellipse([22, 25, 55, 31], fill=(82, 51, 56))

    # Reading chair and open book form one large readable focal cluster.
    draw.ellipse([31, 18, 55, 30], fill=(133, 82, 63))
    draw.rectangle([34, 22, 53, 29], fill=(144, 91, 67))
    draw.rectangle([30, 26, 34, 31], fill=(91, 56, 50))
    draw.rectangle([52, 26, 56, 31], fill=(91, 56, 50))
    draw.polygon([(34, 23), (41, 21), (46, 23), (51, 21), (53, 24), (46, 26), (40, 24)], fill=(229, 205, 159))
    draw.line([(46, 23), (46, 26)], fill=(151, 112, 82))
    return image


FRAMES = [_make(frame) for frame in range(N)]
