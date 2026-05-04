"""Run on the Windows PC. Captures MTGO at N fps, gates by perceptual hash, POSTs to server.

POSTs are fired in background threads so a slow VLM call on the server side
doesn't stall the capture loop. Frames are downscaled to JPEG before sending
to keep body size small (~200KB vs ~3MB raw PNG) — large multipart uploads
can stall on some LAN configurations.
"""
import threading
import time
from io import BytesIO

import httpx
import imagehash
import mss
from PIL import Image

from .config import Config


REQUEST_TIMEOUT_SECONDS = 120
MAX_INFLIGHT = 2
SEND_LONG_EDGE = 1280       # downscale long edge before sending
JPEG_QUALITY = 85


def _resize(img: Image.Image, long_edge: int) -> Image.Image:
    w, h = img.size
    if max(w, h) <= long_edge:
        return img
    scale = long_edge / max(w, h)
    return img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)


def run(cfg: Config) -> None:
    last_hash = None
    interval = 1.0 / cfg.capture.fps
    inflight = {"n": 0}
    inflight_lock = threading.Lock()
    seq = {"n": 0}

    def send(payload: bytes, phash_str: str, n: int) -> None:
        try:
            print(f"#{n} POST {len(payload)}B -> {cfg.capture.server_url}", flush=True)
            t0 = time.time()
            with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                r = client.post(
                    cfg.capture.server_url,
                    files={"image": ("frame.jpg", payload, "image/jpeg")},
                    data={"phash": phash_str},
                )
            dt = (time.time() - t0) * 1000
            if r.status_code >= 400:
                print(f"#{n} <- {r.status_code} ({dt:.0f}ms): {r.text[:200]}", flush=True)
            else:
                print(f"#{n} <- {r.status_code} ({dt:.0f}ms): {r.text[:200]}", flush=True)
        except Exception as exc:
            print(f"#{n} send failed: {exc}", flush=True)
        finally:
            with inflight_lock:
                inflight["n"] -= 1

    with mss.mss() as sct:
        monitor = sct.monitors[cfg.capture.monitor]
        print(
            f"capturing monitor {cfg.capture.monitor} "
            f"{monitor['width']}x{monitor['height']} @ {cfg.capture.fps}fps "
            f"-> {cfg.capture.server_url}",
            flush=True,
        )
        while True:
            t0 = time.time()
            shot = sct.grab(monitor)
            img = Image.frombytes("RGB", shot.size, shot.rgb)
            h = imagehash.phash(img)

            if last_hash is None or (h - last_hash) >= cfg.capture.phash_threshold:
                last_hash = h
                with inflight_lock:
                    busy = inflight["n"] >= MAX_INFLIGHT
                    if not busy:
                        inflight["n"] += 1
                        seq["n"] += 1
                        n = seq["n"]
                if busy:
                    print("server busy, dropping frame", flush=True)
                else:
                    small = _resize(img, SEND_LONG_EDGE)
                    buf = BytesIO()
                    small.save(buf, format="JPEG", quality=JPEG_QUALITY)
                    threading.Thread(
                        target=send,
                        args=(buf.getvalue(), str(h), n),
                        daemon=True,
                    ).start()

            sleep = interval - (time.time() - t0)
            if sleep > 0:
                time.sleep(sleep)
