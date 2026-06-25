import math

from PIL import Image, ImageDraw


W, H = 64, 32


def _quantize(value, steps):
    return max(0, min(steps - 1, int(value * steps)))


def _field_frame(palette, frame, count, field, bands=None):
    phase = math.tau * frame / count
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
    palette = [(5, 12, 35), (9, 34, 66), (18, 76, 92), (30, 135, 116), (58, 202, 141), (91, 232, 184)]
    frames = []
    for frame in range(count):
        p = math.tau * frame / count
        image = Image.new("RGB", (W, H), palette[0])
        draw = ImageDraw.Draw(image)
        for y in range(H):
            draw.line([(0, y), (W - 1, y)], fill=palette[min(2, y // 12)])
        for band in range(5, -1, -1):
            points = []
            for x in range(W):
                center = 13 + 5 * math.sin(x / 9 + p) + 2 * math.sin(x / 4 - p)
                points.append((x, round(center + band * 1.5)))
            draw.line(points, fill=palette[band], width=2 if band < 3 else 1)
        for x, y in ((6, 5), (18, 9), (31, 4), (46, 7), (58, 3)):
            draw.point((x, y), fill=(153, 184, 207))
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
