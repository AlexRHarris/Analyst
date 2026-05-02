"""Download Scryfall bulk data and build a perceptual-hash index for card matching.

The index is a list of (phash, {id, name, set}) tuples we linearly scan at
runtime. ~80k cards is small enough that a bare list works (<10ms/lookup).
"""
import json
import pickle
from pathlib import Path

import httpx
import imagehash
from PIL import Image


BULK_URL = "https://api.scryfall.com/bulk-data/default-cards"


def download_bulk(cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    bulk_path = cache_dir / "default-cards.json"
    if bulk_path.exists():
        return bulk_path
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        meta = client.get(BULK_URL).json()
        url = meta["download_uri"]
        with client.stream("GET", url) as r:
            r.raise_for_status()
            with open(bulk_path, "wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)
    return bulk_path


def build_phash_index(
    cache_dir: Path,
    max_cards: int | None = None,
    sets: list[str] | None = None,
) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    bulk_path = download_bulk(cache_dir)
    index_path = cache_dir / "phash_index.pkl"
    images_dir = cache_dir / "images"
    images_dir.mkdir(exist_ok=True)

    with open(bulk_path) as f:
        cards = json.load(f)
    if sets:
        cards = [c for c in cards if c.get("set") in sets]
    if max_cards:
        cards = cards[:max_cards]

    index: list[tuple[imagehash.ImageHash, dict]] = []
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for i, card in enumerate(cards):
            img_url = card.get("image_uris", {}).get("small") or (
                (card.get("card_faces") or [{}])[0].get("image_uris", {}).get("small")
            )
            if not img_url:
                continue
            cached = images_dir / f"{card['id']}.jpg"
            if not cached.exists():
                try:
                    r = client.get(img_url)
                    r.raise_for_status()
                    cached.write_bytes(r.content)
                except Exception:
                    continue
            try:
                h = imagehash.phash(Image.open(cached))
                index.append((h, {"id": card["id"], "name": card["name"], "set": card.get("set")}))
            except Exception:
                continue
            if i and i % 200 == 0:
                print(f"indexed {i}/{len(cards)}")

    with open(index_path, "wb") as f:
        pickle.dump(index, f)
    return index_path


def load_index(cache_dir: Path) -> list[tuple[imagehash.ImageHash, dict]]:
    p = cache_dir / "phash_index.pkl"
    if not p.exists():
        return []
    with open(p, "rb") as f:
        return pickle.load(f)
