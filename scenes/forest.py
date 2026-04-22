import random
from PIL import Image, ImageDraw

NAME = "Forest"
FPS = 6

W, H = 64, 32

BLACK = (0, 0, 0)
NIGHT_BLUE = (0, 0, 85)
PURPLE = (85, 0, 85)
SUN = (255, 170, 0)
SUN_CORE = (255, 255, 85)
TREE = (0, 170, 0)
TREE_DARK = (0, 85, 0)
TRUNK = (255, 170, 0)
BRANCH = (255, 255, 85)
GROUND = (0, 85, 0)
GRASS = (85, 170, 0)
FIREFLY = (255, 255, 85)
FIREFLY_DIM = (170, 170, 0)

_TREES = [
    (5, 22, 5, 4), (16, 24, 4, 3), (26, 22, 6, 5),
    (38, 23, 5, 4), (49, 22, 6, 5), (59, 24, 4, 3),
]

_rng = random.Random(55)
_FIREFLIES = [(_rng.randint(3, W - 4), _rng.randint(13, H - 8), _rng.randint(0, 5)) for _ in range(8)]


def _draw_sky(draw):
    # Sparse sunset bands read better than a solid red/orange wash through the diffuser.
    for y in range(0, 13, 3):
        draw.line([(0, y), (W - 1, y)], fill=NIGHT_BLUE)
    for y in range(13, 22, 3):
        draw.line([(0, y), (W - 1, y)], fill=PURPLE)
    draw.line([(0, 22), (W - 1, 22)], fill=SUN)
    draw.line([(0, 23), (W - 1, 23)], fill=SUN)


def _draw_tree(draw, tx, base_y, half_base, layers):
    # Draw trunk/branches first, then leave bright highlights visible through foliage gaps.
    draw.line([(tx, base_y - layers * 3), (tx, base_y + 2)], fill=TRUNK)
    if tx + 1 < W:
        draw.line([(tx + 1, base_y - layers * 3 + 2), (tx + 1, base_y + 2)], fill=TRUNK)

    for by in (base_y - 8, base_y - 5, base_y - 2):
        draw.line([(tx - 3, by), (tx + 3, by - 1)], fill=BRANCH)
        draw.line([(tx - 2, by - 2), (tx + 4, by)], fill=BRANCH)

    for layer in range(layers):
        y = base_y - (layers - layer) * 3
        half = max(1, 1 + layer * (half_base - 1) // max(1, layers - 1))
        color = TREE if layer % 2 == 0 else TREE_DARK
        for x in range(tx - half, tx + half + 1):
            if 0 <= x < W:
                draw.point((x, y), fill=color)
                if y + 1 < H:
                    draw.point((x, y + 1), fill=color)
        # Repaint small branch tips over the foliage so the scene reads as trees.
        if layer >= 1:
            draw.point((tx - half, y + 1), fill=BRANCH)
            draw.point((tx + half, y + 1), fill=BRANCH)


def _make_frame(frame):
    img = Image.new("RGB", (W, H), BLACK)
    draw = ImageDraw.Draw(img)
    rng = random.Random(frame * 7)

    _draw_sky(draw)

    draw.ellipse([47, 10, 57, 20], fill=SUN)
    draw.ellipse([50, 12, 55, 17], fill=SUN_CORE)

    draw.rectangle([0, H - 6, W - 1, H - 1], fill=GROUND)
    for x in range(0, W, 3):
        h = rng.randint(1, 3)
        draw.line([(x, H - 6), (x, H - 6 - h)], fill=GRASS)

    for tree in _TREES:
        _draw_tree(draw, *tree)

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
