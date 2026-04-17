import random
from PIL import Image, ImageDraw

NAME = "Space"
FPS = 8

W, H = 64, 32

NEBULA_COLS = [
    (100,  40, 140),  # purple
    ( 40,  70, 160),  # blue
    (140,  35,  70),  # magenta-red
    ( 35, 110, 110),  # teal
]
PLANET_BODY   = (120,  85, 220)
PLANET_DARK   = ( 70,  50, 155)
PLANET_RING   = (180, 150, 235)
PLANET_SHADOW = ( 40,  25,  85)
STAR_BRIGHT   = (255, 255, 255)
STAR_MED      = (190, 200, 230)
STAR_DIM      = (100, 110, 145)
SHOOT_HEAD    = (255, 255, 220)
SHOOT_TAIL    = (200, 200, 160)

_rng = random.Random(5)

_STARS = []
for _ in range(70):
    x = _rng.randint(0, W - 1)
    y = _rng.randint(0, H - 1)
    b = _rng.choice([STAR_BRIGHT, STAR_BRIGHT, STAR_MED, STAR_DIM])
    _STARS.append((x, y, b))

# Nebula patches (x, y, radius, color_index)
_NEBULA = [
    ( 6, 24, 7, 0),
    ( 4, 27, 5, 2),
    (10, 25, 4, 3),
    (55,  5, 5, 1),
    (58,  8, 3, 0),
]

TOTAL_FRAMES = 64


def _draw_nebula(draw):
    for nx, ny, nr, ci in _NEBULA:
        c = NEBULA_COLS[ci]
        for dy in range(-nr, nr + 1):
            for dx in range(-nr, nr + 1):
                if dx * dx + dy * dy <= nr * nr:
                    px, py = nx + dx, ny + dy
                    if 0 <= px < W and 0 <= py < H:
                        dist = (dx * dx + dy * dy) ** 0.5
                        t = max(0.0, 1.0 - dist / nr) * 0.75
                        fc = tuple(int(c[i] * t) for i in range(3))
                        # Blend with existing pixel
                        draw.point((px, py), fill=fc)


def _draw_planet(draw, frame):
    px = (W + 14) - (frame // 3 % (W + 24))
    py = 10
    r = 7

    if px + r < 0 or px - r >= W:
        return

    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r:
                x, y = px + dx, py + dy
                if 0 <= x < W and 0 <= y < H:
                    if dx > 3:
                        c = PLANET_SHADOW
                    elif dx > 0:
                        c = PLANET_DARK
                    else:
                        c = PLANET_BODY
                    draw.point((x, y), fill=c)

    # Ring — two rows wide
    for dx in range(-r - 4, r + 5):
        x = px + dx
        if 0 <= x < W:
            if abs(dx) > r - 1:
                draw.point((x, py - 1), fill=PLANET_RING)
                draw.point((x, py + 1), fill=PLANET_RING)
            draw.point((x, py + 2), fill=PLANET_RING)


def _draw_shooting_star(draw, frame):
    cycle = frame % TOTAL_FRAMES
    if cycle > 20:
        return
    hx = W - 1 - cycle * 3
    hy = cycle
    for tail in range(6):
        tx, ty = hx + tail, hy - tail
        if 0 <= tx < W and 0 <= ty < H:
            c = SHOOT_HEAD if tail < 2 else SHOOT_TAIL
            draw.point((tx, ty), fill=c)
            if ty + 1 < H and tail < 3:
                draw.point((tx, ty + 1), fill=SHOOT_TAIL)


def _make_frame(frame):
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    _draw_nebula(draw)

    rng = random.Random(frame * 3)
    for sx, sy, base_c in _STARS:
        c = base_c if rng.random() < 0.88 else STAR_DIM
        draw.point((sx, sy), fill=c)

    _draw_planet(draw, frame)
    _draw_shooting_star(draw, frame)

    return img


FRAMES = [_make_frame(f) for f in range(TOTAL_FRAMES)]
