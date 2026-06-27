from .abstract_core import render_fractal_garden_frame

NAME = "Fractal Garden"
COLLECTION = "Patterns"
FPS = 8
PREVIEW_FRAMES = 48


def render_frame(tick):
    return render_fractal_garden_frame(tick, FPS)
