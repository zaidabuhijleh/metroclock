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


def render_caustic_lattice_frame(tick, fps=8):
    palette = [
        (3, 13, 26), (5, 30, 45), (7, 58, 72), (11, 93, 105),
        (26, 137, 143), (71, 185, 182), (149, 231, 221), (235, 255, 241),
    ]
    t = tick / fps
    image = Image.new("RGB", (W, H), palette[0])
    pixels = image.load()
    for y in range(H):
        ny = y / H
        for x in range(W):
            nx = x / W
            shimmer = 0.0
            for i, scale in enumerate((0.9, 1.25, 1.75)):
                a = nx * math.tau * (scale + 0.2 * i) + t * (0.18 + i * 0.035) + i * 1.7
                b = ny * math.tau * (1.15 + 0.17 * i) - t * (0.14 + i * 0.04)
                curve = math.sin(a + 0.65 * math.sin(b)) + math.cos(b - 0.5 * math.sin(a))
                shimmer += max(0.0, 1.0 - abs(curve) * 2.8)
            tide = 0.25 + 0.22 * math.sin((x + y) / 11 + t * 0.22)
            index = max(0, min(7, int((shimmer * 1.55 + tide) * 2.0)))
            pixels[x, y] = palette[index]
    return image


def render_interference_bloom_frame(tick, fps=8):
    palette = [
        (5, 8, 32), (20, 19, 65), (48, 37, 112), (90, 55, 161),
        (152, 70, 181), (220, 86, 154), (255, 146, 126), (168, 225, 235),
    ]
    t = tick / fps
    emitters = [
        (17 + 6 * math.sin(t * 0.13), 10 + 5 * math.cos(t * 0.17), 0.0),
        (44 + 7 * math.sin(t * 0.11 + 2.2), 18 + 4 * math.cos(t * 0.15 + 1.4), 1.7),
        (30 + 8 * math.sin(t * 0.09 + 4.1), 26 + 3 * math.cos(t * 0.19 + 3.0), 3.2),
    ]
    image = Image.new("RGB", (W, H), palette[0])
    pixels = image.load()
    for y in range(H):
        for x in range(W):
            value = 0.0
            for cx, cy, phase in emitters:
                radius = math.hypot((x - cx) * 0.72, (y - cy) * 1.15)
                value += math.sin(radius * 0.88 - t * 0.42 + phase)
            value += 0.55 * math.sin((x - y) / 7 + t * 0.16)
            band = _triangle_palette_index(value * 1.55 + t * 0.38, len(palette))
            if band == 0 and value > 1.6:
                band = 7
            pixels[x, y] = palette[band]
    return image


def render_lace_diffusion_frame(tick, fps=8):
    palette = [
        (6, 8, 22), (18, 15, 38), (38, 28, 58), (74, 43, 78),
        (123, 61, 92), (185, 88, 99), (222, 190, 154), (103, 205, 183),
    ]
    t = tick / fps
    image = Image.new("RGB", (W, H), palette[0])
    pixels = image.load()
    for y in range(H):
        ny = (y - H / 2) / H
        for x in range(W):
            nx = (x - W / 2) / W
            a = math.sin(22 * (nx + 0.10 * math.sin(5 * ny + t * 0.18)) + t * 0.32)
            b = math.cos(19 * (ny + 0.12 * math.sin(4 * nx - t * 0.21)) - t * 0.27)
            c = math.sin(15 * (nx - ny) + 6 * math.sin(nx + ny + t * 0.11))
            lace = abs(a + b * 0.9 + c * 0.55)
            if lace < 0.12:
                color = palette[7]
            elif lace < 0.24:
                color = palette[6]
            else:
                color = palette[max(0, min(5, int((lace - 0.25) * 2.3) + 1))]
            pixels[x, y] = color
    return image


