from .abstract_core import render_liquid_frame

NAME = "Liquid Chroma"
COLLECTION = "Flow"
FPS = 8
PREVIEW_FRAMES = 48


def render_frame(tick):
    return render_liquid_frame(tick, FPS)
