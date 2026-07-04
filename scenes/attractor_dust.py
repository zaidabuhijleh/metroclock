from .abstract_core import render_attractor_dust_frame

NAME = "Attractor Dust"
COLLECTION = "Patterns"
FPS = 8
PREVIEW_FRAMES = 48


def render_frame(tick):
    return render_attractor_dust_frame(tick, FPS)
