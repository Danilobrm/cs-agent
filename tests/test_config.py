from datetime import date

import pytest

from cs_agent.config import load_settings, parse_reference_date


def test_parse_iso():
    assert parse_reference_date("2026-01-31") == date(2026, 1, 31)


def test_parse_default_when_empty():
    assert parse_reference_date(None) == date(2026, 3, 25)
    assert parse_reference_date("") == date(2026, 3, 25)


def test_parse_today():
    assert parse_reference_date("today") == date.today()


def test_parse_invalid():
    with pytest.raises(ValueError, match="REFERENCE_DATE"):
        parse_reference_date("31/01/2026")


def test_load_settings_data_dir_is_project_relative(monkeypatch):
    monkeypatch.delenv("DATA_DIR", raising=False)
    s = load_settings()
    assert s.data_dir.is_absolute()
    assert (s.data_dir / "products.csv").exists()
