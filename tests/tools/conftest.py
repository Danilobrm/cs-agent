from datetime import date, datetime
from pathlib import Path

import pytest

from cs_agent.data import load_store
from cs_agent.tools.context import Session, ToolContext

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
REF_DATE = date(2026, 3, 25)  # a Wednesday
NOW = datetime(2026, 3, 25, 10, 0)


@pytest.fixture(scope="session")
def store():
    return load_store(DATA_DIR)


@pytest.fixture
def ctx(store):
    """Fresh session per test, fixed day and time."""
    return ToolContext(store, REF_DATE, NOW, Session())
