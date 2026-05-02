from pathlib import Path
import yaml
from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8765
    data_dir: str = "./data"


class CaptureConfig(BaseModel):
    server_url: str = "http://localhost:8765/frame"
    fps: float = 1.0
    phash_threshold: int = 5
    monitor: int = 1


class ScryfallConfig(BaseModel):
    cache_dir: str = "./data/scryfall"


class PerceptionConfig(BaseModel):
    regions: dict[str, list[int]] = Field(default_factory=dict)


class OCRConfig(BaseModel):
    tesseract_cmd: str = "tesseract"


class LLMConfig(BaseModel):
    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5:7b"
    temperature: float = 0.1


class Config(BaseModel):
    server: ServerConfig = ServerConfig()
    capture: CaptureConfig = CaptureConfig()
    scryfall: ScryfallConfig = ScryfallConfig()
    perception: PerceptionConfig = PerceptionConfig()
    ocr: OCRConfig = OCRConfig()
    llm: LLMConfig = LLMConfig()


def load(path: str | Path = "config/default.yaml") -> Config:
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    return Config(**data)
