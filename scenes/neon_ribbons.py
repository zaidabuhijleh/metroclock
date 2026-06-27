from .abstract_core import render_neon_ribbons_frame

NAME = "Neon Ribbons"
COLLECTION = "Patterns"
FPS = 8
PREVIEW_FRAMES = 48


def render_frame(tick):
    return render_neon_ribbons_frame(tick, FPS)
