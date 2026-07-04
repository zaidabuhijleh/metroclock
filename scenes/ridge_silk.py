from .abstract_core import render_ridge_silk_frame

NAME = "Ridge Silk"
COLLECTION = "Patterns"
FPS = 8
PREVIEW_FRAMES = 48


def render_frame(tick):
    return render_ridge_silk_frame(tick, FPS)
