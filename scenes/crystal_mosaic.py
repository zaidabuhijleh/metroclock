from .abstract_core import render_crystal_mosaic_frame

NAME = "Crystal Mosaic"
COLLECTION = "Patterns"
FPS = 8
PREVIEW_FRAMES = 48


def render_frame(tick):
    return render_crystal_mosaic_frame(tick, FPS)
