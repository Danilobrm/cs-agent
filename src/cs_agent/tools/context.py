"""Per-conversation state and the objects every tool receives."""

from dataclasses import dataclass, field, replace
from datetime import date, datetime, time
from typing import Any

from cs_agent.data import Store

MAX_FAILED_VERIFICATIONS = 3


def _clock_time() -> time:
    return datetime.now().time()


@dataclass
class Session:
    """Mutable state of one conversation."""

    verified_customer_ids: set[int] = field(default_factory=set)
    failed_verifications: int = 0
    handoffs: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ToolContext:
    """What a tool needs: data, the simulated day and the session.

    `now` is the reference date combined with the clock time: opening hours use the
    simulated day (so weekday checks are reproducible) and the real time of day, or
    `fixed_time` when set (transcripts and evals). Call `refreshed()` to move it forward.
    """

    store: Store
    ref_date: date
    now: datetime
    session: Session
    fixed_time: time | None = None

    @classmethod
    def create(
        cls,
        store: Store,
        ref_date: date,
        session: Session | None = None,
        fixed_time: time | None = None,
    ) -> "ToolContext":
        return cls(
            store,
            ref_date,
            _moment(ref_date, fixed_time),
            session if session is not None else Session(),
            fixed_time,
        )

    def refreshed(self) -> "ToolContext":
        """Same context with `now` recomputed (a no-op in effect when the time is fixed)."""
        return replace(self, now=_moment(self.ref_date, self.fixed_time))


def _moment(ref_date: date, fixed_time: time | None) -> datetime:
    return datetime.combine(ref_date, fixed_time or _clock_time())
