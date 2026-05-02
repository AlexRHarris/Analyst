import uuid
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form
from PIL import Image

from .config import Config
from .db import DB
from .state import GameState, PlayerState
from .perception.perceive import Perceiver
from .reasoning.llm import Ollama
from .reasoning.reason import reason


def make_app(cfg: Config) -> FastAPI:
    app = FastAPI()
    data_dir = Path(cfg.server.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    db = DB(data_dir / "analyst.db")
    perceiver = Perceiver(cfg)
    llm = Ollama(cfg.llm.base_url, cfg.llm.model, cfg.llm.temperature)

    state_cache: dict[str, GameState] = {}
    current = {"game_id": None}

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

    @app.post("/frame")
    async def frame(image: UploadFile = File(...), phash: str = Form(...)):
        raw = await image.read()
        img = Image.open(BytesIO(raw))
        perception = perceiver.perceive(img)
        prior = get_or_start_game()
        try:
            events, new_state = reason(llm, prior, perception)
        except Exception as exc:
            return {"ok": False, "error": str(exc), "perception": perception}

        state_cache[new_state.game_id] = new_state
        db.save_snapshot(new_state)
        db.save_events(new_state.game_id, new_state.turn, new_state.phase, events)
        db.save_frame(new_state.game_id, phash, None)

        if any(e.type == "GAME_END" for e in events):
            db.end_game(new_state.game_id, result=str(events[-1].payload.get("result", "unknown")))
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
