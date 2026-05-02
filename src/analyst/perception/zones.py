"""Zone-count badges (library / graveyard / exile / hand) — small numeric overlays."""
from PIL import Image
from . import ocr


def count(badge: Image.Image) -> int:
    n = ocr.integer(badge)
    return n or 0
