from .abstract_core import render_moire_vault_frame

NAME = "Moire Vault"
COLLECTION = "Patterns"
FPS = 8
PREVIEW_FRAMES = 64


def render_frame(tick):
    return render_moire_vault_frame(tick, FPS)
