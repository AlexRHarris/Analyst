"""Single VLM call per frame: image + compact prior-state summary -> new_state + extra_events.

Default model: qwen2.5vl:7b via Ollama (local). Swap via config.

We keep state extraction and event extraction in ONE call so the VLM can
correlate visual cues (e.g. a spell on the stack with arrows) with the
state it's reporting. Standard events (DRAW, LIFE_LOSS, ETB, ...) are
derived deterministically by `differ.py` after this returns.
"""
from __future__ import annotations

import base64
import json
from io import BytesIO
from typing import Any

import httpx
from PIL import Image

from .config import LLMConfig
from .state import GameState, Event


IMAGE_LONG_EDGE = 1024  # px — tuned to keep MTGO card text legible after JPEG


SYSTEM = """You analyze ONE screenshot from an MTGO (Magic: The Gathering Online) match.

Output strict JSON, no prose, no markdown:
{
  "new_state": { ...full GameState... },
  "extra_events": [ {"type":"...","actor":"me|opp|null","target":null,"payload":{}} ]
}

Populate new_state from what you can see. For fields you cannot see clearly,
copy them unchanged from PRIOR. Never invent. Card names exactly as printed.

GameState schema:
{
  "game_id": str (copy from PRIOR),
  "turn": int,
  "phase": one of [untap, upkeep, draw, precombat_main, beginning_of_combat,
                   declare_attackers, declare_blockers, combat_damage,
                   first_strike_damage, end_of_combat, postcombat_main,
                   end_step, cleanup],
  "active_player": "me" | "opp",
  "priority": "me" | "opp",
  "stack": [ {"source": str, "controller": "me"|"opp", "is_ability": bool,
              "targets": [str], "x_value": int|null} ],
  "combat": {"attackers":[id], "attacking_target":{id:target},
             "blocks":{blocker:[attacker]}, "damage_order":{}} | null,
  "pending_dialog": {"type":..., "prompt":..., "options":[]} | null,
  "players": {
    "me": <PlayerState>, "opp": <PlayerState>
  }
}
PlayerState:
{
  "name": "me"|"opp",
  "life": int, "poison": int, "energy": int, "experience": int, "rad": int,
  "library_count": int, "hand_count": int,
  "graveyard_count": int, "exile_count": int,
  "mana_pool": {"W":int,"U":int,"B":int,"R":int,"G":int,"C":int},
  "is_monarch": bool, "has_initiative": bool,
  "ring_temptation_level": int,
  "day_night": "day"|"night"|null,
  "hand": [Card],
  "battlefield": {"lands":[Card], "creatures":[Card], "other":[Card]},
  "graveyard":[Card], "exile":[Card], "command_zone":[Card]
}
Card:
{
  "name": str, "instance_id": str,
  "tapped": bool, "summoning_sick": bool, "transformed": bool,
  "counters": {"+1/+1":int, "loyalty":int, ...},
  "attached_to": str|null, "damage_marked": int,
  "power": int|null, "toughness": int|null, "loyalty": int|null,
  "saga_chapter": int|null, "class_level": int|null
}

Rules:
- instance_id: reuse the same id across frames for the same permanent.
  When PRIOR lists a battlefield_ids array, prefer those ids.
- Tapped = rotated 90 degrees.
- Opp's hand: each card is face-down; emit Card with name="" and a
  fresh instance_id. hand_count is the visible count.
- "+1/+1" counters: read the small white pip count near the card.
- Card names exactly as printed; do NOT correct typos or pluralize.

extra_events should ONLY include events NOT derivable from a state diff:
- {"type":"CAST", "actor":"me|opp", "target":null,
   "payload":{"source": "<card name>", "x": <int|null>}}
   when you see a spell newly placed on the stack
- {"type":"COUNTERED", "actor":"me|opp", "target":"<source name>"}
   when you see a counter spell resolve removing a stack item
- {"type":"ATTACKERS_DECLARED", "actor":"me|opp",
   "payload":{"attackers": [card names]}} when red attack arrows are visible
- {"type":"BLOCKERS_DECLARED", "actor":"me|opp",
   "payload":{"blocks": {"<blocker>":["<attacker>"]}}}
- {"type":"DICE_ROLL"|"COIN_FLIP", "actor":"me|opp",
   "payload":{"result": ...}} when a roll/flip overlay is shown
- {"type":"SCRY"|"SURVEIL"|"FATESEAL", "actor":"me|opp",
   "payload":{"count": int}} when the scry/surveil dialog is open
Do NOT emit DRAW, MILL, DISCARD, LIFE_GAIN/LOSS, ENTERS_BATTLEFIELD,
LEAVES_BATTLEFIELD, DIES, TAP, UNTAP, COUNTER_ADD/REMOVE, MANA_ADD/SPEND,
PHASE_CHANGE, TURN_START — these are derived from the state diff.

If the screen is not an active MTGO game (menu, deck builder, lobby),
return new_state unchanged from PRIOR and extra_events: [].

Output JSON only.
"""


