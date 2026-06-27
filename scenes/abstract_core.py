import math

from PIL import Image, ImageDraw


W, H = 64, 32


def _quantize(value, steps):
    return max(0, min(steps - 1, int(value * steps)))


def _field_frame(palette, frame, count, field, bands=None):
    phase = math.tau * frame / count
    return _field_image(palette, phase, field, bands)


def _field_image(palette, phase, field, bands=None):
    image = Image.new("RGB", (W, H))
    pixels = image.load()
    for y in range(H):
        ny = (y - H / 2) / H
        for x in range(W):
            nx = (x - W / 2) / W
            value = field(nx, ny, phase)
            value = 0.5 + 0.5 * math.tanh(value)
            index = _quantize(value, bands or len(palette))
            index = round(index * (len(palette) - 1) / max(1, (bands or len(palette)) - 1))
            pixels[x, y] = palette[index]
    return image


def _triangle_palette_index(value, palette_len):
    cycle = palette_len * 2 - 2
    index = int(value) % cycle
    if index >= palette_len:
        index = cycle - index
    return index


def render_thermal_frame(tick, fps=8):
    palette = [
        (16, 18, 58), (31, 39, 112), (68, 42, 142), (132, 43, 135),
        (201, 54, 82), (244, 91, 44), (255, 157, 48), (255, 226, 91),
    ]
    t = tick / fps

    def field(x, y, _phase):
        centers = [
            (-0.25 + 0.13 * math.cos(t * 0.43), -0.08 + 0.13 * math.sin(t * 0.31), 0.12),
            (0.22 + 0.10 * math.cos(t * 0.29 + 2.1), 0.10 + 0.16 * math.sin(t * 0.37 + 1.3), 0.10),
            (0.02 + 0.17 * math.cos(t * 0.23 + 4.0), -0.27 + 0.08 * math.sin(t * 0.41 + 2.8), 0.075),
        ]
        heat = -1.25
        for cx, cy, radius in centers:
            heat += radius / (0.018 + (x - cx) ** 2 + (y - cy) ** 2)
        heat += 0.35 * math.sin(10 * x + 2 * math.sin(5 * y - t * 0.52))
        heat += 0.12 * math.cos(7 * (x - y) + t * 0.19)
        return heat * 0.42 - 1.45

    return _field_image(palette, t, field, 9)


def render_liquid_frame(tick, fps=8):
    palette = [
        (13, 13, 42), (31, 27, 89), (67, 41, 143), (117, 48, 167),
        (188, 57, 153), (240, 82, 123), (255, 132, 101), (255, 195, 137),
    ]
    t = tick / fps

    def field(x, y, _phase):
        fold = y + 0.18 * math.sin(8 * x + t * 0.56) + 0.10 * math.sin(15 * x - t * 0.91)
        curl = x + 0.14 * math.sin(9 * y - t * 0.47)
        tide = x + y + 0.08 * math.sin(4 * (x - y) + t * 0.17)
        return (
            0.95 * math.sin(9 * fold + t * 0.49)
            + 0.55 * math.sin(7 * curl - t * 0.38)
            + 0.35 * math.cos(15 * tide + t * 0.67)
        )

    return _field_image(palette, t, field, 8)


def render_oil_frame(tick, fps=8):
    palette = [
        (8, 12, 29), (18, 47, 70), (18, 100, 103), (32, 161, 137),
        (92, 196, 151), (68, 116, 190), (99, 68, 174), (183, 67, 160),
        (235, 108, 107), (239, 174, 91),
    ]
    t = tick / fps

    def field(x, y, _phase):
        warped_x = x + 0.18 * math.sin(4 * y + t * 0.32)
        warped_y = y + 0.14 * math.sin(4 * x - t * 0.27)
        radius = math.hypot(warped_x * 1.25, warped_y * 1.8)
        angle = math.atan2(warped_y, warped_x)
        return math.sin(7 * radius - angle - t * 0.42) + 0.22 * math.sin(4 * x + 3 * y + t * 0.19)

    return _field_image(palette, t, field, 6)


