#!/usr/bin/env python3
"""Render MetroClock ambient scenes into reviewable artifacts."""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw

from scenes import SCENES


DEFAULT_OUTPUT = ROOT / "artifacts" / "scenes"


def scene_key(scene) -> str:
    return scene.__name__.split(".")[-1]


def render_scene(scene, output_root: Path, scale: int) -> None:
    key = scene_key(scene)
    scene_dir = output_root / key
    frames_dir = scene_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    frames = [frame.convert("RGB") for frame in scene.FRAMES]
    for index, frame in enumerate(frames):
        frame.save(frames_dir / f"{index:02d}.png")

    duration = max(1, round(1000 / scene.FPS))
    frames[0].save(
        scene_dir / f"{key}.gif",
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
        disposal=2,
    )

    preview_frames = [
        frame.resize((frame.width * scale, frame.height * scale), Image.Resampling.NEAREST)
        for frame in frames
    ]
    preview_frames[0].save(
        scene_dir / f"{key}_{scale}x.gif",
        save_all=True,
        append_images=preview_frames[1:],
        duration=duration,
        loop=0,
        disposal=2,
    )
    preview_frames[0].save(scene_dir / f"{key}_{scale}x.png")

    columns = min(4, len(frames))
    rows = (len(frames) + columns - 1) // columns
    label_height = 7
    sheet = Image.new("RGB", (columns * 64, rows * (32 + label_height)), (12, 12, 18))
    draw = ImageDraw.Draw(sheet)
    for index, frame in enumerate(frames):
        x = (index % columns) * 64
        y = (index // columns) * (32 + label_height)
        sheet.paste(frame, (x, y))
        draw.text((x + 2, y + 32), f"{index:02d}", fill=(210, 210, 220))
    sheet.save(scene_dir / f"{key}_contact.png")
    sheet.resize(
        (sheet.width * scale, sheet.height * scale),
        Image.Resampling.NEAREST,
    ).save(scene_dir / f"{key}_contact_{scale}x.png")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--scale", type=int, default=8)
    parser.add_argument("--scenes", nargs="*", default=[])
    args = parser.parse_args()

    selected = SCENES
    if args.scenes:
        requested = set(args.scenes)
        selected = [scene for scene in SCENES if scene_key(scene) in requested]
        missing = requested - {scene_key(scene) for scene in selected}
        if missing:
            raise SystemExit(f"Unknown scenes: {', '.join(sorted(missing))}")

    args.output.mkdir(parents=True, exist_ok=True)
    for scene in selected:
        importlib.reload(scene)
        render_scene(scene, args.output, args.scale)
        print(f"Rendered {scene_key(scene)}")


if __name__ == "__main__":
    main()
