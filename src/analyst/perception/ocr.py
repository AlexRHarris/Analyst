import re
from PIL import Image
import pytesseract


def text(img: Image.Image, config: str = "") -> str:
    return pytesseract.image_to_string(img, config=config).strip()


def integer(img: Image.Image) -> int | None:
    s = pytesseract.image_to_string(
        img, config="--psm 7 -c tessedit_char_whitelist=0123456789"
    )
    m = re.search(r"\d+", s)
    return int(m.group()) if m else None
