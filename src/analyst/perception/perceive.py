"""Orchestrate every detector over a single frame and emit one perception JSON.

The output is a flat dict the reasoning model consumes. We deliberately keep
the schema loose (raw lists, no enum validation) so the LLM has room to
reconcile noisy CV output against the prior state.
"""
from pathlib import Path
from PIL import Image

from .regions import crop, crop_grid
from .tap import identify_with_tap
from .counters import detect_card_counters
from .mana_pool import detect_mana_pool
from .stack import parse_stack
from .dialog import detect_dialog
from .phase import detect_phase
from .zones import count as zone_count
from .helpers import is_blank, mean_brightness
from .scryfall import load_index
from ..config import Config


# Default slot counts per zone if not overridden in YAML.
DEFAULT_SLOTS = {
    "opp_hand": 10,
    "opp_battlefield_lands": 12,
    "opp_battlefield_creatures": 12,
    "opp_battlefield_other": 10,
    "my_hand": 10,
    "my_battlefield_lands": 12,
    "my_battlefield_creatures": 12,
    "my_battlefield_other": 10,
    "stack": 6,
}

NUMERIC_BADGES = [
    "opp_life", "opp_poison", "opp_energy", "opp_experience",
    "opp_library_count", "opp_graveyard_count", "opp_exile_count",
    "opp_hand_count", "opp_turn_timer",
    "my_life", "my_poison", "my_energy", "my_experience",
    "my_library_count", "my_graveyard_count", "my_exile_count",
    "my_hand_count", "my_turn_timer",
]

PRESENCE_MARKERS = [
    "opp_monarch_marker", "opp_initiative_marker", "opp_ring_marker",
    "my_monarch_marker", "my_initiative_marker", "my_ring_marker",
]


class Perceiver:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.index = load_index(Path(cfg.scryfall.cache_dir))
        self._slots = {**DEFAULT_SLOTS, **cfg.perception.zone_slots}

    def perceive(self, img: Image.Image) -> dict:
        regions = self.cfg.perception.regions
        out: dict = {
            "phase": None,
            "priority": None,
            "active_player": None,
            "turn_indicator": None,
            "match_score": None,
            "counts": {"me": {}, "opp": {}},
            "mana_pool": {"me": {}, "opp": {}},
            "markers": {"me": {}, "opp": {}},
            "zones": {},
            "stack": [],
            "dialog": None,
            "day_night": {},
        }

        # Phase
        if "phase_ribbon" in regions and self.cfg.perception.phase_order:
            out["phase"] = detect_phase(
                crop(img, regions["phase_ribbon"]),
                self.cfg.perception.phase_order,
            )

        # Numeric badges
        for key in NUMERIC_BADGES:
            if key not in regions:
                continue
            prefix, _, field = key.partition("_")
            who = "me" if prefix == "my" else prefix
            out["counts"][who][field] = zone_count(crop(img, regions[key]))

        # Mana pools (config uses my_*/opp_* prefixes)
        for who, prefix in (("me", "my"), ("opp", "opp")):
            key = f"{prefix}_mana_pool"
            if key in regions:
                out["mana_pool"][who] = detect_mana_pool(crop(img, regions[key]))

        # Presence markers (monarch / initiative / ring)
        for key in PRESENCE_MARKERS:
            if key not in regions:
                continue
            prefix, _, rest = key.partition("_")
            who = "me" if prefix == "my" else prefix
            marker = rest.replace("_marker", "")
            present = mean_brightness(crop(img, regions[key])) > 30
            out["markers"][who][marker] = bool(present)

        # Day / night side (config uses my_*/opp_* prefixes)
        for who, prefix in (("me", "my"), ("opp", "opp")):
            key = f"{prefix}_day_night_marker"
            if key in regions:
                b = mean_brightness(crop(img, regions[key]))
                if b > 150:
                    out["day_night"][who] = "day"
                elif b > 30:
                    out["day_night"][who] = "night"

        # Visible card zones
        for zone, slots in self._slots.items():
            if zone == "stack" or zone not in regions:
                continue
            cards = []
            for slot_img in crop_grid(img, regions[zone], cols=slots):
                if is_blank(slot_img):
                    continue
                m = identify_with_tap(slot_img, self.index, threshold=14)
                card_record: dict = {
                    "name": m["name"] if m else "?unknown",
                    "tapped": (m or {}).get("tapped", False),
                    "scryfall_id": (m or {}).get("id"),
                }
                counters = detect_card_counters(slot_img)
                if counters:
                    card_record["counters"] = counters
                cards.append(card_record)
            out["zones"][zone] = cards

        # Stack
        if "stack" in regions:
            out["stack"] = parse_stack(
                crop(img, regions["stack"]),
                self.index,
                slots=self._slots.get("stack", 6),
            )

        # Dialog overlay
        if "dialog" in regions:
            out["dialog"] = detect_dialog(crop(img, regions["dialog"]))

        return out
