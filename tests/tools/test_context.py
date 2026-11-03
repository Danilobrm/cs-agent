from datetime import date

from cs_agent.tools.context import Session, ToolContext


def test_create_uses_reference_day_and_fresh_session(store):
    a = ToolContext.create(store, date(2026, 3, 25))
    b = ToolContext.create(store, date(2026, 3, 25))
    assert a.now.date() == date(2026, 3, 25)
    assert a.session is not b.session


def test_create_keeps_given_session(store):
    session = Session()
    assert ToolContext.create(store, date(2026, 3, 25), session).session is session
