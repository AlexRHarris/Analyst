import imagehash
from PIL import Image


def identify(img: Image.Image, index, threshold: int = 12) -> dict | None:
    if not index:
        return None
    h = imagehash.phash(img)
    best, best_d = None, threshold + 1
    for ih, meta in index:
        d = h - ih
        if d < best_d:
            best, best_d = meta, d
    if best and best_d <= threshold:
        return {**best, "distance": best_d}
    return None
