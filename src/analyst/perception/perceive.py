"""Run CV/OCR over a frame and produce a structured perception JSON for the LLM."""
from pathlib import Path
from PIL import Image

from .regions import crop, crop_grid
from .card_id import identify
from . import ocr
from .scryfall import load_index
from ..config import Config


# Number of card slots to scan in each zone strip. MTGO usually shows up to
# ~10-12 across; tune in YAML if your layout differs.
DEFAULT_SLOTS = {
    "my_hand": 7,
    "my_battlefield": 10,
    "opp_battlefield": 10,
    "stack": 4,
}


class Perceiver:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.index = load_index(Path(cfg.scryfall.cache_dir))

    def perceive(self, img: Image.Image) -> dict:
        regions = self.cfg.perception.regions
        out: dict = {"life": {}, "zones": {}, "phase": None}

        if "my_life" in regions:
            out["life"]["me"] = ocr.integer(crop(img, regions["my_life"]))
        if "opp_life" in regions:
            out["life"]["opp"] = ocr.integer(crop(img, regions["opp_life"]))

        if "phase_ribbon" in regions:
            out["phase"] = ocr.text(crop(img, regions["phase_ribbon"]), config="--psm 7")

        for zone, slots in DEFAULT_SLOTS.items():
            if zone not in regions:
                continue
            cards = []
            for slot_img in crop_grid(img, regions[zone], cols=slots):
                if _blank(slot_img):
                    continue
                m = identify(slot_img, self.index, threshold=14)
                cards.append(m["name"] if m else "?unknown")
            out["zones"][zone] = cards

        return out


def _blank(img: Image.Image, threshold: int = 5) -> bool:
    g = img.convert("L")
    lo, hi = g.getextrema()
    return (hi - lo) < threshold
