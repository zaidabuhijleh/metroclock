from .abstract_core import render_coral_mist_frame

NAME = "Coral Mist"
COLLECTION = "Flow"
FPS = 8
PREVIEW_FRAMES = 48


def render_frame(tick):
    return render_coral_mist_frame(tick, FPS)
