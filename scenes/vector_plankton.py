from .abstract_core import render_vector_plankton_frame

NAME = "Vector Plankton"
COLLECTION = "Flow"
FPS = 8
PREVIEW_FRAMES = 48


def render_frame(tick):
    return render_vector_plankton_frame(tick, FPS)