def render_turing_morph_frame(tick, fps=8):
    palette = [
        (7, 9, 19), (18, 24, 43), (30, 47, 78), (61, 65, 107),
        (119, 71, 103), (177, 82, 85), (224, 127, 88), (233, 198, 151),
    ]
    t = tick / fps
    image = Image.new("RGB", (W, H), palette[0])
    pixels = image.load()
    for y in range(H):
        ny = (y - H / 2) / H
        for x in range(W):
            nx = (x - W / 2) / W
            warp_x = nx + 0.16 * math.sin(8 * ny + t * 0.17)
            warp_y = ny + 0.14 * math.sin(7 * nx - t * 0.19)
            spots = (
                math.sin(18 * warp_x + t * 0.23)
                + math.sin(17 * warp_y - t * 0.21)
                + math.cos(20 * (warp_x * 0.72 + warp_y * 1.1) + t * 0.13)
            )
            value = math.sin(spots * 1.35 + 2.2 * math.sin(6 * (nx - ny) + t * 0.12))
            if value > 0.86:
                color = palette[7 if (x + y) % 3 == 0 else 6]
            elif value > 0.58:
                color = palette[6]
            elif value > 0.14:
                color = palette[4]
            else:
                color = palette[int(abs(spots * 1.7)) % 3]
            pixels[x, y] = color
    return image


def render_superformula_bloom_frame(tick, fps=8):
    palette = [
        (5, 8, 32), (22, 18, 65), (55, 31, 111), (105, 45, 154),
        (177, 61, 157), (237, 92, 130), (255, 159, 119), (132, 233, 191),
    ]
    t = tick / fps
    image = Image.new("RGB", (W, H), palette[0])
    pixels = image.load()
    m = 6 + 1.2 * math.sin(t * 0.10)
    n1 = 0.35 + 0.06 * math.sin(t * 0.13)
    n2 = 1.25 + 0.20 * math.cos(t * 0.09)
    n3 = 1.25 + 0.20 * math.sin(t * 0.11)
    for y in range(H):
        yy = (y - H / 2) / 11.5
        for x in range(W):
            xx = (x - W / 2) / 18.0
            angle = math.atan2(yy, xx)
            radius = math.hypot(xx, yy)
            part = abs(math.cos(m * angle / 4)) ** n2 + abs(math.sin(m * angle / 4)) ** n3
            shape = part ** (-1 / n1)
            ripple = 0.10 * math.sin(14 * radius - t * 0.28)
            diff = shape - radius + ripple
            if diff > 0.22:
                color = palette[3 + int((diff * 7 + t * 0.4) % 3)]
            elif diff > 0.04:
                color = palette[6]
            elif abs(diff) < 0.045:
                color = palette[7]
            else:
                color = palette[max(0, min(2, int((radius + 0.4) * 2)))]
            pixels[x, y] = color
    return image


def render_ink_advection_frame(tick, fps=8):
    palette = [
        (4, 8, 28), (10, 29, 57), (9, 69, 79), (18, 124, 105),
        (71, 190, 145), (156, 82, 157), (230, 92, 134), (255, 172, 122),
    ]
    t = tick / fps
    image = Image.new("RGB", (W, H), palette[0])
    pixels = image.load()
    for y in range(H):
        ny = (y - H / 2) / H
        for x in range(W):
            nx = (x - W / 2) / W
            vx = nx + 0.20 * math.sin(6 * ny + t * 0.22) + 0.10 * math.sin(13 * ny - t * 0.17)
            vy = ny + 0.17 * math.sin(7 * nx - t * 0.19) + 0.08 * math.cos(11 * nx + t * 0.13)
            swirl = math.atan2(vy + 0.12 * math.sin(t * 0.09), vx - 0.10 * math.cos(t * 0.11))
            radius = math.hypot(vx * 1.15, vy * 1.7)
            ink = (
                0.9 * math.sin(9 * vx + 3 * math.sin(4 * vy + t * 0.23) + t * 0.28)
                + 0.7 * math.cos(8 * vy - 2 * math.sin(5 * vx - t * 0.21))
                + 0.45 * math.sin(7 * radius - 1.5 * swirl + t * 0.18)
            )
            lift = 0.5 + 0.5 * math.tanh(ink * 0.72)
            index = max(0, min(7, int(lift * 8)))
            pixels[x, y] = palette[index]
    return image


