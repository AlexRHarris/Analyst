from datetime import datetime
from pydantic import BaseModel, Field


class Card(BaseModel):
    name: str
    scryfall_id: str | None = None
    counters: dict[str, int] = Field(default_factory=dict)
    tapped: bool = False
    attached_to: str | None = None


class PlayerState(BaseModel):
    name: str
    life: int = 20
    library_count: int = 60
    hand_count: int = 7
    hand: list[Card] = Field(default_factory=list)
    battlefield: list[Card] = Field(default_factory=list)
    graveyard: list[Card] = Field(default_factory=list)
    exile: list[Card] = Field(default_factory=list)
    mana_pool: dict[str, int] = Field(default_factory=dict)


class GameState(BaseModel):
    game_id: str
    turn: int = 1
    phase: str = "untap"
    active_player: str = "me"
    priority: str = "me"
    stack: list[Card] = Field(default_factory=list)
    players: dict[str, PlayerState] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=datetime.utcnow)


class Event(BaseModel):
    type: str
    actor: str | None = None
    target: str | None = None
    payload: dict = Field(default_factory=dict)
