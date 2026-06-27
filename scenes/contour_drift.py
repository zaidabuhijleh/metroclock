from .abstract_core import render_contour_frame

NAME = "Contour Drift"
COLLECTION = "Patterns"
FPS = 8
PREVIEW_FRAMES = 48


def render_frame(tick):
    return render_contour_frame(tick, FPS)
