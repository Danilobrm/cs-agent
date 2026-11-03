import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from cs_agent.tools.serialize import to_json_safe


@dataclass(frozen=True)
class Box:
    price: Decimal
    day: date


def test_scalars():
    assert to_json_safe(Decimal("1234.5")) == "R$ 1.234,50"
    assert to_json_safe(date(2026, 3, 5)) == "05/03/2026"
    assert to_json_safe(datetime(2026, 3, 5, 9, 30)) == "05/03/2026 09:30"
    assert to_json_safe(None) is None
    assert to_json_safe(7) == 7


def test_nested_containers_and_dataclass():
    obj = {"box": Box(Decimal("10"), date(2026, 1, 2)), "list": (Decimal("1"), [date(2026, 1, 3)])}
    out = to_json_safe(obj)
    assert out == {
        "box": {"price": "R$ 10,00", "day": "02/01/2026"},
        "list": ["R$ 1,00", ["03/01/2026"]],
    }
    json.dumps(out)


def test_sets_become_sorted_lists():
    assert to_json_safe({3, 1, 2}) == [1, 2, 3]
