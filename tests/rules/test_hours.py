from datetime import datetime

import pytest

from cs_agent.rules.hours import is_open, next_opening

# 2026-03-23 is a Monday.
MON, FRI, SAT, SUN = (datetime(2026, 3, d, 0, 0) for d in (23, 27, 28, 29))


def at(day, hour, minute=0):
    return day.replace(hour=hour, minute=minute)


def test_friday_17_59_open_and_18_00_closed():
    assert is_open(at(FRI, 17, 59))
    assert not is_open(at(FRI, 18, 0))


def test_opening_time_is_inclusive():
    assert not is_open(at(MON, 8, 59))
    assert is_open(at(MON, 9, 0))


def test_saturday_closes_at_13():
    assert is_open(at(SAT, 12, 59))
    assert not is_open(at(SAT, 13, 0))


def test_sunday_closed_all_day():
    assert not any(is_open(at(SUN, h)) for h in range(24))


def test_next_opening_when_open_is_now():
    now = at(MON, 10, 30)
    assert next_opening(now) == now


def test_saturday_13_00_next_opening_is_monday_09_00():
    assert next_opening(at(SAT, 13, 0)) == datetime(2026, 3, 30, 9, 0)


def test_sunday_next_opening_is_monday():
    assert next_opening(at(SUN, 12, 0)) == datetime(2026, 3, 30, 9, 0)


def test_before_opening_same_day():
    assert next_opening(at(MON, 7, 15)) == at(MON, 9, 0)
    assert next_opening(at(SAT, 8, 0)) == at(SAT, 9, 0)


def test_after_closing_goes_to_next_day():
    assert next_opening(at(MON, 18, 0)) == datetime(2026, 3, 24, 9, 0)
    assert next_opening(at(FRI, 18, 0)) == datetime(2026, 3, 28, 9, 0)  # Saturday


@pytest.mark.parametrize("dt", [at(FRI, 18, 0), at(SAT, 13, 0), at(SUN, 3, 0)])
def test_next_opening_is_always_open(dt):
    assert is_open(next_opening(dt))
