from .abstract_core import render_cyclic_colonies_frame

NAME = "Cyclic Colonies"
COLLECTION = "Patterns"
FPS = 8
PREVIEW_FRAMES = 48


def render_frame(tick):
    return render_cyclic_colonies_frame(tick, FPS)
