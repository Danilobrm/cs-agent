"""Application settings loaded from environment / .env."""

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REFERENCE_DATE = "2026-03-25"


def parse_reference_date(value: str | None) -> date:
    """Parse REFERENCE_DATE: ISO date, "today", or default when empty."""
    raw = (value or "").strip() or DEFAULT_REFERENCE_DATE
    if raw.lower() == "today":
        return date.today()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise ValueError(
            f"Invalid REFERENCE_DATE {raw!r}: use an ISO date (YYYY-MM-DD) or 'today'"
        ) from None


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    llm_model: str | None
    gemini_api_key: str | None
    openai_api_key: str | None
    ollama_base_url: str
    data_dir: Path
    reference_date: date


def load_settings() -> Settings:
    """Build Settings from the environment. API keys are not validated here."""
    load_dotenv(PROJECT_ROOT / ".env")
    env = os.environ.get
    data_dir = Path(env("DATA_DIR") or PROJECT_ROOT / "data")
    if not data_dir.is_absolute():
        data_dir = PROJECT_ROOT / data_dir
    return Settings(
        llm_provider=(env("LLM_PROVIDER") or "gemini").strip().lower(),
        llm_model=(env("LLM_MODEL") or "").strip() or None,
        gemini_api_key=env("GEMINI_API_KEY") or None,
        openai_api_key=env("OPENAI_API_KEY") or None,
        ollama_base_url=env("OLLAMA_BASE_URL") or "http://localhost:11434/v1",
        data_dir=data_dir,
        reference_date=parse_reference_date(env("REFERENCE_DATE")),
    )
