from .abstract_core import render_cellular_reef_frame

NAME = "Cellular Reef"
COLLECTION = "Patterns"
FPS = 8
PREVIEW_FRAMES = 48


def render_frame(tick):
    return render_cellular_reef_frame(tick, FPS)
