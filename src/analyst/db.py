import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .state import GameState, Event


SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    format TEXT,
    result TEXT
);

CREATE TABLE IF NOT EXISTS state_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    turn INTEGER,
    phase TEXT,
    active_player TEXT,
    state_json TEXT NOT NULL,
    FOREIGN KEY (game_id) REFERENCES games(id)
);
CREATE INDEX IF NOT EXISTS idx_snapshots_game_ts ON state_snapshots(game_id, ts);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    turn INTEGER,
    phase TEXT,
    type TEXT NOT NULL,
    actor TEXT,
    target TEXT,
    payload_json TEXT,
    FOREIGN KEY (game_id) REFERENCES games(id)
);
CREATE INDEX IF NOT EXISTS idx_events_game_ts ON events(game_id, ts);

CREATE TABLE IF NOT EXISTS frames (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT,
    ts TEXT NOT NULL,
    phash TEXT NOT NULL,
    path TEXT
);
"""


class DB:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def conn(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()

    def start_game(self, game_id: str, format: str | None = None) -> None:
        with self.conn() as c:
            c.execute(
                "INSERT OR IGNORE INTO games (id, started_at, format) VALUES (?, ?, ?)",
                (game_id, datetime.utcnow().isoformat(), format),
            )

    def end_game(self, game_id: str, result: str) -> None:
        with self.conn() as c:
            c.execute(
                "UPDATE games SET ended_at = ?, result = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), result, game_id),
            )

    def save_snapshot(self, state: GameState) -> None:
        with self.conn() as c:
            c.execute(
                """INSERT INTO state_snapshots
                   (game_id, ts, turn, phase, active_player, state_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    state.game_id,
                    datetime.utcnow().isoformat(),
                    state.turn,
                    state.phase,
                    state.active_player,
                    state.model_dump_json(),
                ),
            )

    def save_events(self, game_id: str, turn: int, phase: str, events: list[Event]) -> None:
        if not events:
            return
        ts = datetime.utcnow().isoformat()
        with self.conn() as c:
            c.executemany(
                """INSERT INTO events
                   (game_id, ts, turn, phase, type, actor, target, payload_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (game_id, ts, turn, phase, e.type, e.actor, e.target, json.dumps(e.payload))
                    for e in events
                ],
            )

    def latest_state(self, game_id: str) -> GameState | None:
        with self.conn() as c:
            row = c.execute(
                "SELECT state_json FROM state_snapshots WHERE game_id = ? ORDER BY id DESC LIMIT 1",
                (game_id,),
            ).fetchone()
            return GameState.model_validate_json(row["state_json"]) if row else None

    def save_frame(self, game_id: str | None, phash: str, path: str | None) -> None:
        with self.conn() as c:
            c.execute(
                "INSERT INTO frames (game_id, ts, phash, path) VALUES (?, ?, ?, ?)",
                (game_id, datetime.utcnow().isoformat(), phash, path),
            )
