from .abstract_core import render_lava_frame

NAME = "Lava Lamp"
COLLECTION = "Flow"
FPS = 8
PREVIEW_FRAMES = 48


def render_frame(tick):
    return render_lava_frame(tick, FPS)
