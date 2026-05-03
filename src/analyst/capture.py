"""Run on the Windows PC. Captures MTGO at N fps, gates by perceptual hash, POSTs to server.

POSTs are fired in background threads so a slow VLM call on the server side
doesn't stall the capture loop. If more than `max_inflight` requests are still
in flight, new frames are dropped — the ROI gate on the server side will
catch up when load eases.
"""
import threading
import time
from io import BytesIO

import httpx
import imagehash
import mss
from PIL import Image

from .config import Config


REQUEST_TIMEOUT_SECONDS = 300  # generous: covers cold-start VLM model load
MAX_INFLIGHT = 2


def run(cfg: Config) -> None:
    last_hash = None
    interval = 1.0 / cfg.capture.fps
    inflight = {"n": 0}
    inflight_lock = threading.Lock()

    def send(payload: bytes, phash_str: str) -> None:
        try:
            with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                r = client.post(
                    cfg.capture.server_url,
                    files={"image": ("frame.png", payload, "image/png")},
                    data={"phash": phash_str},
                )
                if r.status_code >= 400:
                    print(f"server {r.status_code}: {r.text[:200]}")
        except Exception as exc:
            print(f"send failed: {exc}")
        finally:
            with inflight_lock:
                inflight["n"] -= 1

    with mss.mss() as sct:
        monitor = sct.monitors[cfg.capture.monitor]
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
                if busy:
                    print("server busy, dropping frame")
                else:
                    buf = BytesIO()
                    img.save(buf, format="PNG")
                    threading.Thread(
                        target=send,
                        args=(buf.getvalue(), str(h)),
                        daemon=True,
                    ).start()

            sleep = interval - (time.time() - t0)
            if sleep > 0:
                time.sleep(sleep)
