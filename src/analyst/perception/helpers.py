"""Tiny utilities shared across perception modules."""
from PIL import Image


def is_blank(img: Image.Image, threshold: int = 5) -> bool:
    """Reject empty card slots / mana cells by extrema of grayscale.

    Empty slots in MTGO render as nearly-uniform background. A real card has
    high-contrast edges and produces a wide extrema range.
    """
    g = img.convert("L")
    lo, hi = g.getextrema()
    return (hi - lo) < threshold


def mean_brightness(img: Image.Image) -> float:
    g = img.convert("L")
    pixels = list(g.getdata())
    return sum(pixels) / len(pixels) if pixels else 0.0
