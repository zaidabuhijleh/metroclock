from .abstract_core import render_orbit_loom_frame

NAME = "Orbit Loom"
COLLECTION = "Patterns"
FPS = 8
PREVIEW_FRAMES = 80


def render_frame(tick):
    return render_orbit_loom_frame(tick, FPS)
