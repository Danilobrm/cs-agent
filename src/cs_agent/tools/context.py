"""Per-conversation state and the objects every tool receives."""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from cs_agent.data import Store

MAX_FAILED_VERIFICATIONS = 3


@dataclass
class Session:
    """Mutable state of one conversation."""

    verified_customer_ids: set[int] = field(default_factory=set)
    failed_verifications: int = 0
    handoffs: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ToolContext:
    """What a tool needs: data, the simulated day and the session.

    `now` is REFERENCE_DATE combined with the real clock time: opening hours use the
    simulated day (so weekday checks are reproducible) and the real time of day.
    """

    store: Store
    ref_date: date
    now: datetime
    session: Session

    @classmethod
    def create(cls, store: Store, ref_date: date, session: Session | None = None) -> "ToolContext":
        now = datetime.combine(ref_date, datetime.now().time())
        return cls(store, ref_date, now, session if session is not None else Session())
