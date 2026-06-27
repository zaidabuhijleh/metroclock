from .abstract_core import render_thermal_frame

NAME = "Thermal Flow"
COLLECTION = "Flow"
FPS = 8
PREVIEW_FRAMES = 48


def render_frame(tick):
    return render_thermal_frame(tick, FPS)
