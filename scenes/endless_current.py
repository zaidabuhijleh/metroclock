import math

from PIL import Image

NAME = "Endless Current"
COLLECTION = "Flow"
FPS = 8
PREVIEW_FRAMES = 48

W, H = 64, 32
PALETTE = (
    (4, 17, 38),
    (6, 35, 61),
    (7, 66, 82),
    (10, 105, 96),
    (20, 145, 116),
    (61, 190, 145),
    (128, 226, 178),
    (211, 248, 212),
)


def _palette_index(value):
    value = 0.5 + 0.5 * math.tanh(value)
    return max(0, min(len(PALETTE) - 1, int(value * len(PALETTE))))


def render_frame(tick):
    t = tick / FPS
    image = Image.new("RGB", (W, H))
    pixels = image.load()

    for y in range(H):
        ny = (y - H / 2) / H
        for x in range(W):
            nx = (x - W / 2) / W

            # Slow domain warp. The time terms are intentionally non-looping,
            # so the panel can drift indefinitely instead of returning to a
            # fixed start pose.
            wx = nx + 0.18 * math.sin(5.2 * ny + t * 0.31) + 0.08 * math.sin(11 * ny - t * 0.17)
            wy = ny + 0.16 * math.sin(4.7 * nx - t * 0.23) + 0.07 * math.cos(9 * nx + t * 0.19)

            eddy_a = math.sin(9.0 * (wx + 0.22 * math.sin(3 * wy + t * 0.13)) + t * 0.37)
            eddy_b = math.cos(8.5 * (wy + 0.18 * math.sin(4 * wx - t * 0.11)) - t * 0.29)
            ribbon = math.sin(14 * (wx - wy) + 0.35 * math.sin(t * 0.07) + t * 0.21)
            glow = 0.32 / (0.045 + (wx - 0.24 * math.sin(t * 0.09)) ** 2 + (wy + 0.18 * math.cos(t * 0.12)) ** 2)

            value = 0.86 * eddy_a + 0.64 * eddy_b + 0.34 * ribbon + 0.10 * glow - 0.55
            pixels[x, y] = PALETTE[_palette_index(value)]

    return image
