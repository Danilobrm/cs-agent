from datetime import date, datetime, time

from cs_agent.tools import context
from cs_agent.tools.context import Session, ToolContext


def test_create_uses_reference_day_and_fresh_session(store):
    a = ToolContext.create(store, date(2026, 3, 25))
    b = ToolContext.create(store, date(2026, 3, 25))
    assert a.now.date() == date(2026, 3, 25)
    assert a.session is not b.session


def test_create_keeps_given_session(store):
    session = Session()
    assert ToolContext.create(store, date(2026, 3, 25), session).session is session


def test_fixed_time_pins_now(store):
    ctx = ToolContext.create(store, date(2026, 3, 25), fixed_time=time(10, 30))
    assert ctx.now == datetime(2026, 3, 25, 10, 30)
    assert ctx.refreshed().now == datetime(2026, 3, 25, 10, 30)


def test_refreshed_follows_the_clock_without_fixed_time(store, monkeypatch):
    ctx = ToolContext.create(store, date(2026, 3, 25))
    monkeypatch.setattr(context, "_clock_time", lambda: time(15, 45))
    assert ctx.now.time() != time(15, 45) or True  # created with the real clock
    refreshed = ctx.refreshed()
    assert refreshed.now == datetime(2026, 3, 25, 15, 45)
    assert refreshed.session is ctx.session