def render_lava_frame(tick, fps=8):
    bg = (13, 8, 29)
    palettes = [
        ((105, 26, 87), (201, 48, 80), (255, 112, 49), (255, 190, 77)),
        ((54, 35, 114), (112, 43, 151), (219, 53, 116), (255, 128, 63)),
        ((45, 36, 98), (128, 36, 119), (236, 70, 85), (255, 167, 72)),
    ]
    t = tick / fps
    image = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(image)
    for i, colors in enumerate(palettes):
        cx = [15, 34, 51][i] + round(5 * math.sin(t * [0.24, 0.19, 0.31][i] + i * 2.1))
        cy = [9, 22, 12][i] + round(6 * math.cos(t * [0.17, 0.27, 0.21][i] + i * 1.7))
        rx = [10, 12, 9][i] + round(2 * math.sin(t * [0.41, 0.33, 0.37][i] + i))
        ry = [7, 8, 10][i] + round(2 * math.cos(t * [0.35, 0.29, 0.43][i] + i))
        for inset, color in zip((0, 2, 4, 6), colors):
            if rx - inset > 0 and ry - inset > 0:
                draw.ellipse(
                    [cx - rx + inset, cy - ry + inset, cx + rx - inset, cy + ry - inset],
                    fill=color,
                )
    return image


def render_aurora_frame(tick, fps=8):
    palette = [
        (5, 18, 45), (7, 39, 69), (8, 75, 91), (12, 118, 107),
        (28, 159, 126), (75, 203, 153), (136, 231, 188), (205, 248, 217),
    ]
    t = tick / fps

    def field(x, y, _phase):
        fold = y + 0.20 * math.sin(8 * x + t * 0.41) + 0.12 * math.sin(14 * x - t * 0.63)
        curl = x + 0.16 * math.sin(9 * y - t * 0.29)
        tide = x - y + 0.10 * math.sin(5 * (x + y) + t * 0.21)
        return (
            1.05 * math.sin(9 * fold + t * 0.37)
            + 0.62 * math.sin(7 * curl - t * 0.34)
            + 0.38 * math.cos(13 * tide + t * 0.52)
        )

    return _field_image(palette, t, field, 8)


def render_kelp_current_frame(tick, fps=8):
    palette = [
        (5, 21, 38), (8, 46, 62), (8, 82, 83), (12, 123, 103),
        (31, 166, 120), (87, 205, 151), (159, 231, 184), (217, 247, 207),
    ]
    t = tick / fps

    def field(x, y, _phase):
        sweep = x + 0.22 * math.sin(5.5 * y + t * 0.36) + 0.08 * math.sin(13 * y - t * 0.22)
        tide = y + 0.18 * math.sin(6 * x - t * 0.27)
        eddy = math.sin(
            10 * math.hypot(x + 0.12 * math.cos(t * 0.18), y - 0.05 * math.sin(t * 0.24))
            - t * 0.39
        )
        return 1.05 * math.sin(8.5 * sweep + t * 0.31) + 0.62 * math.cos(7 * tide - t * 0.28) + 0.35 * eddy

    return _field_image(palette, t, field, 7)


def render_coral_mist_frame(tick, fps=8):
    palette = [
        (31, 18, 58), (73, 33, 91), (130, 46, 113), (195, 63, 118),
        (239, 96, 101), (255, 143, 91), (255, 190, 126), (126, 90, 177),
    ]
    t = tick / fps
    image = Image.new("RGB", (W, H), palette[0])
    pixels = image.load()
    for y in range(H):
        for x in range(W):
            nx = (x - W / 2) / W
            ny = (y - H / 2) / H
            fold = (
                0.9 * math.sin(7.5 * (nx + 0.16 * math.sin(5 * ny + t * 0.31)) + t * 0.42)
                + 0.7 * math.cos(9 * (ny + 0.11 * math.sin(4 * nx - t * 0.27)) - t * 0.34)
                + 0.35 * math.sin(17 * (nx - ny) + t * 0.51)
            )
            lift = 0.48 + 0.5 * math.tanh(fold)
            index = max(0, min(6, int(lift * 7)))
            pixels[x, y] = palette[index]
    return image


