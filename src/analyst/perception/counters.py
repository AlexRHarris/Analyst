"""Per-card counter OCR.

MTGO renders counters as small overlay numbers near the bottom-right of the
card slot. We crop a fraction of the slot, OCR digits, and return a flat int.
The counter type is left to the reasoning model — distinguishing +1/+1 from
loyalty etc. by pixel color alone is brittle. We just report 'count'.

For higher precision later: classify color of the counter chip (white = +1/+1,
red = -1/-1, blue = loyalty, etc.) — see `_chip_color` stub below.
"""
from PIL import Image
from . import ocr


def detect_card_counters(slot: Image.Image) -> dict[str, int]:
    w, h = slot.size
    badge = slot.crop((int(w * 0.55), int(h * 0.65), w, h))
    n = ocr.integer(badge)
    if n is None or n == 0:
        return {}
    return {"count": n}


def detect_player_counter(badge: Image.Image) -> int:
    """Generic numeric badge OCR used for poison/energy/experience/etc."""
    n = ocr.integer(badge)
    return n or 0


def _chip_color(badge: Image.Image) -> str:
    """Stub: return rough color name of the most-saturated pixel block.

    Useful for distinguishing counter types (white +1/+1 vs red -1/-1 vs
    blue loyalty). Not wired in yet.
    """
    rgb = badge.convert("RGB").resize((4, 4))
    pixels = list(rgb.getdata())
    avg = tuple(sum(c) / len(pixels) for c in zip(*pixels))
    r, g, b = avg
    if r > 180 and g > 180 and b > 180:
        return "white"
    if r > g + 30 and r > b + 30:
        return "red"
    if b > r + 30 and b > g + 30:
        return "blue"
    if g > r + 30 and g > b + 30:
        return "green"
    return "neutral"
