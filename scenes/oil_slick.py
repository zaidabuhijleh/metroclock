from .abstract_core import render_oil_frame

NAME = "Oil Slick"
COLLECTION = "Flow"
FPS = 8
PREVIEW_FRAMES = 48


def render_frame(tick):
    return render_oil_frame(tick, FPS)
