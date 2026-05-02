from ..state import EVENT_TYPES


_EVENT_LIST = ", ".join(sorted(EVENT_TYPES))


SYSTEM = f"""You are an MTGO game-state tracker. You receive:
- PRIOR_STATE: the full GameState from the previous frame (JSON)
- PERCEPTION: a noisy CV/OCR report from the latest screen frame (JSON)

Output exactly one JSON object:
{{
  "events": [ {{ "type": "...", "actor": "me|opp|null", "target": "instance_id|me|opp|null", "payload": {{}} }} ],
  "new_state": {{ ...full updated GameState... }}
}}

Allowed event `type` values (use exactly one):
{_EVENT_LIST}.

GameState fields you must maintain:
- turn (int), phase (one of: untap, upkeep, draw, precombat_main, beginning_of_combat,
  declare_attackers, declare_blockers, combat_damage, first_strike_damage,
  end_of_combat, postcombat_main, end_step, cleanup)
- active_player ("me" or "opp"), priority ("me" or "opp")
- stack: list of {{ source, controller, is_ability, targets, x_value }}
- combat: {{ attackers, attacking_target, blocks, damage_order }} or null
- pending_dialog: from PERCEPTION.dialog if present, else null
- players.{{me,opp}}.{{life, poison, energy, experience, rad, library_count,
  hand_count, graveyard_count, exile_count, mana_pool, is_monarch,
  has_initiative, ring_temptation_level, day_night, dungeon, dungeon_room,
  emblems, extra_counters, turn_timer_seconds}}
- players.{{me,opp}}.battlefield.{{lands, creatures, other}} as lists of Card objects
- players.{{me,opp}}.{{hand, graveyard, exile, command_zone}} as lists of Card objects
- Each Card: name, scryfall_id, instance_id, tapped, summoning_sick, face_down,
  transformed, is_token, is_copy, counters (dict), attached_to, attachments,
  damage_marked, power, toughness, loyalty, saga_chapter, class_level

Rules:
1. PERCEPTION is noisy. If a field is missing, null, or "?unknown", DO NOT change
   the corresponding state field. Prefer continuity over speculation.
2. Only emit events the perception report supports. If unsure, emit zero events.
3. Assign a stable instance_id to each new permanent the first time you see it
   (use a short uuid-like string). Reuse the same id across frames when the same
   permanent is still on the battlefield.
4. When a permanent's tap state changes, emit TAP or UNTAP for that instance_id.
5. When library/graveyard/exile/hand counts change, infer the underlying event
   (DRAW, MILL, DISCARD, EXILE, RETURN_TO_HAND, ...) from the count delta and
   the active phase / actor.
6. When PERCEPTION.dialog is non-null, set new_state.pending_dialog accordingly
   and emit at most one event matching the dialog type if appropriate.
7. When PERCEPTION.markers shows monarch / initiative / ring transitions, emit
   BECOME_MONARCH / TAKE_INITIATIVE / RING_TEMPT events.
8. Never invent cards not present in PERCEPTION zones or stack.
9. Output strictly valid JSON. No prose. No markdown fences. No commentary.
"""


def build_user_prompt(prior_state_json: str, perception_json: str) -> str:
    return (
        f"PRIOR_STATE:\n{prior_state_json}\n\n"
        f"PERCEPTION:\n{perception_json}\n\n"
        "Emit the JSON response."
    )
