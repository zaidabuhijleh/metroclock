import random
from PIL import Image, ImageDraw

NAME = "Forest"
FPS = 6

W, H = 64, 32

SKY_TOP      = (255, 112, 48)
SKY_MID      = (228, 72, 56)
SKY_BOTTOM   = (70, 18, 34)
SUN          = (255, 198, 92)
SUN_GLOW     = (255, 150, 70)
TREE_FILL    = (36, 150, 64)
TREE_DARK    = (18, 96, 44)
TRUNK        = (210, 120, 58)
BRANCH       = (232, 156, 78)
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
        if y < 10:
            t = y / 9
            color = (
                int(SKY_TOP[0] * (1 - t) + SKY_MID[0] * t),
                int(SKY_TOP[1] * (1 - t) + SKY_MID[1] * t),
                int(SKY_TOP[2] * (1 - t) + SKY_MID[2] * t),
            )
        else:
            t = (y - 10) / max(1, H - 11)
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
    for dx in (-2, -1, 2, 3):
        bx = tx + dx
        if 0 <= bx < W and 0 <= branch_y < H:
            draw.point((bx, branch_y), fill=BRANCH)


def _make_frame(frame):
    img = Image.new("RGB", (W, H), SKY_TOP)
    draw = ImageDraw.Draw(img)
    rng = random.Random(frame * 7)

    _draw_sky(draw)

    # Low sunset sun peeking between the trees.
    draw.ellipse([47, 5, 56, 14], fill=SUN)
    draw.ellipse([45, 7, 58, 16], outline=SUN_GLOW)

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
