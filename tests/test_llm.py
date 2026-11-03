from datetime import date
from pathlib import Path

import pytest

from cs_agent.config import Settings
from cs_agent.llm import PROVIDERS, ConfigError, create_llm


def make_settings(**overrides) -> Settings:
    values = {
        "llm_provider": "gemini",
        "llm_model": None,
        "gemini_api_key": "g-key",
        "openai_api_key": "o-key",
        "ollama_base_url": "http://localhost:11434/v1",
        "data_dir": Path("data"),
        "reference_date": date(2026, 3, 25),
    }
    return Settings(**{**values, **overrides})


def test_gemini_defaults():
    llm = create_llm(make_settings())
    assert llm.provider == "gemini"
    assert llm.model == PROVIDERS["gemini"].default_model
    assert str(llm.client.base_url) == "https://generativelanguage.googleapis.com/v1beta/openai/"
    assert llm.client.api_key == "g-key"


def test_ollama_needs_no_key_and_uses_configured_url():
    llm = create_llm(
        make_settings(
            llm_provider="ollama", gemini_api_key=None, ollama_base_url="http://box:11434/v1"
        )
    )
    assert llm.model == "qwen2.5:7b"
    assert str(llm.client.base_url) == "http://box:11434/v1/"
    assert llm.client.api_key == "ollama"


def test_openai_uses_sdk_default_url():
    llm = create_llm(make_settings(llm_provider="openai"))
    assert str(llm.client.base_url) == "https://api.openai.com/v1/"
    assert llm.client.api_key == "o-key"


def test_timeout_and_retries():
    client = create_llm(make_settings()).client
    assert client.timeout == 30
    assert client.max_retries == 2


def test_model_override():
    assert create_llm(make_settings(llm_model="gemini-custom")).model == "gemini-custom"


def test_missing_gemini_key_explains_how_to_fix():
    with pytest.raises(ConfigError) as exc:
        create_llm(make_settings(gemini_api_key=None))
    message = str(exc.value)
    assert "GEMINI_API_KEY" in message
    assert "aistudio.google.com" in message
    assert "ollama" in message.lower()


def test_missing_openai_key():
    with pytest.raises(ConfigError, match="OPENAI_API_KEY"):
        create_llm(make_settings(llm_provider="openai", openai_api_key=None))


def test_unknown_provider_lists_options():
    with pytest.raises(ConfigError) as exc:
        create_llm(make_settings(llm_provider="claude"))
    assert "'claude'" in str(exc.value)
    for name in PROVIDERS:
        assert name in str(exc.value)
