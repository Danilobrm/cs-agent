from dataclasses import replace
from datetime import date, time

import pytest

from cs_agent.app import build_agent
from cs_agent.config import load_settings
from cs_agent.llm import ConfigError


@pytest.fixture
def settings(monkeypatch):
    for name in ("LLM_PROVIDER", "LLM_MODEL", "GEMINI_API_KEY", "OPENAI_API_KEY", "REFERENCE_DATE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("cs_agent.config.load_dotenv", lambda *_: None)
    return replace(load_settings(), llm_provider="ollama")


def test_build_agent_wires_everything(settings):
    agent = build_agent(settings, fixed_time=time(10, 0))
    assert agent.llm.provider == "ollama"
    assert agent.ctx.ref_date == date(2026, 3, 25)
    assert agent.ctx.now.time() == time(10, 0)
    assert len(agent.policy) > 1000


def test_build_agent_raises_config_error_without_key(settings):
    with pytest.raises(ConfigError):
        build_agent(replace(settings, llm_provider="gemini", gemini_api_key=None))
