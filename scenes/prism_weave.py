import math

from PIL import Image, ImageDraw

NAME = "Prism Weave"
COLLECTION = "Patterns"
FPS = 7
W, H, N = 64, 32, 16

PALETTE = (
    (10, 13, 35),
    (35, 49, 103),
    (50, 112, 155),
    (54, 180, 172),
    (132, 211, 154),
    (239, 181, 90),
    (230, 83, 123),
    (137, 60, 153),
)


def _make(frame):
    image = Image.new("RGB", (W, H), PALETTE[0])
    draw = ImageDraw.Draw(image)
    phase = math.tau * frame / N

    # Two broad woven ribbons cross without small noisy detail.
    for band in range(7, 0, -1):
        color = PALETTE[band]
        upper = []
        lower = []
        for x in range(W):
            y1 = 9 + 6 * math.sin(x / 9 + phase)
            y2 = 22 + 6 * math.sin(x / 9 + phase + math.pi)
            upper.append((x, round(y1 + (band - 4) * 0.75)))
            lower.append((x, round(y2 + (band - 4) * 0.75)))
        draw.line(upper, fill=color, width=2)
        draw.line(lower, fill=color, width=2)

    # Dark over-under masks establish the weave rhythm.
    offset = round(8 * (0.5 + 0.5 * math.sin(phase)))
    for x in range(-16 + offset, W + 16, 24):
        draw.rectangle([x, 13, x + 8, 18], fill=PALETTE[0])
        draw.line([(x, 13), (x + 8, 18)], fill=PALETTE[2], width=2)
    return image


FRAMES = [_make(frame) for frame in range(N)]
