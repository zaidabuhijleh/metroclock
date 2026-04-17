import random
from PIL import Image, ImageDraw

NAME = "Forest"
FPS = 6

W, H = 64, 32

SKY        = (  2,   5,  18)
STAR       = (215, 225, 255)
STAR_DIM   = ( 90, 100, 145)
TREE_FILL  = (  0, 200,  50)   # bright green — visible at low brightness
TREE_DARK  = (  0, 130,  30)   # darker green for layer depth
GROUND     = ( 25,  60,  18)
GRASS      = ( 55, 135,  35)
FIREFLY    = (235, 255, 110)
FIREFLY_DIM= (125, 180,  55)

_rng = random.Random(17)
_STARS = [(x, y) for x in range(W) for y in range(H - 16)
          if _rng.random() < 0.035]

# Pine trees: (tip_x, tip_y, half_base, layers)
_TREES = [
    ( 5, 10, 4, 4), (16, 13, 3, 3), (26,  8, 5, 5),
    (38, 11, 4, 4), (48,  9, 5, 5), (58, 13, 3, 3),
]

_rng2 = random.Random(55)
_FIREFLIES = [(_rng2.randint(3, W - 4), _rng2.randint(10, H - 9), _rng2.randint(0, 5))
              for _ in range(16)]


def _draw_tree(draw, tx, ty, hw, layers):
    # Narrow at tip (top), wide at base (bottom) — correct pine tree shape
    for layer in range(layers):
        y = ty + layer * 3
        half = max(1, 1 + layer * (hw - 1) // max(1, layers - 1))
        c = TREE_FILL if layer % 2 == 0 else TREE_DARK
        for x in range(tx - half, tx + half + 1):
            if 0 <= x < W and 0 <= y < H:
                draw.point((x, y), fill=c)
            if y + 1 < H and 0 <= x < W:
                draw.point((x, y + 1), fill=c)
    # Trunk
    for dy in range(3):
        ty2 = ty + layers * 3 + dy
        if 0 <= ty2 < H:
            draw.point((tx, ty2), fill=TREE_DARK)
            if tx + 1 < W:
                draw.point((tx + 1, ty2), fill=TREE_DARK)


def _make_frame(frame):
    img = Image.new("RGB", (W, H), SKY)
    draw = ImageDraw.Draw(img)
    rng = random.Random(frame * 7)

    for sx, sy in _STARS:
        c = STAR if rng.random() < 0.75 else STAR_DIM
        draw.point((sx, sy), fill=c)

    draw.rectangle([0, H - 7, W - 1, H - 1], fill=GROUND)
    for x in range(0, W, 3):
        h = rng.randint(1, 3)
        draw.line([(x, H - 7), (x, H - 7 - h)], fill=GRASS)

    for tx, ty, hw, layers in _TREES:
        _draw_tree(draw, tx, ty, hw, layers)

    for fx, fy, phase in _FIREFLIES:
        visible = ((frame + phase) % 6) < 3
        if visible:
            bright = ((frame + phase) % 6) < 2
            c = FIREFLY if bright else FIREFLY_DIM
            drift_x = fx + ((frame + phase) % 3) - 1
            drift_y = fy + (((frame + phase) // 2) % 3) - 1
            if 0 <= drift_x < W and 0 <= drift_y < H:
                draw.point((drift_x, drift_y), fill=c)
                if drift_x + 1 < W:
                    draw.point((drift_x + 1, drift_y), fill=FIREFLY_DIM)

    return img


FRAMES = [_make_frame(f) for f in range(6)]
