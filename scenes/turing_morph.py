from .abstract_core import render_turing_morph_frame

NAME = "Turing Morph"
COLLECTION = "Patterns"
FPS = 8
PREVIEW_FRAMES = 48


def render_frame(tick):
    return render_turing_morph_frame(tick, FPS)
