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


def render_biolume_bloom_frame(tick, fps=8):
    palette = [
        (3, 10, 29), (8, 24, 55), (20, 33, 88), (34, 64, 122),
        (22, 123, 135), (50, 188, 156), (132, 236, 190), (222, 255, 218),
    ]
    t = tick / fps
    blobs = [
        (14, 10, 8.5, 6.0, 0.19, 0.13, 0.0),
        (35, 16, 11.5, 7.5, 0.14, 0.21, 1.7),
        (52, 8, 7.5, 5.5, 0.23, 0.16, 3.4),
        (22, 25, 9.0, 6.5, 0.17, 0.24, 4.8),
        (58, 24, 8.0, 6.0, 0.11, 0.29, 2.5),
    ]
    image = Image.new("RGB", (W, H), palette[0])
    pixels = image.load()
    for y in range(H):
        for x in range(W):
            value = -1.2
            for cx, cy, rx, ry, sx, sy, phase in blobs:
                bx = cx + 5 * math.sin(t * sx + phase) + 2 * math.sin(t * 0.07 + phase)
                by = cy + 4 * math.cos(t * sy + phase)
                dx = (x - bx) / rx
                dy = (y - by) / ry
                value += 1.0 / (0.10 + dx * dx + dy * dy)
            value += 0.22 * math.sin(x / 5 + y / 7 + t * 0.2)
            index = max(0, min(len(palette) - 1, int((0.5 + 0.5 * math.tanh(value * 0.6 - 1.1)) * len(palette))))
            pixels[x, y] = palette[index]
    return image


def render_vector_plankton_frame(tick, fps=8):
    palette = [
        (4, 9, 31), (9, 24, 62), (16, 48, 104), (21, 92, 149),
        (38, 151, 177), (88, 215, 186), (180, 243, 191), (255, 229, 151),
    ]
    t = tick / fps
    image = Image.new("RGB", (W, H), palette[0])
    draw = ImageDraw.Draw(image)

    for y in range(H):
        shade = palette[min(2, y // 11)]
        draw.line([(0, y), (W - 1, y)], fill=shade)

    for i in range(18):
        seed = i * 12.9898
        base_x = (i * 17 + 11) % W
        base_y = (i * 23 + 7) % H
        age = (t * (0.33 + (i % 5) * 0.025) + i * 0.137) % 1.0
        x = base_x + 20 * (age - 0.5)
        y = base_y + 7 * math.sin(age * math.tau + seed) + 4 * math.sin(t * 0.21 + seed)
        for step in range(4):
            a = age - step * 0.028
            px = int(round((base_x + 20 * (a - 0.5)) % W))
            py = int(round((y - step * 0.9 + 2 * math.sin(a * 8 + seed)) % H))
            color = palette[max(3, 6 - step)]
            draw.point((px, py), fill=color)
            if step == 0:
                draw.point(((px - 1) % W, py), fill=palette[4])
        head = (int(round(x % W)), int(round(y % H)))
        draw.point(head, fill=palette[7 if i % 6 == 0 else 6])

    for ribbon in range(3):
        points = []
        for x in range(W):
            y = 8 + ribbon * 8 + 3 * math.sin(x / 9 + t * (0.18 + ribbon * 0.04)) + 2 * math.sin(x / 4 - t * 0.13)
            points.append((x, round(y)))
        draw.line(points, fill=palette[2 + ribbon], width=1)
    return image


def render_cellular_reef_frame(tick, fps=8):
    palette = [
        (27, 14, 45), (64, 27, 75), (112, 38, 93), (178, 56, 101),
        (236, 92, 100), (255, 146, 105), (255, 203, 145), (54, 164, 143),
    ]
    t = tick / fps
    image = Image.new("RGB", (W, H), palette[0])
    pixels = image.load()
    for y in range(H):
        ny = (y - H / 2) / H
        for x in range(W):
            nx = (x - W / 2) / W
            a = math.sin(13 * (nx + 0.12 * math.sin(4 * ny + t * 0.17)) + t * 0.24)
            b = math.cos(12 * (ny + 0.13 * math.sin(3.5 * nx - t * 0.21)) - t * 0.19)
            c = math.sin(18 * math.hypot(nx + 0.18 * math.sin(t * 0.09), ny - 0.12 * math.cos(t * 0.11)) - t * 0.31)
            value = abs(a + b + 0.75 * c)
            band = int(value * 2.8 + t * 0.22) % 7
            if band in (0, 1):
                color = palette[7]
            else:
                color = palette[min(6, band)]
            pixels[x, y] = color
    return image


def render_neon_ribbons_frame(tick, fps=8):
    bg = (5, 8, 31)
    palette = [
        (12, 22, 64), (44, 58, 130), (94, 92, 198), (190, 77, 198),
        (249, 87, 157), (255, 143, 91), (255, 204, 117), (126, 234, 196),
    ]
    t = tick / fps
    image = Image.new("RGB", (W, H), bg)
    pixels = image.load()
    for y in range(H):
        for x in range(W):
            nx = x / W
            ny = y / H
            value = 0.0
            for i in range(4):
                center = 0.18 + i * 0.20 + 0.06 * math.sin(t * (0.11 + i * 0.03) + i)
                curve = center + 0.10 * math.sin(nx * math.tau * (1.2 + i * 0.18) + t * (0.18 + i * 0.04) + i)
                dist = abs(ny - curve)
                value += max(0.0, 0.055 - dist) * (18 - i)
            value += 0.15 * math.sin(14 * (nx + ny) + t * 0.22)
            if value <= 0.08:
                color = palette[0 if (x + y + int(t * 2)) % 9 else 1]
            else:
                color = palette[max(1, min(7, int(value * 2.1)))]
            pixels[x, y] = color

    draw = ImageDraw.Draw(image)
    for i in range(4):
        points = []
        color = palette[3 + (i % 5)]
        for x in range(-2, W + 2):
            y = 6 + i * 6 + 4 * math.sin(x / (8 + i) + t * (0.16 + i * 0.03) + i)
            points.append((x, round(y)))
        draw.line(points, fill=color, width=1)
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
