from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


Phase = Literal[
    "untap",
    "upkeep",
    "draw",
    "precombat_main",
    "beginning_of_combat",
    "declare_attackers",
    "declare_blockers",
    "combat_damage",
    "first_strike_damage",
    "end_of_combat",
    "postcombat_main",
    "end_step",
    "cleanup",
]


# Counter types we track explicitly. Anything else goes under "other_<name>".
COUNTER_TYPES = {
    "+1/+1", "-1/-1",
    "loyalty", "charge", "time", "lore", "level", "quest",
    "shield", "stun", "finality", "indestructible",
    "brick", "dream", "ki", "fade", "vanishing",
}

# Counter-like values stored on the player rather than on a permanent.
PLAYER_COUNTER_TYPES = {"poison", "energy", "experience", "ticket", "rad", "manifestation"}


class Card(BaseModel):
    name: str
    scryfall_id: str | None = None
    instance_id: str | None = None  # stable across frames so events can refer to it
    tapped: bool = False
    summoning_sick: bool = False
    face_down: bool = False
    transformed: bool = False  # showing the back face / night side
    is_token: bool = False
    is_copy: bool = False
    counters: dict[str, int] = Field(default_factory=dict)
    attached_to: str | None = None  # instance_id of the permanent this is attached to
    attachments: list[str] = Field(default_factory=list)  # instance_ids attached to this
    damage_marked: int = 0
    power: int | None = None
    toughness: int | None = None
    loyalty: int | None = None  # planeswalkers
    saga_chapter: int | None = None
    class_level: int | None = None
    targets: list[str] = Field(default_factory=list)  # for stack items / arrows


class ManaPool(BaseModel):
    W: int = 0
    U: int = 0
    B: int = 0
    R: int = 0
    G: int = 0
    C: int = 0


class Battlefield(BaseModel):
    lands: list[Card] = Field(default_factory=list)
    creatures: list[Card] = Field(default_factory=list)
    other: list[Card] = Field(default_factory=list)  # artifacts, enchantments, planeswalkers, tokens not creatures


class PlayerState(BaseModel):
    name: str
    life: int = 20
    poison: int = 0
    energy: int = 0
    experience: int = 0
    rad: int = 0
    library_count: int = 60
    hand_count: int = 7
    graveyard_count: int = 0
    exile_count: int = 0
    sideboard_count: int | None = None
    hand: list[Card] = Field(default_factory=list)  # contents only known for "me"
    battlefield: Battlefield = Field(default_factory=Battlefield)
    graveyard: list[Card] = Field(default_factory=list)
    exile: list[Card] = Field(default_factory=list)
    command_zone: list[Card] = Field(default_factory=list)
    mana_pool: ManaPool = Field(default_factory=ManaPool)
    is_active: bool = False
    has_priority: bool = False
    is_monarch: bool = False
    has_initiative: bool = False
    ring_temptation_level: int = 0
    dungeon: str | None = None
    dungeon_room: int = 0
    day_night: Literal["day", "night"] | None = None
    emblems: list[str] = Field(default_factory=list)
    extra_counters: dict[str, int] = Field(default_factory=dict)
    turn_timer_seconds: int | None = None


class StackItem(BaseModel):
    instance_id: str | None = None
    source: str
    controller: str
    is_ability: bool = False
    targets: list[str] = Field(default_factory=list)
    x_value: int | None = None


class Combat(BaseModel):
    attackers: list[str] = Field(default_factory=list)  # instance_ids of attacking creatures
    attacking_target: dict[str, str] = Field(default_factory=dict)  # attacker -> "opp" | planeswalker_id | battle_id
    blocks: dict[str, list[str]] = Field(default_factory=dict)  # blocker_id -> [attacker_ids]
    damage_order: dict[str, list[str]] = Field(default_factory=dict)  # attacker -> ordered blockers


class Dialog(BaseModel):
    type: Literal[
        "mulligan", "keep_or_mull", "scry", "surveil", "fateseal",
        "target", "choose_mode", "x_cost", "discard", "sideboard",
        "win", "loss", "draw_game", "concede_prompt", "other",
    ]
    prompt: str | None = None
    options: list[str] = Field(default_factory=list)


class GameState(BaseModel):
    game_id: str
    format: str | None = None
    game_number: int = 1
    match_score: tuple[int, int] = (0, 0)  # (me_wins, opp_wins)
    turn: int = 1
    phase: Phase = "untap"
    active_player: str = "me"
    priority: str = "me"
    stack: list[StackItem] = Field(default_factory=list)
    combat: Combat | None = None
    players: dict[str, PlayerState] = Field(default_factory=dict)
    pending_dialog: Dialog | None = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    last_perception_ts: datetime | None = None


# Canonical event vocabulary. The reasoning model MUST emit one of these for `type`.
EVENT_TYPES = {
    # Game / match flow
    "GAME_START", "GAME_END", "MATCH_END",
    "MULLIGAN", "KEEP", "PARIS_BOTTOM",
    # Turn / phase
    "TURN_START", "TURN_END", "PHASE_CHANGE", "STEP_CHANGE", "PRIORITY_PASS",
    # Card movement
    "DRAW", "DISCARD", "MILL", "EXILE", "RETURN_TO_HAND", "RETURN_TO_LIBRARY",
    "TUTOR", "SHUFFLE", "SCRY", "SURVEIL", "FATESEAL",
    # Casting / stack
    "CAST", "ACTIVATE_ABILITY", "TRIGGER", "RESOLVE", "COUNTERED", "COPIED", "FIZZLED",
    # Battlefield
    "ENTERS_BATTLEFIELD", "LEAVES_BATTLEFIELD", "DIES", "SACRIFICED", "DESTROYED",
    "CREATED_TOKEN", "EXILE_FROM_PLAY",
    # Combat
    "ATTACKERS_DECLARED", "BLOCKERS_DECLARED", "DAMAGE_ASSIGNED", "COMBAT_DAMAGE_DEALT",
    # State changes
    "TAP", "UNTAP", "TRANSFORM", "FLIP", "MORPH_FLIP", "ATTACH", "UNATTACH",
    "BECOME_MONARCH", "TAKE_INITIATIVE", "RING_TEMPT", "VENTURE_DUNGEON",
    "COMPLETE_DUNGEON", "DAY_NIGHT_FLIP", "EMBLEM_CREATED",
    # Counters
    "COUNTER_ADD", "COUNTER_REMOVE",
    # Player resources
    "LIFE_GAIN", "LIFE_LOSS", "POISON_GAIN", "POISON_LOSS",
    "ENERGY_GAIN", "ENERGY_SPEND", "EXP_GAIN", "RAD_GAIN", "RAD_LOSS",
    "MANA_ADD", "MANA_SPEND",
    # Misc
    "SAGA_CHAPTER", "CLASS_LEVEL_UP", "PLANESWALK", "DUNGEON_ROOM",
    "DICE_ROLL", "COIN_FLIP",
}


class Event(BaseModel):
    type: str
    actor: str | None = None
    target: str | None = None
    payload: dict = Field(default_factory=dict)