def render_sea_glass_frame(tick, fps=8):
    palette = [
        (7, 24, 42), (10, 52, 73), (12, 91, 100), (18, 132, 122),
        (54, 174, 145), (112, 213, 174), (187, 238, 204), (54, 106, 165),
    ]
    t = tick / fps
    image = Image.new("RGB", (W, H))
    pixels = image.load()
    for y in range(H):
        for x in range(W):
            cell_x = x // 12
            cell_y = y // 8
            lx = (x % 12) - 5.5
            ly = (y % 8) - 3.5
            dist = abs(lx * 0.78) + abs(ly)
            wave = (
                dist
                + 2.2 * math.sin((cell_x + cell_y) * 0.9 + t * 0.33)
                + 1.1 * math.sin((x - y) / 12 - t * 0.29)
            )
            index = _triangle_palette_index(wave + t * 1.4, len(palette))
            pixels[x, y] = palette[index]

    draw = ImageDraw.Draw(image)
    for x in range(0, W, 12):
        draw.line([(x, 0), (x, H - 1)], fill=palette[1])
    for y in range(0, H, 8):
        draw.line([(0, y), (W - 1, y)], fill=palette[1])
    return image


def render_ember_bloom_frame(tick, fps=8):
    palette = [
        (35, 16, 52), (82, 31, 88), (142, 44, 102), (207, 64, 101),
        (246, 101, 83), (255, 151, 83), (255, 208, 117), (103, 63, 150),
    ]
    t = tick / fps
    centers = ((16, 9), (44, 8), (30, 22), (57, 24), (6, 25))
    image = Image.new("RGB", (W, H), palette[0])
    pixels = image.load()
    for y in range(H):
        for x in range(W):
            value = 0.0
            for i, (cx, cy) in enumerate(centers):
                dx = x - (cx + 2 * math.sin(t * (0.21 + i * 0.03) + i))
                dy = y - (cy + 2 * math.cos(t * (0.17 + i * 0.04) + i * 1.4))
                radius = math.hypot(dx * 0.9, dy * 1.25)
                angle = math.atan2(dy, dx)
                value += math.sin(radius * 0.55 - t * 0.36 + i) + 0.55 * math.cos(6 * angle + t * 0.28)
            value = 0.5 + 0.5 * math.tanh(value * 0.28)
            index = max(0, min(6, int(value * 7)))
            pixels[x, y] = palette[index]
    return image


def render_contour_frame(tick, fps=8):
    palette = [
        (14, 18, 48), (37, 37, 83), (74, 46, 105), (116, 52, 112),
        (162, 61, 105), (207, 83, 91), (239, 126, 78), (250, 183, 91),
    ]
    t = tick / fps
    image = Image.new("RGB", (W, H), palette[0])
    pixels = image.load()
    for y in range(H):
        for x in range(W):
            dx = x - (31 + 8 * math.cos(t * 0.23))
            dy = (y - (16 + 5 * math.sin(t * 0.19))) * 1.55
            radius = math.hypot(dx, dy)
            radius += 4 * math.sin(x / 8 + t * 0.31) + 2 * math.sin(y / 3 - t * 0.27)
            pixels[x, y] = palette[_triangle_palette_index(radius / 4.2 + t * 0.55, len(palette))]
    return image


def thermal_frames(count=12):
    palette = [
        (16, 18, 58), (31, 39, 112), (68, 42, 142), (132, 43, 135),
        (201, 54, 82), (244, 91, 44), (255, 157, 48), (255, 226, 91),
    ]

    def field(x, y, p):
        centers = [
            (-0.25 + 0.13 * math.cos(p), -0.08 + 0.13 * math.sin(p), 0.12),
            (0.22 + 0.10 * math.cos(p + 2.1), 0.10 + 0.16 * math.sin(p + 1.3), 0.10),
            (0.02 + 0.17 * math.cos(p + 4.0), -0.27 + 0.08 * math.sin(p + 2.8), 0.075),
        ]
        heat = -1.25
        for cx, cy, radius in centers:
            heat += radius / (0.018 + (x - cx) ** 2 + (y - cy) ** 2)
        heat += 0.35 * math.sin(10 * x + 2 * math.sin(5 * y - p))
        return heat * 0.42 - 1.45

    return [_field_frame(palette, f, count, field, 9) for f in range(count)]


def liquid_frames(count=12):
    palette = [
        (13, 13, 42), (31, 27, 89), (67, 41, 143), (117, 48, 167),
        (188, 57, 153), (240, 82, 123), (255, 132, 101), (255, 195, 137),
    ]

    def field(x, y, p):
        fold = y + 0.18 * math.sin(8 * x + p) + 0.10 * math.sin(15 * x - 2 * p)
        curl = x + 0.14 * math.sin(9 * y - p)
        return (
            0.95 * math.sin(9 * fold + p)
            + 0.55 * math.sin(7 * curl - p)
            + 0.35 * math.cos(15 * (x + y) + 2 * p)
        )

    return [_field_frame(palette, f, count, field, 8) for f in range(count)]


