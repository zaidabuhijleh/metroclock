import random
from PIL import Image, ImageDraw

NAME = "Forest"
FPS = 6

W, H = 64, 32

SKY        = (4,   8,  22)
STAR       = (200, 210, 255)
STAR_DIM   = (80,  90, 130)
TREE_DARK  = (10,  25,  10)
TREE_MID   = (15,  40,  15)
GROUND     = (20,  35,  10)
GRASS      = (30,  60,  20)
FIREFLY    = (220, 255, 120)
FIREFLY_DIM= (100, 160,  50)

_rng = random.Random(17)
_STARS = [(x, y) for x in range(W) for y in range(H - 14)
          if _rng.random() < 0.03]

# Pine trees: (tip_x, tip_y, half_base, layers)
_TREES = [
    (5,  10, 4, 4), (14, 12, 3, 3), (24,  8, 5, 5),
    (36, 11, 4, 4), (46,  9, 5, 5), (56, 13, 3, 3),
]

# Firefly positions: (x, y, phase_offset)
_rng2 = random.Random(55)
_FIREFLIES = [(_rng2.randint(2, W - 3), _rng2.randint(10, H - 8), _rng2.randint(0, 5))
              for _ in range(14)]


def _draw_tree(draw, tx, ty, hw, layers):
    for layer in range(layers):
        y = ty + layer * 3
        half = hw - layer + layer * (hw // layers)
        half = max(1, hw - layer)
        c = TREE_DARK if layer % 2 == 0 else TREE_MID
        for x in range(tx - half, tx + half + 1):
            if 0 <= x < W and 0 <= y < H:
                draw.point((x, y), fill=c)
            if y + 1 < H and abs(x - tx) <= half - 1:
                draw.point((x, y + 1), fill=c)
    # trunk
    for dy in range(3):
        ty2 = ty + layers * 3 + dy
        if 0 <= ty2 < H:
            draw.point((tx, ty2), fill=TREE_DARK)


def _make_frame(frame):
    img = Image.new("RGB", (W, H), SKY)
    draw = ImageDraw.Draw(img)

    rng = random.Random(frame * 7)

    # Stars — occasional twinkle
    for sx, sy in _STARS:
        c = STAR if rng.random() < 0.75 else STAR_DIM
        draw.point((sx, sy), fill=c)

    # Ground
    draw.rectangle([0, H - 6, W - 1, H - 1], fill=GROUND)
    for x in range(0, W, 3):
        h = rng.randint(1, 3)
        draw.line([(x, H - 6), (x, H - 6 - h)], fill=GRASS)

    # Trees
    for tx, ty, hw, layers in _TREES:
        _draw_tree(draw, tx, ty, hw, layers)

    # Fireflies — blink on/off, drift slightly each frame
    for fx, fy, phase in _FIREFLIES:
        visible = ((frame + phase) % 6) < 3
        if visible:
            bright = ((frame + phase) % 6) < 2
            c = FIREFLY if bright else FIREFLY_DIM
            drift_x = fx + ((frame + phase) % 3) - 1
            drift_y = fy + (((frame + phase) // 2) % 3) - 1
            if 0 <= drift_x < W and 0 <= drift_y < H:
                draw.point((drift_x, drift_y), fill=c)

    return img


FRAMES = [_make_frame(f) for f in range(6)]
