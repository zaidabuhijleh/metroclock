#!/usr/bin/env python3
"""Measure the MetroClock render hot paths on the machine you run it on.

Read-only: it never writes config and never opens the LED matrix, so it is safe
to run on a live Pi. Stop the service first if you want clean numbers, since
otherwise you are sharing a single core with the real render loop:

    sudo systemctl stop metroclock
    cd /home/zaid/metroclock && .venv/bin/python scripts/bench_render.py
    sudo systemctl start metroclock

Numbers are medians in milliseconds.
"""

from __future__ import annotations

import os
import platform
import statistics
import sys
import time
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# The matrix binding is Pi-only and we never draw to it here; stub it so the
# same script runs on a dev machine.
try:
    import rgbmatrix  # noqa: F401
except ImportError:
    stub = types.ModuleType("rgbmatrix")

    class _Options:
        pass

    class _Matrix:
        def __init__(self, options=None):
            self.brightness = 100

        def CreateFrameCanvas(self):
            return object()

        def SetImage(self, image):
            pass

    stub.RGBMatrix = _Matrix
    stub.RGBMatrixOptions = _Options
    sys.modules["rgbmatrix"] = stub

import config
import config_manager

LOOP_FPS = 50  # what core/app.py's 0.02s sleep targets


def bench(fn, repeats: int) -> float:
    fn()  # warm
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - started) * 1000.0)
    return statistics.median(samples)


def host_summary() -> str:
    model = ""
    try:
        with open("/proc/cpuinfo", "r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith(("Model", "model name")):
                    model = line.split(":", 1)[1].strip()
                    break
    except Exception:
        model = platform.processor() or platform.machine()
    return f"{platform.system()} {platform.machine()} | {model or 'unknown cpu'} | Python {platform.python_version()}"


def section(title: str):
    print()
    print(title)
    print("-" * len(title))


def bench_config():
    section("config (core/app.py reloads this 2-3x per rendered frame)")
    reload_ms = bench(config_manager.reload_config, 40)
    print(f"  reload_config()            {reload_ms:8.2f} ms")
    print(f"  read_config()              {bench(config_manager.read_config, 40):8.2f} ms")
    print(f"  -> at {LOOP_FPS}fps x2.5 calls: {reload_ms * LOOP_FPS * 2.5:7.0f} ms of CPU per second")


def bench_fonts():
    section("font discovery (its cache is destroyed by every reload_config)")
    config._FONT_FAMILIES_CACHE = None
    started = time.perf_counter()
    families = config._discover_font_families()
    cold_ms = (time.perf_counter() - started) * 1000.0
    files = sum(len(family.get("sizes") or []) for family in families)
    print(f"  _discover_font_families()  {cold_ms:8.2f} ms  ({len(families)} families, {files} font files)")
    print(f"  warm (cached)              {bench(config._discover_font_families, 20):8.2f} ms")
    print("  -> paid on every clock-face cache miss, i.e. once a minute in clock mode")


def bench_scenes():
    section("ambient scenes (AmbientWidget.draw re-renders every loop tick)")
    from scenes import SCENES

    procedural = [scene for scene in SCENES if hasattr(scene, "render_frame")]
    rows = []
    for scene in procedural:
        name = scene.__name__.split(".")[-1]
        rows.append((bench(lambda s=scene: s.render_frame(7), 5), name, scene.FPS))
    rows.sort(reverse=True)

    for ms, name, fps in rows[:6]:
        print(f"  {name:<24} {ms:8.2f} ms/frame   scene FPS={fps}")
    print(f"  ... {len(procedural)} procedural scenes total")

    median_ms = statistics.median(row[0] for row in rows)
    scene_fps = statistics.median(row[2] for row in rows)
    print(f"  median                     {median_ms:8.2f} ms/frame")
    print(f"  -> rendered at {LOOP_FPS}fps: {median_ms * LOOP_FPS:7.0f} ms of CPU per second")
    print(f"  -> actually needed at {scene_fps:.0f}fps: {median_ms * scene_fps:7.0f} ms of CPU per second")


def bench_widgets():
    section("steady-state widget render (update + draw, warm caches)")
    from core.app import WidgetRegistry

    import web_server

    registry = WidgetRegistry(width=config.MATRIX_WIDTH, height=config.MATRIX_HEIGHT)
    # Scene 0 is a precomputed-FRAMES scene, which would make ambient look free.
    # Pin a procedural one so the row reflects the expensive path.
    web_server.set_ambient_scene("thermal_flow")
    # metro/stocks/sports do blocking network work; give their workers a moment
    # so we measure drawing rather than a cold cache miss.
    time.sleep(2)
    for key in ("clock", "custom", "metro", "stocks", "weather", "ambient", "pomodoro"):
        renderer = registry._renderers.get(key)
        if renderer is None:
            continue
        try:
            print(f"  {key:<24} {bench(renderer.render, 20):8.2f} ms")
        except Exception as exc:
            print(f"  {key:<24}   failed: {type(exc).__name__}: {exc}")
    print(f"  (budget at {LOOP_FPS}fps is {1000.0 / LOOP_FPS:.0f} ms per frame)")


def main():
    print("MetroClock render benchmark")
    print(host_summary())
    bench_config()
    bench_fonts()
    bench_scenes()
    bench_widgets()
    print()


if __name__ == "__main__":
    main()