def render_ridge_silk_frame(tick, fps=8):
    palette = [
        (8, 7, 28), (25, 17, 58), (51, 31, 96), (43, 68, 126),
        (32, 121, 129), (151, 72, 132), (214, 107, 123), (237, 190, 151),
    ]
    t = tick / fps
    image = Image.new("RGB", (W, H), palette[0])
    pixels = image.load()
    for y in range(H):
        ny = (y - H / 2) / H
        for x in range(W):
            nx = (x - W / 2) / W
            wx = nx + 0.18 * math.sin(5 * ny + t * 0.12)
            wy = ny + 0.14 * math.cos(6 * nx - t * 0.10)
            value = 0.0
            amp = 1.0
            freq = 5.0
            for octave in range(4):
                n = math.sin(freq * (wx + 0.6 * wy) + t * (0.10 + octave * 0.025))
                n += 0.65 * math.cos(freq * (wy - 0.4 * wx) - t * (0.09 + octave * 0.02))
                ridge = 1.0 - abs(n * 0.5)
                value += ridge * amp
                amp *= 0.55
                freq *= 1.75
                wx += 0.05 * math.sin(value + octave)
                wy += 0.04 * math.cos(value - octave)
            band = _triangle_palette_index(value * 4.1 + t * 0.18, len(palette))
            pixels[x, y] = palette[band]
    return image


