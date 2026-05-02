"""Stack: identify each thumbnail in the stack region top-to-bottom via phash."""
from PIL import Image

from .card_id import identify
from .helpers import is_blank


def parse_stack(stack_img: Image.Image, index, slots: int = 6) -> list[dict]:
    w, h = stack_img.size
    rh = h // slots
    out: list[dict] = []
    for i in range(slots):
        slot = stack_img.crop((0, i * rh, w, (i + 1) * rh))
        if is_blank(slot):
            continue
        m = identify(slot, index, threshold=16)
        if m:
            out.append({"source": m["name"], "scryfall_id": m["id"], "is_ability": False})
        else:
            out.append({"source": "?unknown", "is_ability": False})
    return out
