from .abstract_core import render_ink_advection_frame

NAME = "Ink Advection"
COLLECTION = "Flow"
FPS = 8
PREVIEW_FRAMES = 48


def render_frame(tick):
    return render_ink_advection_frame(tick, FPS)
