"""Run on the Windows PC. Captures MTGO at N fps, gates by perceptual hash, POSTs to server."""
import time
from io import BytesIO

import httpx
import imagehash
import mss
from PIL import Image

from .config import Config


def run(cfg: Config) -> None:
    last_hash = None
    interval = 1.0 / cfg.capture.fps
    with mss.mss() as sct, httpx.Client(timeout=30) as client:
        monitor = sct.monitors[cfg.capture.monitor]
        while True:
            t0 = time.time()
            shot = sct.grab(monitor)
            img = Image.frombytes("RGB", shot.size, shot.rgb)
            h = imagehash.phash(img)
            if last_hash is None or (h - last_hash) >= cfg.capture.phash_threshold:
                last_hash = h
                buf = BytesIO()
                img.save(buf, format="PNG")
                buf.seek(0)
                try:
                    client.post(
                        cfg.capture.server_url,
                        files={"image": ("frame.png", buf, "image/png")},
                        data={"phash": str(h)},
                    )
                except Exception as exc:
                    print(f"send failed: {exc}")
            sleep = interval - (time.time() - t0)
            if sleep > 0:
                time.sleep(sleep)
