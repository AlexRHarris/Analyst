"""Derive standard events from a (prior, new) GameState pair.

The VLM is responsible for state extraction; this module extracts events
deterministically. Anything that is a direct function of count/state
deltas lives here so the VLM doesn't need to invent it.
"""
from __future__ import annotations

from .state import GameState, PlayerState, Card, Event


def diff(prior: GameState, new: GameState) -> list[Event]:
    out: list[Event] = []

    if new.phase != prior.phase:
        out.append(Event(
            type="PHASE_CHANGE",
            payload={"from": prior.phase, "to": new.phase},
        ))
    if new.turn != prior.turn:
        out.append(Event(
            type="TURN_START",
            actor=new.active_player,
            payload={"turn": new.turn},
        ))
    if new.active_player != prior.active_player:
        out.append(Event(
            type="PRIORITY_PASS",
            actor=new.active_player,
            payload={"to_active": new.active_player},
        ))

    for who in ("me", "opp"):
        old_p = prior.players.get(who)
        new_p = new.players.get(who)
        if old_p is None or new_p is None:
            continue
        out.extend(_diff_player(who, old_p, new_p))

    return out


def _diff_player(who: str, old: PlayerState, new: PlayerState) -> list[Event]:
    ev: list[Event] = []

    # Resource scalars
    for field, gain_t, loss_t in [
        ("life",        "LIFE_GAIN",    "LIFE_LOSS"),
        ("poison",      "POISON_GAIN",  "POISON_LOSS"),
        ("energy",      "ENERGY_GAIN",  "ENERGY_SPEND"),
        ("experience",  "EXP_GAIN",     None),
        ("rad",         "RAD_GAIN",     "RAD_LOSS"),
    ]:
        d = getattr(new, field) - getattr(old, field)
        if d > 0:
            ev.append(Event(type=gain_t, actor=who, payload={"amount": d}))
        elif d < 0 and loss_t is not None:
            ev.append(Event(type=loss_t, actor=who, payload={"amount": -d}))

    # Library / hand / graveyard / exile zone-count deltas
    dlib = old.library_count - new.library_count
    dhand = new.hand_count - old.hand_count
    dgy = new.graveyard_count - old.graveyard_count
    dex = new.exile_count - old.exile_count

    if dlib > 0 and dhand >= dlib:
        ev.append(Event(type="DRAW", actor=who, payload={"count": dlib}))
    elif dlib > 0 and dgy >= dlib:
        ev.append(Event(type="MILL", actor=who, payload={"count": dlib}))
    elif dlib > 0 and dex >= dlib:
        ev.append(Event(type="EXILE", actor=who, payload={"count": dlib}))
    elif dlib > 0:
        ev.append(Event(type="TUTOR", actor=who, payload={"count": dlib}))

    if dhand < 0 and dgy > 0:
        ev.append(Event(type="DISCARD", actor=who, payload={"count": min(-dhand, dgy)}))

    # Mana pool
    for color in ("W", "U", "B", "R", "G", "C"):
        d = getattr(new.mana_pool, color) - getattr(old.mana_pool, color)
        if d > 0:
            ev.append(Event(type="MANA_ADD", actor=who,
                            payload={"color": color, "amount": d}))
        elif d < 0:
            ev.append(Event(type="MANA_SPEND", actor=who,
                            payload={"color": color, "amount": -d}))

    # Markers
    if new.is_monarch and not old.is_monarch:
        ev.append(Event(type="BECOME_MONARCH", actor=who))
    if new.has_initiative and not old.has_initiative:
        ev.append(Event(type="TAKE_INITIATIVE", actor=who))
    if new.ring_temptation_level > old.ring_temptation_level:
        ev.append(Event(type="RING_TEMPT", actor=who,
                        payload={"level": new.ring_temptation_level}))
    if new.day_night and old.day_night and new.day_night != old.day_night:
        ev.append(Event(type="DAY_NIGHT_FLIP", payload={"to": new.day_night}))

    # Battlefield card movement (by instance_id)
    old_ids = _bf_ids(old)
    new_ids = _bf_ids(new)
    new_bf = _bf_cards(new)
    old_bf = _bf_cards(old)

    for iid in new_ids - old_ids:
        c = new_bf[iid]
        ev.append(Event(type="ENTERS_BATTLEFIELD", actor=who, target=iid,
                        payload={"name": c.name, "is_token": c.is_token}))
    for iid in old_ids - new_ids:
        c = old_bf[iid]
        # Where did it go? Approximate by looking at zone-count deltas.
        if dgy > 0:
            t = "DIES" if c.power is not None else "LEAVES_BATTLEFIELD"
        elif dex > 0:
            t = "EXILE_FROM_PLAY"
        else:
            t = "LEAVES_BATTLEFIELD"
        ev.append(Event(type=t, actor=who, target=iid, payload={"name": c.name}))

    # Tap state changes for permanents present in both states
    for iid in new_ids & old_ids:
        if old_bf[iid].tapped != new_bf[iid].tapped:
            ev.append(Event(
                type="TAP" if new_bf[iid].tapped else "UNTAP",
                actor=who, target=iid,
                payload={"name": new_bf[iid].name},
            ))

    # Counter changes
    for iid in new_ids & old_ids:
        for k in set(new_bf[iid].counters) | set(old_bf[iid].counters):
            d = new_bf[iid].counters.get(k, 0) - old_bf[iid].counters.get(k, 0)
            if d > 0:
                ev.append(Event(type="COUNTER_ADD", actor=who, target=iid,
                                payload={"counter": k, "amount": d}))
            elif d < 0:
                ev.append(Event(type="COUNTER_REMOVE", actor=who, target=iid,
                                payload={"counter": k, "amount": -d}))

    return ev


def _bf_cards(p: PlayerState) -> dict[str, Card]:
    out: dict[str, Card] = {}
    for c in p.battlefield.lands + p.battlefield.creatures + p.battlefield.other:
        if c.instance_id:
            out[c.instance_id] = c
    return out


def _bf_ids(p: PlayerState) -> set[str]:
    return set(_bf_cards(p).keys())
