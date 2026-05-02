"""Phase ribbon: split into N equal segments, return the name of the brightest one.

MTGO highlights the active phase icon. Segment-by-mean-brightness is a robust
heuristic that works without keeping per-set template images.
"""
import numpy as np
from PIL import Image


def detect_phase(ribbon: Image.Image, phase_order: list[str]) -> str | None:
    if not phase_order:
        return None
    arr = np.asarray(ribbon.convert("L"), dtype=np.float32)
    h, w = arr.shape
    n = len(phase_order)
    seg_w = w // n
    if seg_w == 0:
        return None
    means = [arr[:, i * seg_w : (i + 1) * seg_w].mean() for i in range(n)]
    return phase_order[int(np.argmax(means))]