def _resize(img: Image.Image, long_edge: int) -> Image.Image:
    w, h = img.size
    if max(w, h) <= long_edge:
        return img
    scale = long_edge / max(w, h)
    return img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)


def _compact_prior(prior: GameState) -> dict:
    def player_summary(p) -> dict:
        bf_ids = (
            [c.instance_id for c in p.battlefield.lands if c.instance_id]
            + [c.instance_id for c in p.battlefield.creatures if c.instance_id]
            + [c.instance_id for c in p.battlefield.other if c.instance_id]
        )
        return {
            "life": p.life, "poison": p.poison, "energy": p.energy,
            "library_count": p.library_count, "hand_count": p.hand_count,
            "graveyard_count": p.graveyard_count, "exile_count": p.exile_count,
            "mana_pool": p.mana_pool.model_dump(),
            "is_monarch": p.is_monarch, "has_initiative": p.has_initiative,
            "ring_temptation_level": p.ring_temptation_level,
            "day_night": p.day_night,
            "battlefield_ids": bf_ids,
        }

    me = prior.players.get("me")
    opp = prior.players.get("opp")
    return {
        "game_id": prior.game_id,
        "turn": prior.turn,
        "phase": prior.phase,
        "active_player": prior.active_player,
        "priority": prior.priority,
        "stack_size": len(prior.stack),
        "me": player_summary(me) if me else None,
        "opp": player_summary(opp) if opp else None,
    }


def warmup(cfg: LLMConfig) -> None:
    """One-shot ping to load the model into Ollama memory.

    Without this the first real frame pays a multi-minute cold start.
    Subsequent calls reuse the loaded weights (Ollama keeps models warm
    for ~5 minutes by default; bump OLLAMA_KEEP_ALIVE if your sessions
    are longer than that).
    """
    try:
        with httpx.Client(timeout=600) as c:
            c.post(
                f"{cfg.base_url.rstrip('/')}/api/chat",
                json={
                    "model": cfg.model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                    "options": {"num_predict": 1, "num_ctx": cfg.num_ctx},
                },
            )
    except Exception as exc:
        # Non-fatal: log and continue. The first /frame call will retry.
        print(f"[vlm.warmup] failed (non-fatal): {exc}")


def perceive(cfg: LLMConfig, frame: Image.Image, prior: GameState) -> tuple[GameState, list[Event]]:
    img = _resize(frame, IMAGE_LONG_EDGE)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode()

    user = "PRIOR:\n" + json.dumps(_compact_prior(prior)) + "\n\nReturn JSON."

    with httpx.Client(timeout=600) as c:
        r = c.post(
            f"{cfg.base_url.rstrip('/')}/api/chat",
            json={
                "model": cfg.model,
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": user, "images": [b64]},
                ],
                "format": "json",
                "stream": False,
                "options": {"temperature": cfg.temperature, "num_ctx": cfg.num_ctx},
            },
        )
        r.raise_for_status()
        raw = r.json()["message"]["content"]

    data: dict[str, Any] = json.loads(raw)
    new_state_data = data.get("new_state") or prior.model_dump(mode="json")
    new_state_data["game_id"] = prior.game_id  # never let the model rename the game
    new_state = GameState(**new_state_data)
    extra_events = [Event(**e) for e in data.get("extra_events", [])]
    return new_state, extra_events
