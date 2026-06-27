from .abstract_core import render_kelp_current_frame

NAME = "Kelp Current"
COLLECTION = "Flow"
FPS = 8
PREVIEW_FRAMES = 48


def render_frame(tick):
    return render_kelp_current_frame(tick, FPS)
