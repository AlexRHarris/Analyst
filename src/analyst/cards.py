"""Optional card-name verification via Scryfall perceptual hashing.

The VLM names cards by reading them; phash is the one thing that beats it
on MTGO renders. If you build the index, the server cross-checks card
names against phash matches and corrects obvious misreadings.

Build:    analyst build-index --sets <set codes>
Disable:  delete data/scryfall/phash_index.pkl, or skip the build step.
"""
from __future__ import annotations

import json
import pickle
from pathlib import Path

import httpx
import imagehash
from PIL import Image


BULK_URL = "https://api.scryfall.com/bulk-data/default-cards"


def build_index(cache_dir: Path, sets: list[str] | None = None,
                max_cards: int | None = None) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    bulk_path = cache_dir / "default-cards.json"
    if not bulk_path.exists():
        with httpx.Client(timeout=120, follow_redirects=True) as c:
            meta = c.get(BULK_URL).json()
            with c.stream("GET", meta["download_uri"]) as r:
                r.raise_for_status()
                with open(bulk_path, "wb") as f:
                    for chunk in r.iter_bytes():
                        f.write(chunk)

    with open(bulk_path) as f:
        cards = json.load(f)
    if sets:
        cards = [c for c in cards if c.get("set") in sets]
    if max_cards:
        cards = cards[:max_cards]

    images_dir = cache_dir / "images"
    images_dir.mkdir(exist_ok=True)
    index: list[tuple[imagehash.ImageHash, dict]] = []
    with httpx.Client(timeout=30, follow_redirects=True) as c:
        for i, card in enumerate(cards):
            url = card.get("image_uris", {}).get("small") or (
                (card.get("card_faces") or [{}])[0].get("image_uris", {}).get("small")
            )
            if not url:
                continue
            cached = images_dir / f"{card['id']}.jpg"
            if not cached.exists():
                try:
                    r = c.get(url)
                    r.raise_for_status()
                    cached.write_bytes(r.content)
                except Exception:
                    continue
            try:
                index.append((imagehash.phash(Image.open(cached)),
                              {"id": card["id"], "name": card["name"], "set": card.get("set")}))
            except Exception:
                continue
            if i and i % 200 == 0:
                print(f"indexed {i}/{len(cards)}")

    out = cache_dir / "phash_index.pkl"
    with open(out, "wb") as f:
        pickle.dump(index, f)
    return out


def load_index(cache_dir: Path):
    p = cache_dir / "phash_index.pkl"
    if not p.exists():
        return None
    with open(p, "rb") as f:
        return pickle.load(f)


def best_match(img: Image.Image, index, threshold: int = 14) -> dict | None:
    if not index:
        return None
    h_n = imagehash.phash(img)
    h_r = imagehash.phash(img.rotate(90, expand=True))
    best, best_d, tapped = None, threshold + 1, False
    for ih, meta in index:
        dn = h_n - ih
        if dn < best_d:
            best, best_d, tapped = meta, dn, False
        dr = h_r - ih
        if dr < best_d:
            best, best_d, tapped = meta, dr, True
    if best is None:
        return None
    return {**best, "distance": best_d, "tapped": tapped}
