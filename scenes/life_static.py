from .abstract_core import render_life_static_frame

NAME = "Life Static"
COLLECTION = "Patterns"
FPS = 8
PREVIEW_FRAMES = 48


def render_frame(tick):
    return render_life_static_frame(tick, FPS)