def oil_frames(count=12):
    palette = [
        (8, 12, 29), (18, 47, 70), (18, 100, 103), (32, 161, 137),
        (92, 196, 151), (68, 116, 190), (99, 68, 174), (183, 67, 160),
        (235, 108, 107), (239, 174, 91),
    ]

    def field(x, y, p):
        warped_x = x + 0.18 * math.sin(4 * y + p)
        warped_y = y + 0.14 * math.sin(4 * x - p)
        radius = math.hypot(warped_x * 1.25, warped_y * 1.8)
        angle = math.atan2(warped_y, warped_x)
        return math.sin(7 * radius - angle - p) + 0.22 * math.sin(4 * x + 3 * y + p)

    return [_field_frame(palette, f, count, field, 6) for f in range(count)]


def lava_frames(count=12):
    bg = (13, 8, 29)
    palettes = [
        ((105, 26, 87), (201, 48, 80), (255, 112, 49), (255, 190, 77)),
        ((54, 35, 114), (112, 43, 151), (219, 53, 116), (255, 128, 63)),
        ((45, 36, 98), (128, 36, 119), (236, 70, 85), (255, 167, 72)),
    ]
    frames = []
    for frame in range(count):
        p = math.tau * frame / count
        image = Image.new("RGB", (W, H), bg)
        draw = ImageDraw.Draw(image)
        for i, colors in enumerate(palettes):
            cx = [15, 34, 51][i] + round(4 * math.sin(p + i * 2.1))
            cy = [9, 22, 12][i] + round(5 * math.cos(p + i * 1.7))
            rx = [10, 12, 9][i] + round(2 * math.sin(p * 2 + i))
            ry = [7, 8, 10][i] + round(2 * math.cos(p * 2 + i))
            for inset, color in zip((0, 2, 4, 6), colors):
                if rx - inset > 0 and ry - inset > 0:
                    draw.ellipse(
                        [cx - rx + inset, cy - ry + inset, cx + rx - inset, cy + ry - inset],
                        fill=color,
                    )
        frames.append(image)
    return frames


def aurora_frames(count=12):
    palette = [
        (5, 18, 45), (7, 39, 69), (8, 75, 91), (12, 118, 107),
        (28, 159, 126), (75, 203, 153), (136, 231, 188), (205, 248, 217),
    ]

    def field(x, y, p):
        fold = y + 0.20 * math.sin(8 * x + p) + 0.12 * math.sin(14 * x - 1.7 * p)
        curl = x + 0.16 * math.sin(9 * y - p)
        tide = x - y + 0.10 * math.sin(5 * (x + y) + p)
        return (
            1.05 * math.sin(9 * fold + p)
            + 0.62 * math.sin(7 * curl - p)
            + 0.38 * math.cos(13 * tide + 1.6 * p)
        )

    return [_field_frame(palette, f, count, field, 8) for f in range(count)]


def kelp_current_frames(count=16):
    palette = [
        (5, 21, 38), (8, 46, 62), (8, 82, 83), (12, 123, 103),
        (31, 166, 120), (87, 205, 151), (159, 231, 184), (217, 247, 207),
    ]

    def field(x, y, p):
        sweep = x + 0.22 * math.sin(5.5 * y + p) + 0.08 * math.sin(13 * y - p)
        tide = y + 0.18 * math.sin(6 * x - 0.8 * p)
        eddy = math.sin(10 * math.hypot(x + 0.12 * math.cos(p), y - 0.05 * math.sin(p)) - p)
        return 1.05 * math.sin(8.5 * sweep + p) + 0.62 * math.cos(7 * tide - p) + 0.35 * eddy

    return [_field_frame(palette, f, count, field, 7) for f in range(count)]


