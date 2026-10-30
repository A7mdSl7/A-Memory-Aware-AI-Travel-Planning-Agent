from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

@dataclass(frozen=True)
class Settings:
    database_path: Path
    demo_mode: bool = True

def get_settings() -> Settings:
    raw = Path(os.getenv("DATABASE_PATH", "data/memorylab.db"))
    db = raw if raw.is_absolute() else ROOT / raw
    return Settings(
        database_path=db,
        demo_mode=os.getenv("DEMO_MODE", "true").lower() in {"1", "true", "yes", "on"},
    )
