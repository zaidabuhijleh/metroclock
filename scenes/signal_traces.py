from .abstract_core import render_signal_traces_frame

NAME = "Signal Traces"
COLLECTION = "Patterns"
FPS = 8
PREVIEW_FRAMES = 72


def render_frame(tick):
    return render_signal_traces_frame(tick, FPS)
