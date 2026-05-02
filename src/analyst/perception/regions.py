from PIL import Image


def crop(img: Image.Image, box: list[int]) -> Image.Image:
    return img.crop(tuple(box))


def crop_grid(img: Image.Image, box: list[int], cols: int, rows: int = 1) -> list[Image.Image]:
    x0, y0, x1, y1 = box
    cw = (x1 - x0) // cols
    rh = (y1 - y0) // rows
    out = []
    for r in range(rows):
        for c in range(cols):
            out.append(img.crop((x0 + c * cw, y0 + r * rh, x0 + (c + 1) * cw, y0 + (r + 1) * rh)))
    return out
