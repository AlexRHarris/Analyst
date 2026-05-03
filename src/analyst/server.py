"""Linux-side receiver. Gates frames, runs the VLM, diffs state, persists."""
from __future__ import annotations

import uuid
from io import BytesIO
from pathlib import Path

import imagehash
from fastapi import FastAPI, File, Form, UploadFile
from PIL import Image

from .config import Config
from .db import DB
from .differ import diff
from .state import GameState, PlayerState
from .vlm import perceive


def make_app(cfg: Config) -> FastAPI:
    app = FastAPI()
    data_dir = Path(cfg.server.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    db = DB(data_dir / "analyst.db")

    state_cache: dict[str, GameState] = {}
    current = {"game_id": None, "roi_hashes": None}

    def get_or_start_game() -> GameState:
        gid = current["game_id"]
        if gid is None:
            gid = str(uuid.uuid4())
            current["game_id"] = gid
            db.start_game(gid)
            state_cache[gid] = GameState(
                game_id=gid,
                players={"me": PlayerState(name="me"), "opp": PlayerState(name="opp")},
            )
        return state_cache[current["game_id"]]

    def roi_changed(img: Image.Image) -> bool:
        n = cfg.server.roi_grid
        w, h = img.size
        cw, rh = w // n, h // n
        hashes = []
        for r in range(n):
            for col in range(n):
                hashes.append(imagehash.phash(
                    img.crop((col * cw, r * rh, (col + 1) * cw, (r + 1) * rh))
                ))
        prev = current["roi_hashes"]
        current["roi_hashes"] = hashes
        if prev is None:
            return True
        return any((h - p) >= cfg.server.roi_threshold for h, p in zip(hashes, prev))

    @app.post("/frame")
    async def frame(image: UploadFile = File(...), phash: str = Form(...)):
        raw = await image.read()
        img = Image.open(BytesIO(raw)).convert("RGB")

        if not roi_changed(img):
            return {"ok": True, "skipped": "roi_unchanged"}

        prior = get_or_start_game()
        try:
            new_state, extra_events = perceive(cfg.llm, img, prior)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        events = diff(prior, new_state) + extra_events
        state_cache[new_state.game_id] = new_state
        db.save_snapshot(new_state)
        db.save_events(new_state.game_id, new_state.turn, new_state.phase, events)
        db.save_frame(new_state.game_id, phash, None)

        if any(e.type == "GAME_END" for e in events):
            db.end_game(
                new_state.game_id,
                result=str(events[-1].payload.get("result", "unknown")),
            )
            current["game_id"] = None

        return {
            "ok": True,
            "events": [e.model_dump() for e in events],
            "turn": new_state.turn,
            "phase": new_state.phase,
        }

    @app.post("/game/end")
    def end_game(result: str = "unknown"):
        gid = current["game_id"]
        if gid:
            db.end_game(gid, result)
            current["game_id"] = None
        return {"ok": True}

    @app.get("/health")
    def health():
        return {"ok": True, "model": cfg.llm.model}

    return app
