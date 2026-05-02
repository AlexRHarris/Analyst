"""Detect modal dialogs MTGO shows for prompts.

Heuristic: when MTGO is awaiting a player decision (mulligan, target, X cost,
scry/surveil, choose mode, sideboard, win/loss), the dialog region in the
center of the screen contains text + buttons against a darkened backdrop.

We OCR the prompt area and classify by keyword. If no recognizable dialog
keywords are present, return None.
"""
from PIL import Image
from . import ocr


KEYWORDS: dict[str, list[str]] = {
    "mulligan": ["mulligan", "to 6", "to 5", "to 4", "to 3"],
    "keep_or_mull": ["keep", "mulligan"],
    "scry": ["scry", "top of your library", "bottom"],
    "surveil": ["surveil"],
    "fateseal": ["fateseal"],
    "target": ["choose a target", "select a target", "target a"],
    "choose_mode": ["choose one", "choose two", "choose up to"],
    "x_cost": ["choose a value for x", "value of x"],
    "discard": ["discard a card", "discard cards"],
    "sideboard": ["sideboard", "submit deck"],
    "win": ["you win", "victory"],
    "loss": ["you lose", "defeat"],
    "draw_game": ["draw game"],
    "concede_prompt": ["concede"],
}


def detect_dialog(dialog_img: Image.Image) -> dict | None:
    text = ocr.text(dialog_img).lower()
    if not text:
        return None
    for dialog_type, keys in KEYWORDS.items():
        if any(k in text for k in keys):
            return {"type": dialog_type, "prompt": text[:400]}
    if len(text) > 30:
        return {"type": "other", "prompt": text[:400]}
    return None
