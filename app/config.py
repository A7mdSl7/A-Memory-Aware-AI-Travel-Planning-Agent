from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

@dataclass(frozen=True)
class Settings:
    gemini_api_key: str | None
    gemini_model: str
    database_path: Path
    demo_mode: bool

def get_settings() -> Settings:
    raw = Path(os.getenv("DATABASE_PATH", "data/memorylab.db"))
    db = raw if raw.is_absolute() else ROOT / raw
    return Settings(os.getenv("GEMINI_API_KEY") or None, os.getenv("GEMINI_MODEL", "gemini-3.8-flash"), db, os.getenv("DEMO_MODE", "true").lower() in {"1", "true", "yes", "on"})