def render_attractor_dust_frame(tick, fps=8):
    palette = [
        (3, 6, 22), (12, 22, 59), (23, 61, 122), (30, 132, 173),
        (91, 220, 183), (156, 124, 223), (244, 82, 137), (255, 190, 118),
    ]
    t = tick / fps
    image = Image.new("RGB", (W, H), palette[0])
    pixels = image.load()

    a = -1.72 + 0.08 * math.sin(t * 0.07)
    b = 1.82 + 0.07 * math.cos(t * 0.06)
    c = -1.15 + 0.06 * math.sin(t * 0.05 + 2.0)
    d = -1.48 + 0.05 * math.cos(t * 0.08 + 1.1)
    x, y = 0.1, 0.0
    for i in range(900):
        x, y = math.sin(a * y) + c * math.cos(a * x), math.sin(b * x) + d * math.cos(b * y)
        if i < 40:
            continue
        px = int(round(W / 2 + x * 13.5 + 3 * math.sin(t * 0.05)))
        py = int(round(H / 2 + y * 7.5 + 2 * math.cos(t * 0.04)))
        if 0 <= px < W and 0 <= py < H:
            old = pixels[px, py]
            color = palette[3 + (i // 130) % 5]
            pixels[px, py] = tuple(min(255, old[j] + color[j] // 2) for j in range(3))
            if i % 37 == 0 and px + 1 < W:
                pixels[px + 1, py] = palette[4]
    return image


def render_moire_vault_frame(tick, fps=8):
    palette = [
        (3, 6, 22), (8, 15, 40), (13, 31, 58), (19, 62, 82),
        (35, 119, 126), (76, 212, 184), (119, 96, 206), (255, 184, 94),
    ]
    phase = math.tau * ((tick % 64) / 64)
    centers = (
        (12 + 5 * math.cos(phase), 16 + 3 * math.sin(phase * 1.4)),
        (52 + 5 * math.cos(phase + 2.1), 15 + 4 * math.sin(phase * 1.2 + 1.2)),
        (32 + 4 * math.cos(phase * 0.7 + 4.0), 16 + 6 * math.sin(phase * 0.8)),
    )
    image = Image.new("RGB", (W, H), palette[0])
    pixels = image.load()
    for y in range(H):
        for x in range(W):
            distances = []
            for cx, cy in centers:
                dx = (x - cx) * 0.78
                dy = y - cy
                distances.append(math.hypot(dx, dy))
            ring_a = abs((distances[0] + phase * 2.0) % 8.8 - 4.4)
            ring_b = abs((distances[1] - phase * 1.7) % 9.4 - 4.7)
            ring_c = abs((distances[2] + phase * 1.1) % 12.0 - 6.0)
            braid = abs(((distances[0] - distances[1]) + phase * 1.4) % 10.4 - 5.2)
            line = min(ring_a, ring_b, ring_c * 0.85)
            crossing = braid < 0.34 and (ring_a < 1.1 or ring_b < 1.1)
            if line < 0.20:
                color = palette[7 if crossing or (x + y + tick) % 23 == 0 else 5]
            elif line < 0.48:
                color = palette[6 if crossing else 4]
            elif line < 0.78:
                color = palette[3]
            else:
                shade = 1 + int(0.5 + 0.5 * math.sin((x - y) * 0.10 + phase))
                color = palette[shade]
            pixels[x, y] = color
    return image


def render_signal_traces_frame(tick, fps=8):
    palette = [
        (3, 7, 18), (8, 16, 35), (13, 34, 52), (24, 82, 76),
        (47, 157, 124), (98, 229, 177), (255, 154, 98), (255, 222, 130),
    ]
    phase = (tick % 72) / 72
    image = Image.new("RGB", (W, H), palette[0])
    draw = ImageDraw.Draw(image)
    for x in range(4, W, 8):
        draw.line([(x, 0), (x, H - 1)], fill=palette[1])
    for y in range(4, H, 8):
        draw.line([(0, y), (W - 1, y)], fill=palette[1])

    paths = [
        [(0, 7), (11, 7), (11, 15), (25, 15), (25, 5), (42, 5), (42, 12), (63, 12)],
        [(3, 27), (15, 27), (15, 20), (31, 20), (31, 28), (49, 28), (49, 21), (63, 21)],
        [(0, 18), (9, 18), (18, 9), (31, 9), (40, 18), (52, 18), (63, 7)],
        [(6, 2), (20, 2), (20, 11), (35, 11), (35, 25), (53, 25), (60, 31)],
        [(0, 30), (10, 24), (22, 24), (33, 13), (45, 13), (56, 2), (63, 2)],
    ]

    def path_points(path):
        points = []
        for (x1, y1), (x2, y2) in zip(path, path[1:]):
            steps = max(abs(x2 - x1), abs(y2 - y1))
            for step in range(steps):
                p = step / max(1, steps)
                points.append((round(x1 + (x2 - x1) * p), round(y1 + (y2 - y1) * p)))
        points.append(path[-1])
        return points

    for path_index, path in enumerate(paths):
        points = path_points(path)
        line_color = palette[3 + path_index % 2]
        draw.line(path, fill=line_color)
        offset = int((phase + path_index * 0.17) * len(points)) % len(points)
        for glow in range(7):
            px, py = points[(offset - glow * 2) % len(points)]
            color = palette[7 if glow == 0 else 6 if glow < 3 else 5]
            draw.point((px, py), fill=color)
            if glow < 2 and px + 1 < W:
                draw.point((px + 1, py), fill=palette[6])
        for node in path[1:-1:2]:
            draw.point(node, fill=palette[5])
    return image


def render_orbit_loom_frame(tick, fps=8):
    palette = [
        (5, 5, 22), (13, 16, 49), (28, 33, 82), (59, 51, 123),
        (108, 61, 160), (208, 78, 150), (255, 143, 113), (124, 233, 210),
    ]
    phase = math.tau * ((tick % 80) / 80)
    image = Image.new("RGB", (W, H), palette[0])
    draw = ImageDraw.Draw(image)
    for y in range(H):
        if y % 5 == 0:
            draw.line([(0, y), (W - 1, y)], fill=palette[1])

    curves = [
        (25, 10, 2, 3, 0.0, palette[7]),
        (24, 9, 3, 4, 1.7, palette[5]),
        (18, 7, 5, 2, 3.4, palette[6]),
    ]
    for radius_x, radius_y, ax, ay, shift, color in curves:
        previous = None
        for i in range(72):
            u = math.tau * i / 72
            wobble = 2.5 * math.sin(u * 3 + phase + shift)
            x = round(W / 2 + (radius_x + wobble) * math.sin(ax * u + phase * 0.7 + shift))
            y = round(H / 2 + radius_y * math.sin(ay * u - phase * 0.9 + shift))
            point = (x, y)
            if 0 <= x < W and 0 <= y < H:
                if previous and abs(previous[0] - x) <= 5 and abs(previous[1] - y) <= 5:
                    draw.line([previous, point], fill=color)
                if i % 9 == int(tick / 2 + shift) % 9:
                    draw.point(point, fill=palette[7])
            previous = point
    draw.rectangle((30, 14, 33, 17), outline=palette[6])
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
