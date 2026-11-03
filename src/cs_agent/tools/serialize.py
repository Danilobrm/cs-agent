"""Turn tool results into JSON-safe values with display formatting."""

from dataclasses import fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from cs_agent.money import format_brl


def to_json_safe(obj: Any) -> Any:
    """Recursively convert dataclasses, containers, Decimal and dates for the LLM.

    Decimal becomes "R$ 1.234,56", date "DD/MM/YYYY", datetime "DD/MM/YYYY HH:MM".
    """
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_json_safe(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, dict):
        return {str(k): to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [to_json_safe(v) for v in obj]
    if isinstance(obj, set | frozenset):
        return sorted(to_json_safe(v) for v in obj)
    if isinstance(obj, Decimal):
        return format_brl(obj)
    if isinstance(obj, datetime):  # before date: datetime is a date subclass
        return obj.strftime("%d/%m/%Y %H:%M")
    if isinstance(obj, date):
        return obj.strftime("%d/%m/%Y")
    return obj
