WIDTH = 21
HEIGHT = 32
PIXELS = WIDTH * HEIGHT

PALETTE = {
    0: (0, 0, 0),
    1: (255, 214, 74),
    2: (255, 163, 51),
    3: (245, 247, 255),
    4: (214, 214, 222),
    5: (82, 174, 255),
    6: (255, 245, 140),
    7: (176, 176, 186),
    8: (184, 197, 255),
    9: (156, 214, 214),
    10: (192, 248, 255),
    11: (165, 234, 255),
    12: (214, 196, 255),
}


def blank():
    return [0] * PIXELS


def set_px(grid, x, y, color):
    if 0 <= x < WIDTH and 0 <= y < HEIGHT:
        grid[y * WIDTH + x] = color


def set_px_if_empty(grid, x, y, color):
    if 0 <= x < WIDTH and 0 <= y < HEIGHT and grid[y * WIDTH + x] == 0:
        grid[y * WIDTH + x] = color


def draw_disc(grid, cx, cy, radius, color):
    radius_sq = radius * radius
    for y in range(cy - radius, cy + radius + 1):
        for x in range(cx - radius, cx + radius + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= radius_sq:
                set_px(grid, x, y, color)


def draw_line(grid, x1, y1, x2, y2, color):
    dx = abs(x2 - x1)
    dy = -abs(y2 - y1)
    sx = 1 if x1 < x2 else -1
    sy = 1 if y1 < y2 else -1
    err = dx + dy

    while True:
        set_px(grid, x1, y1, color)
        if x1 == x2 and y1 == y2:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x1 += sx
        if e2 <= dx:
            err += dx
            y1 += sy


def draw_cloud(grid, x_offset=0, y_offset=0, tint=3, shadow=4):
    lobes = [
        (6 + x_offset, 15 + y_offset, 4),
        (10 + x_offset, 12 + y_offset, 5),
        (15 + x_offset, 15 + y_offset, 4),
    ]
    for cx, cy, radius in lobes:
        draw_disc(grid, cx, cy, radius, tint)

    for y in range(15 + y_offset, 19 + y_offset):
        for x in range(4 + x_offset, 18 + x_offset):
            set_px(grid, x, y, tint)

    for y in range(17 + y_offset, 20 + y_offset):
        for x in range(5 + x_offset, 17 + x_offset):
            if grid[y * WIDTH + x] == tint:
                set_px(grid, x, y, shadow)


def draw_star(grid, x, y, bright, dim, twinkle):
    color = bright if twinkle else dim
    for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
        set_px(grid, x + dx, y + dy, color)


def draw_sun(grid, phase=0, x=7, y=10):
    draw_disc(grid, x, y, 5, 1)
    for px in range(x - 3, x + 1):
        for py in range(y - 4, y + 4):
            if 0 <= px < WIDTH and 0 <= py < HEIGHT and grid[py * WIDTH + px] == 1:
                set_px(grid, px, py, 2)

    short = 2 + (phase % 2)
    long = 4 + (phase % 2)
    rays = [
        ((x, y - 7), (x, y - 7 - short)),
        ((x, y + 7), (x, y + 7 + short)),
        ((x - 7, y), (x - 7 - short, y)),
        ((x + 7, y), (x + 7 + short, y)),
        ((x - 5, y - 5), (x - 5 - long, y - 5 - long)),
        ((x + 5, y - 5), (x + 5 + long, y - 5 - long)),
        ((x - 5, y + 5), (x - 5 - long, y + 5 + long)),
        ((x + 5, y + 5), (x + 5 + long, y + 5 + long)),
    ]
    for start, end in rays:
        draw_line(grid, start[0], start[1], end[0], end[1], 1)


def draw_moon(grid, twinkle=0, x=7, y=10):
    draw_disc(grid, x, y, 7, 8)
    draw_disc(grid, x + 3, y - 1, 5, 0)

    stars = [
        (1, 2, 6, 3, twinkle % 2 == 0),
        (15, 2, 6, 3, True),
        (19, 6, 6, 3, twinkle % 3 != 1),
        (17, 11, 6, 3, twinkle % 2 == 1),
        (18, 17, 6, 3, twinkle % 3 == 0),
        (15, 23, 6, 3, twinkle % 2 == 0),
        (19, 27, 6, 3, twinkle % 3 == 2),
        (9, 27, 6, 3, twinkle % 2 == 1),
    ]
    for sx, sy, bright, dim, state in stars:
        draw_star(grid, sx, sy, bright, dim, state)


def draw_rain(grid, offset=0, heavy=False):
    columns = [2, 5, 9, 13]
    if heavy:
        columns.extend([17])
    starts = [18, 20, 22, 21, 23]
    cycle = 10
    for i, x in enumerate(columns):
        y = starts[i] + (offset % cycle)
        if y < HEIGHT - 1:
            set_px_if_empty(grid, x, y, 5)
            if y + 1 < HEIGHT:
                set_px_if_empty(grid, x + 1, y + 1, 11)
        if heavy and y + 1 < HEIGHT:
            set_px_if_empty(grid, x, y + 1, 11)
            if y + 2 < HEIGHT:
                set_px_if_empty(grid, x + 1, y + 2, 5)


def draw_drizzle(grid, offset=0):
    columns = [6, 10, 14]
    for i, x in enumerate(columns):
        y = 20 + ((offset + i) % 4) * 2
        set_px_if_empty(grid, x, y, 9)


def draw_snow(grid, offset=0):
    flakes = [(6, 20), (10, 23), (14, 21), (8, 26), (12, 27)]
    for index, (x, y) in enumerate(flakes):
        py = y + ((offset + index) % 3) - 1
        for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
            set_px_if_empty(grid, x + dx, py + dy, 10)


def draw_fog(grid, offset=0):
    bands = [20, 24, 28]
    shift = offset % 3
    for row, y in enumerate(bands):
        start = 2 + ((row + shift) % 3)
        end = WIDTH - 3 - ((shift + row) % 2)
        for x in range(start, end):
            set_px(grid, x, y, 9 if (x + row) % 3 else 3)


def draw_haze(grid, offset=0):
    rows = [18, 22, 26]
    for row, y in enumerate(rows):
        start = 2 + ((offset + row) % 2)
        end = WIDTH - 3 - ((offset + row) % 2)
        for x in range(start, end):
            color = 6 if (x + row + offset) % 5 else 2
            set_px_if_empty(grid, x, y, color)


def draw_wind(grid, offset=0, color=11):
    rows = [13, 18, 23]
    for row, y in enumerate(rows):
        start = 3 + ((offset + row) % 4)
        end = WIDTH - 2 - ((offset + row) % 2)
        for x in range(start, end):
            if (x + row) % 5 != 0:
                set_px_if_empty(grid, x, y, color)
        set_px_if_empty(grid, end - 1, y - 1 + (row % 2), color)


def draw_lightning(grid, phase=0):
    if phase % 2 == 0:
        bolt = [(11, 18), (9, 22), (12, 22), (10, 27)]
    else:
        bolt = [(12, 18), (10, 21), (13, 21), (11, 27)]
    for start, end in zip(bolt, bolt[1:]):
        draw_line(grid, start[0], start[1], end[0], end[1], 6)


def draw_tornado(grid, phase=0):
    widths = [12, 10, 8, 6, 4, 2]
    wobble = [-1, 0, 1, 0][phase % 4]
    top_y = 7
    for i, span in enumerate(widths):
        y = top_y + i * 3
        center = 11 + wobble - (i // 3)
        for x in range(center - span // 2, center + span // 2 + 1):
            color = 4 if i < 2 else 7
            set_px(grid, x, y, color)
            if y + 1 < HEIGHT and i < len(widths) - 1:
                set_px(grid, x, y + 1, color)
    debris = [(4, 24), (6, 27), (14, 26), (17, 29)]
    for dx, dy in debris:
        set_px_if_empty(grid, dx + (phase % 2), dy, 2 if (dx + dy + phase) % 2 else 6)


def draw_smoke(grid, phase=0):
    puffs = [
        (7 + (phase % 2), 22, 3, 4),
        (11, 18 + (phase % 2), 4, 7),
        (14 - (phase % 2), 12, 3, 4),
    ]
    for cx, cy, radius, color in puffs:
        draw_disc(grid, cx, cy, radius, color)


def create_side_view_plane():
    grid = [
        0, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        0, 3, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        0, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 0,
        3, 3, 3, 3, 3, 4, 4, 4, 4, 3, 3, 3, 3, 3,
        0, 0, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 0, 0,
        0, 0, 0, 0, 0, 4, 4, 4, 4, 0, 0, 0, 0, 0,
    ]
    return grid


def frame_clear_day(phase):
    grid = blank()
    draw_sun(grid, phase, x=10, y=15)
    return grid


def frame_clear_night(phase):
    grid = blank()
    draw_moon(grid, phase, x=7, y=15)
    return grid


def frame_few_clouds_day(phase):
    grid = blank()
    draw_sun(grid, phase, x=7, y=11)
    draw_cloud(grid, x_offset=phase % 2, y_offset=6, tint=3, shadow=4)
    return grid


def frame_few_clouds_night(phase):
    grid = blank()
    draw_moon(grid, phase, x=7, y=11)
    draw_cloud(grid, x_offset=phase % 2, y_offset=6, tint=3, shadow=4)
    return grid


def frame_scattered_clouds(phase):
    grid = blank()
    draw_cloud(grid, x_offset=-2 + (phase % 2), y_offset=2, tint=4, shadow=7)
    draw_cloud(grid, x_offset=3 - (phase % 2), y_offset=8, tint=3, shadow=4)
    return grid


def frame_broken_clouds(phase):
    grid = blank()
    draw_cloud(grid, x_offset=-2, y_offset=1, tint=7, shadow=4)
    draw_cloud(grid, x_offset=2 + (phase % 2), y_offset=8, tint=3, shadow=4)
    return grid


def frame_overcast(phase):
    grid = blank()
    draw_cloud(grid, x_offset=-2 + (phase % 2), y_offset=1, tint=7, shadow=4)
    draw_cloud(grid, x_offset=1 - (phase % 2), y_offset=8, tint=4, shadow=7)
    return grid


def frame_drizzle(phase):
    grid = frame_overcast(phase)
    draw_drizzle(grid, phase)
    return grid


def frame_rain(phase):
    grid = blank()
    draw_cloud(grid, x_offset=-3, y_offset=-2, tint=7, shadow=4)
    draw_cloud(grid, x_offset=2 + (phase % 2), y_offset=4, tint=3, shadow=4)

    drops = [
        (2, 14), (6, 16), (10, 18), (14, 17),
        (5, 22), (9, 25), (13, 23),
    ]
    cycle = 10
    for index, (x, y) in enumerate(drops):
        py = y + ((phase + index) % cycle)
        set_px_if_empty(grid, x, py, 5)
        set_px_if_empty(grid, x + 1, py + 1, 11)

    return grid


def frame_shower_rain(phase):
    grid = blank()
    draw_cloud(grid, x_offset=-3 + (phase % 2), y_offset=-2, tint=7, shadow=4)
    draw_cloud(grid, x_offset=1, y_offset=3, tint=4, shadow=7)

    drops = [
        (2, 13), (5, 15), (9, 16), (13, 15), (17, 17),
        (4, 21), (8, 24), (12, 22), (16, 25),
    ]
    cycle = 10
    for index, (x, y) in enumerate(drops):
        py = y + ((phase + index) % cycle)
        set_px_if_empty(grid, x, py, 5)
        set_px_if_empty(grid, x + 1, py + 1, 11)
        if py + 2 < HEIGHT:
            set_px_if_empty(grid, x, py + 2, 11)

    return grid


def frame_thunderstorm(phase):
    grid = frame_overcast(phase)
    draw_rain(grid, phase, heavy=True)
    draw_lightning(grid, phase)
    return grid


def frame_snow(phase):
    grid = blank()
    draw_cloud(grid, x_offset=-3 + (phase % 2), y_offset=-4, tint=7, shadow=4)
    draw_cloud(grid, x_offset=2, y_offset=3, tint=3, shadow=4)

    flakes = [
        (2, 8), (6, 10), (10, 12), (14, 11),
        (5, 16), (9, 19), (13, 17),
        (7, 22), (12, 24),
    ]
    cycle = 10
    for index, (x, y) in enumerate(flakes):
        py = y + ((phase + index) % cycle)
        for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
            set_px_if_empty(grid, x + dx, py + dy, 10)

    return grid


def frame_mist(phase):
    grid = blank()
    draw_cloud(grid, x_offset=0, y_offset=1, tint=3, shadow=4)
    draw_fog(grid, phase)
    return grid


def frame_haze(phase):
    grid = blank()
    draw_sun(grid, phase, x=7, y=11)
    draw_haze(grid, phase)
    return grid


def frame_dust(phase):
    grid = blank()
    rows = [10, 16, 22]
    for row, y in enumerate(rows):
        start = 1 + ((phase + row) % 2)
        for x in range(start, WIDTH - 2):
            if x % 4 != row % 3:
                set_px_if_empty(grid, x, y, 6)
    for x, y in ((4, 8), (8, 12), (12, 18), (16, 24), (10, 27)):
        set_px_if_empty(grid, x + (phase % 2), y, 2)
    return grid


def frame_squall(phase):
    grid = blank()
    draw_cloud(grid, x_offset=0, y_offset=1, tint=7, shadow=4)
    draw_wind(grid, phase, color=11)
    draw_rain(grid, phase, heavy=False)
    return grid


def frame_tornado(phase):
    grid = blank()
    draw_tornado(grid, phase)
    return grid


def frame_smoke(phase):
    grid = blank()
    draw_smoke(grid, phase)
    return grid


def build_frames(builder, count):
    return [builder(index) for index in range(count)]


SIDE_PLANE = create_side_view_plane()

ANIMATIONS = {
    "clear_day": build_frames(frame_clear_day, 2),
    "clear_night": build_frames(frame_clear_night, 2),
    "few_clouds_day": build_frames(frame_few_clouds_day, 2),
    "few_clouds_night": build_frames(frame_few_clouds_night, 2),
    "scattered_clouds": build_frames(frame_scattered_clouds, 2),
    "broken_clouds": build_frames(frame_broken_clouds, 2),
    "overcast": build_frames(frame_overcast, 2),
    "drizzle": build_frames(frame_drizzle, 3),
    "rain": build_frames(frame_rain, 10),
    "shower_rain": build_frames(frame_shower_rain, 10),
    "thunderstorm": build_frames(frame_thunderstorm, 3),
    "snow": build_frames(frame_snow, 10),
    "mist": build_frames(frame_mist, 2),
    "haze": build_frames(frame_haze, 2),
    "dust": build_frames(frame_dust, 3),
    "squall": build_frames(frame_squall, 3),
    "tornado": build_frames(frame_tornado, 4),
    "smoke": build_frames(frame_smoke, 2),
    "Clear": build_frames(frame_clear_day, 2),
    "Clouds": build_frames(frame_overcast, 2),
    "Rain": build_frames(frame_rain, 10),
    "Drizzle": build_frames(frame_drizzle, 3),
    "Thunderstorm": build_frames(frame_thunderstorm, 3),
    "Snow": build_frames(frame_snow, 10),
    "Mist": build_frames(frame_mist, 2),
    "Haze": build_frames(frame_haze, 2),
    "Dust": build_frames(frame_dust, 3),
    "Fog": build_frames(frame_mist, 2),
    "Smoke": build_frames(frame_smoke, 2),
    "Ash": build_frames(frame_smoke, 2),
    "Sand": build_frames(frame_dust, 3),
    "Squall": build_frames(frame_squall, 3),
    "Tornado": build_frames(frame_tornado, 4),
    "SidePlane": [SIDE_PLANE],
}


def get_frame(condition, frame_index):
    frames = ANIMATIONS.get(condition, ANIMATIONS["clear_day"])
    current_frame = frames[frame_index % len(frames)]
    return current_frame, PALETTE