def coral_mist_frames(count=16):
    palette = [
        (31, 18, 58), (73, 33, 91), (130, 46, 113), (195, 63, 118),
        (239, 96, 101), (255, 143, 91), (255, 190, 126), (126, 90, 177),
    ]
    frames = []
    for frame in range(count):
        p = math.tau * frame / count
        image = Image.new("RGB", (W, H), palette[0])
        pixels = image.load()
        for y in range(H):
            for x in range(W):
                nx = (x - W / 2) / W
                ny = (y - H / 2) / H
                fold = (
                    0.9 * math.sin(7.5 * (nx + 0.16 * math.sin(5 * ny + p)) + p)
                    + 0.7 * math.cos(9 * (ny + 0.11 * math.sin(4 * nx - p)) - p)
                    + 0.35 * math.sin(17 * (nx - ny) + 1.4 * p)
                )
                lift = 0.48 + 0.5 * math.tanh(fold)
                index = max(0, min(6, int(lift * 7)))
                pixels[x, y] = palette[index]

        frames.append(image)
    return frames


def sea_glass_frames(count=28):
    palette = [
        (7, 24, 42), (10, 52, 73), (12, 91, 100), (18, 132, 122),
        (54, 174, 145), (112, 213, 174), (187, 238, 204), (54, 106, 165),
    ]
    frames = []
    for frame in range(count):
        p = math.tau * frame / count
        loop_offset = (len(palette) * 2 - 2) * frame / count
        image = Image.new("RGB", (W, H))
        pixels = image.load()
        for y in range(H):
            for x in range(W):
                cell_x = x // 12
                cell_y = y // 8
                lx = (x % 12) - 5.5
                ly = (y % 8) - 3.5
                dist = abs(lx * 0.78) + abs(ly)
                wave = (
                    dist
                    + 2.2 * math.sin((cell_x + cell_y) * 0.9 + p)
                    + 1.1 * math.sin((x - y) / 12 - p)
                )
                index = int(wave + loop_offset) % (len(palette) * 2 - 2)
                if index >= len(palette):
                    index = len(palette) * 2 - 2 - index
                pixels[x, y] = palette[index]

        draw = ImageDraw.Draw(image)
        for x in range(0, W, 12):
            draw.line([(x, 0), (x, H - 1)], fill=palette[1])
        for y in range(0, H, 8):
            draw.line([(0, y), (W - 1, y)], fill=palette[1])
        frames.append(image)
    return frames


def ember_bloom_frames(count=16):
    palette = [
        (35, 16, 52), (82, 31, 88), (142, 44, 102), (207, 64, 101),
        (246, 101, 83), (255, 151, 83), (255, 208, 117), (103, 63, 150),
    ]
    frames = []
    centers = ((16, 9), (44, 8), (30, 22), (57, 24), (6, 25))
    for frame in range(count):
        p = math.tau * frame / count
        image = Image.new("RGB", (W, H), palette[0])
        pixels = image.load()
        for y in range(H):
            for x in range(W):
                value = 0.0
                for i, (cx, cy) in enumerate(centers):
                    dx = x - (cx + 2 * math.sin(p + i))
                    dy = y - (cy + 2 * math.cos(p + i * 1.4))
                    radius = math.hypot(dx * 0.9, dy * 1.25)
                    angle = math.atan2(dy, dx)
                    value += math.sin(radius * 0.55 - p + i) + 0.55 * math.cos(6 * angle + p)
                value = 0.5 + 0.5 * math.tanh(value * 0.28)
                index = max(0, min(6, int(value * 7)))
                pixels[x, y] = palette[index]

        frames.append(image)
    return frames


def contour_frames(count=12):
    palette = [
        (14, 18, 48), (37, 37, 83), (74, 46, 105), (116, 52, 112),
        (162, 61, 105), (207, 83, 91), (239, 126, 78), (250, 183, 91),
    ]
    frames = []
    for frame in range(count):
        p = math.tau * frame / count
        image = Image.new("RGB", (W, H), palette[0])
        pixels = image.load()
        for y in range(H):
            for x in range(W):
                dx = x - (31 + 8 * math.cos(p))
                dy = (y - (16 + 5 * math.sin(p))) * 1.55
                radius = math.hypot(dx, dy)
                radius += 4 * math.sin(x / 8 + p) + 2 * math.sin(y / 3 - p)
                index = int(radius / 4.2) % (len(palette) * 2 - 2)
                if index >= len(palette):
                    index = len(palette) * 2 - 2 - index
                pixels[x, y] = palette[index]
        frames.append(image)
    return frames
