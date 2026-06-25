import math

from PIL import Image, ImageDraw

NAME = "Tea by Candle"
COLLECTION = "Cozy"
FPS = 6
W, H, N = 64, 32, 12


def _make(frame):
    image = Image.new("RGB", (W, H), (31, 18, 36))
    draw = ImageDraw.Draw(image)
    phase = math.tau * frame / N

    # Arched alcove with a restrained amber glow.
    draw.ellipse([3, -9, 61, 42], fill=(57, 31, 43))
    draw.ellipse([9, -4, 55, 35], fill=(77, 41, 43))
    draw.rectangle([0, 23, 63, 31], fill=(66, 38, 34))
    draw.line([(0, 24), (63, 24)], fill=(103, 58, 41))

    draw.rectangle([7, 4, 20, 21], fill=(70, 42, 39))
    for y in (9, 15, 21):
        draw.line([(7, y), (20, y)], fill=(119, 69, 45), width=2)
    for x, y, color in (
        (8, 6, (161, 73, 70)), (12, 6, (75, 111, 132)), (16, 6, (180, 131, 66)),
        (9, 12, (84, 132, 91)), (13, 12, (145, 83, 145)), (17, 12, (186, 104, 62)),
        (8, 18, (76, 123, 151)), (12, 18, (179, 84, 105)), (16, 18, (115, 137, 74)),
    ):
        draw.rectangle([x, y, x + 2, y + 3], fill=color)

    # Candle and tea set are deliberately oversized for the matrix.
    draw.ellipse([25, 8, 59, 29], fill=(94, 49, 40))
    draw.ellipse([31, 11, 55, 27], fill=(132, 67, 42))
    draw.rectangle([43, 10, 47, 23], fill=(232, 188, 112))
    flame_y = 6 - round(math.sin(phase))
    draw.polygon([(43, 10), (45, flame_y), (48, 10)], fill=(255, 126, 42))
    draw.point((45, flame_y + 1), fill=(255, 230, 121))

    draw.ellipse([24, 23, 57, 29], fill=(101, 58, 43))
    draw.rectangle([27, 20, 38, 25], fill=(184, 121, 79))
    draw.ellipse([27, 18, 38, 23], fill=(210, 151, 99))
    draw.ellipse([36, 20, 42, 25], outline=(205, 142, 91), width=2)
    draw.ellipse([45, 22, 54, 26], fill=(205, 164, 111))
    draw.ellipse([46, 22, 53, 24], fill=(88, 49, 38))

    # Steam drifts as coherent paired strokes.
    drift = round(2 * math.sin(phase))
    draw.line([(31, 18), (30 + drift, 15), (32 + drift, 12)], fill=(180, 153, 139))
    draw.line([(35, 18), (36 - drift, 15), (34 - drift, 13)], fill=(150, 127, 125))
    return image


FRAMES = [_make(frame) for frame in range(N)]
