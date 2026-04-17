import random
from PIL import Image, ImageDraw

NAME = "Space"
FPS = 8

W, H = 64, 32

NEBULA_COLORS = [
    (60,  20,  80),  # purple
    (20,  40,  80),  # deep blue
    (80,  20,  40),  # dark red
    (20,  60,  60),  # teal
]
PLANET_BODY   = (100,  70, 200)
PLANET_DARK   = ( 60,  40, 140)
PLANET_RING   = (160, 130, 220)
PLANET_SHADOW = ( 30,  20,  70)
STAR_BRIGHT   = (255, 255, 255)
STAR_MED      = (180, 190, 220)
STAR_DIM      = ( 90, 100, 130)
SHOOT_HEAD    = (255, 255, 200)
SHOOT_TAIL    = (180, 180, 140)

_rng = random.Random(5)

# Static star field
_STARS = []
for _ in range(55):
    x = _rng.randint(0, W - 1)
    y = _rng.randint(0, H - 1)
    b = _rng.choice([STAR_BRIGHT, STAR_MED, STAR_DIM])
    _STARS.append((x, y, b))

# Nebula patches (x, y, radius, color_index)
_NEBULA = [
    (5,  25, 6, 0),
    (3,  28, 4, 2),
    (8,  26, 3, 3),
]

TOTAL_FRAMES = 64   # shooting star period


def _draw_nebula(draw):
    for nx, ny, nr, ci in _NEBULA:
        c = NEBULA_COLORS[ci]
        for dy in range(-nr, nr + 1):
            for dx in range(-nr, nr + 1):
                if dx * dx + dy * dy <= nr * nr:
                    px, py = nx + dx, ny + dy
                    if 0 <= px < W and 0 <= py < H:
                        # Fade toward edges
                        dist = (dx * dx + dy * dy) ** 0.5
                        t = 1.0 - dist / nr
                        fc = tuple(int(c[i] * t * 0.6) for i in range(3))
                        draw.point((px, py), fill=fc)


def _draw_planet(draw, frame):
    # Planet drifts: starts at x=70 (off right edge), moves left 1px every 3 frames
    px = (W + 14) - (frame // 3 % (W + 24))
    py = 10
    r = 7

    if px + r < 0 or px - r >= W:
        return

    # Body
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r:
                x, y = px + dx, py + dy
                if 0 <= x < W and 0 <= y < H:
                    # Shadow on right side
                    c = PLANET_SHADOW if dx > 2 else (PLANET_DARK if dx > -1 else PLANET_BODY)
                    draw.point((x, y), fill=c)

    # Ring (horizontal ellipse, ±1 row)
    for dx in range(-r - 3, r + 4):
        x = px + dx
        if 0 <= x < W:
            draw.point((x, py + 1), fill=PLANET_RING)
        if 0 <= x < W and abs(dx) > r - 1:
            draw.point((x, py), fill=PLANET_RING)


def _draw_shooting_star(draw, frame):
    # Appears once per TOTAL_FRAMES cycle, travels diagonally
    cycle = frame % TOTAL_FRAMES
    if cycle > 18:
        return
    # Start top-right, move down-left
    hx = W - 1 - cycle * 3
    hy = cycle
    for tail in range(5):
        tx = hx + tail
        ty = hy - tail
        if 0 <= tx < W and 0 <= ty < H:
            c = SHOOT_HEAD if tail == 0 else SHOOT_TAIL
            draw.point((tx, ty), fill=c)


def _make_frame(frame):
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    _draw_nebula(draw)

    rng = random.Random(frame * 3)
    for sx, sy, base_c in _STARS:
        # Subtle twinkle
        c = base_c if rng.random() < 0.85 else STAR_DIM
        draw.point((sx, sy), fill=c)

    _draw_planet(draw, frame)
    _draw_shooting_star(draw, frame)

    return img


FRAMES = [_make_frame(f) for f in range(TOTAL_FRAMES)]
