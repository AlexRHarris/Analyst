"""Tap-state detection via rotated phash.

A tapped MTGO card is the same image rotated 90° clockwise. We hash both the
slot image and a counter-rotated copy against the Scryfall index, and pick the
better match. If the rotated form wins, the card was tapped.
"""
import imagehash
from PIL import Image


def identify_with_tap(img: Image.Image, index, threshold: int = 14) -> dict | None:
    if not index:
        return None
    h_normal = imagehash.phash(img)
    h_rot = imagehash.phash(img.rotate(90, expand=True))
    best_n, best_n_d = _best(h_normal, index)
    best_r, best_r_d = _best(h_rot, index)

    if best_n is None and best_r is None:
        return None
    if best_r is not None and (best_n is None or best_r_d < best_n_d):
        if best_r_d > threshold:
            return None
        return {**best_r, "distance": best_r_d, "tapped": True}
    if best_n_d > threshold:
        return None
    return {**best_n, "distance": best_n_d, "tapped": False}


def _best(h, index):
    best, best_d = None, 1_000
    for ih, meta in index:
        d = h - ih
        if d < best_d:
            best, best_d = meta, d
    return best, best_d
