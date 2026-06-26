import math

from PIL import Image

NAME = "Ripple Tiles"
COLLECTION = "Patterns"
FPS = 7
W, H, N = 64, 32, 28

PALETTE = (
    (8, 16, 37),
    (20, 48, 88),
    (28, 91, 125),
    (36, 145, 151),
    (80, 195, 160),
    (184, 219, 139),
    (244, 176, 91),
    (223, 82, 111),
)


def _make(frame):
    image = Image.new("RGB", (W, H))
    pixels = image.load()
    phase = math.tau * frame / N
    loop_offset = (len(PALETTE) * 2 - 2) * frame / N
    centers = ((8, 8), (24, 8), (40, 8), (56, 8), (16, 24), (32, 24), (48, 24))

    for y in range(H):
        for x in range(W):
            nearest = min(math.hypot(x - cx, y - cy) for cx, cy in centers)
            wave = nearest + 1.8 * math.sin((x + y) / 8 + phase)
            index = int((wave * 0.7 + loop_offset)) % (len(PALETTE) * 2 - 2)
            if index >= len(PALETTE):
                index = len(PALETTE) * 2 - 2 - index
            pixels[x, y] = PALETTE[index]
    return image


FRAMES = [_make(frame) for frame in range(N)]
