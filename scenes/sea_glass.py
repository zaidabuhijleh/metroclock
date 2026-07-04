from .abstract_core import render_sea_glass_frame

NAME = "Sea Glass"
COLLECTION = "Patterns"
FPS = 8
PREVIEW_FRAMES = 48


def render_frame(tick):
    return render_sea_glass_frame(tick, FPS)
