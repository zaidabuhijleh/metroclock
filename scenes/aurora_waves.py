from .abstract_core import render_aurora_frame

NAME = "Aurora Waves"
COLLECTION = "Flow"
FPS = 8
PREVIEW_FRAMES = 48


def render_frame(tick):
    return render_aurora_frame(tick, FPS)
