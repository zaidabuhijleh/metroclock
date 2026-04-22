import random
from PIL import Image, ImageDraw

NAME = "Forest"
FPS = 6

W, H = 64, 32

SKY_TOP      = (22, 34, 82)
SKY_MID      = (128, 58, 86)
SKY_BOTTOM   = (245, 132, 54)
SUN          = (255, 214, 104)
SUN_GLOW     = (255, 166, 74)
TREE_FILL    = (18, 118, 52)
TREE_DARK    = (8, 70, 34)
TRUNK        = (255, 168, 76)
BRANCH       = (255, 210, 116)
GROUND       = (32, 54, 22)
GRASS        = (72, 132, 44)
FIREFLY      = (235, 255, 110)
FIREFLY_DIM  = (125, 180, 55)

_TREES = [
    (5, 9, 4, 4), (16, 12, 3, 3), (26, 7, 5, 5),
    (38, 10, 4, 4), (48, 8, 5, 5), (58, 12, 3, 3),
]

_rng = random.Random(55)
_FIREFLIES = [(_rng.randint(3, W - 4), _rng.randint(12, H - 8), _rng.randint(0, 5)) for _ in range(10)]


def _draw_sky(draw):
    for y in range(H):
        if y < 14:
            t = y / 13
            color = (
                int(SKY_TOP[0] * (1 - t) + SKY_MID[0] * t),
                int(SKY_TOP[1] * (1 - t) + SKY_MID[1] * t),
                int(SKY_TOP[2] * (1 - t) + SKY_MID[2] * t),
            )
        else:
            t = (y - 14) / max(1, H - 15)
            color = (
                int(SKY_MID[0] * (1 - t) + SKY_BOTTOM[0] * t),
                int(SKY_MID[1] * (1 - t) + SKY_BOTTOM[1] * t),
                int(SKY_MID[2] * (1 - t) + SKY_BOTTOM[2] * t),
            )
        draw.line([(0, y), (W - 1, y)], fill=color)


def _draw_tree(draw, tx, ty, hw, layers):
    for layer in range(layers):
        y = ty + layer * 3
        half = max(1, 1 + layer * (hw - 1) // max(1, layers - 1))
        fill = TREE_FILL if layer % 2 == 0 else TREE_DARK
        for x in range(tx - half, tx + half + 1):
            if 0 <= x < W and 0 <= y < H:
                draw.point((x, y), fill=fill)
            if y + 1 < H and 0 <= x < W:
                draw.point((x, y + 1), fill=fill)

    trunk_top = ty + layers * 3 - 1
    for dy in range(4):
        y = trunk_top + dy
        if 0 <= y < H:
            draw.point((tx, y), fill=TRUNK)
            if tx + 1 < W:
                draw.point((tx + 1, y), fill=TRUNK)

    branch_y = trunk_top + 1
    for dx in (-3, -2, -1, 2, 3, 4):
        bx = tx + dx
        if 0 <= bx < W and 0 <= branch_y < H:
            draw.point((bx, branch_y), fill=BRANCH)
            if abs(dx) <= 3 and branch_y - 1 >= 0:
                draw.point((bx, branch_y - 1), fill=TRUNK)


def _make_frame(frame):
    img = Image.new("RGB", (W, H), SKY_TOP)
    draw = ImageDraw.Draw(img)
    rng = random.Random(frame * 7)

    _draw_sky(draw)

    # Low sunset sun peeking between the trees.
    draw.ellipse([47, 9, 57, 19], fill=SUN)
    draw.ellipse([45, 11, 59, 21], outline=SUN_GLOW)

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
            color = FIREFLY if bright else FIREFLY_DIM
            drift_x = fx + ((frame + phase) % 3) - 1
            drift_y = fy + (((frame + phase) // 2) % 3) - 1
            if 0 <= drift_x < W and 0 <= drift_y < H:
                draw.point((drift_x, drift_y), fill=color)
                if drift_x + 1 < W:
                    draw.point((drift_x + 1, drift_y), fill=FIREFLY_DIM)

    return img


FRAMES = [_make_frame(frame) for frame in range(6)]
