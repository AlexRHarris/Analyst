import json

from ..state import GameState, Event
from .llm import Ollama
from .prompts import SYSTEM, build_user_prompt


def reason(llm: Ollama, prior: GameState, perception: dict) -> tuple[list[Event], GameState]:
    user = build_user_prompt(prior.model_dump_json(), json.dumps(perception))
    raw = llm.generate_json(SYSTEM, user)
    data = json.loads(raw)
    events = [Event(**e) for e in data.get("events", [])]
    new_state_data = data.get("new_state") or prior.model_dump()
    # Force the LLM-supplied state to keep the prior game_id — the reasoner
    # shouldn't be inventing identifiers, even if it tries.
    new_state_data["game_id"] = prior.game_id
    return events, GameState(**new_state_data)
