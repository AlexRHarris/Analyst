"""Mana pool W/U/B/R/G/C — six equal cells in a horizontal strip.

The canonical MTGO order is W U B R G C. We split the pool box into six
columns, OCR each, and return a dict.
"""
from PIL import Image
from . import ocr

ORDER = ["W", "U", "B", "R", "G", "C"]


def detect_mana_pool(pool: Image.Image) -> dict[str, int]:
    w, h = pool.size
    cell_w = w // len(ORDER)
    out: dict[str, int] = {}
    for i, color in enumerate(ORDER):
        cell = pool.crop((i * cell_w, 0, (i + 1) * cell_w, h))
        n = ocr.integer(cell)
        out[color] = n or 0
    return out
