from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8765
    data_dir: str = "./data"
    # ROI gate: divide the frame into NxN cells and only call the VLM if any
    # cell's perceptual hash changed by more than threshold bits.
    roi_grid: int = 4
    roi_threshold: int = 4


class CaptureConfig(BaseModel):
    server_url: str = "http://localhost:8765/frame"
    fps: float = 1.0
    phash_threshold: int = 5
    monitor: int = 1


class LLMConfig(BaseModel):
    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5vl:7b"
    temperature: float = 0.1
    num_ctx: int = 8192


class ScryfallConfig(BaseModel):
    cache_dir: str = "./data/scryfall"


class Config(BaseModel):
    server: ServerConfig = ServerConfig()
    capture: CaptureConfig = CaptureConfig()
    llm: LLMConfig = LLMConfig()
    scryfall: ScryfallConfig = ScryfallConfig()


def load(path: str | Path = "config/default.yaml") -> Config:
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return Config(**data)
