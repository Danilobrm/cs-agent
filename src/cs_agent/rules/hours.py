"""Store opening hours (Policy 2).

Mon-Fri 09:00-18:00, Sat 09:00-13:00, Sun closed. Known limitation: there is no holiday
calendar, so holidays (closed per the policy) are reported as open.
"""

from datetime import datetime, time, timedelta

_OPEN = time(9, 0)
# weekday() -> closing time; Monday is 0. Sunday (6) is absent: closed.
_CLOSE = {**dict.fromkeys(range(5), time(18, 0)), 5: time(13, 0)}


def is_open(dt: datetime) -> bool:
    """Open from the opening time (inclusive) until the closing time (exclusive)."""
    close = _CLOSE.get(dt.weekday())
    return close is not None and _OPEN <= dt.time() < close


def next_opening(dt: datetime) -> datetime:
    """First opening moment at or after `dt` (`dt` itself when the store is open)."""
    if is_open(dt):
        return dt
    day = dt
    # Today still counts if it is before opening time; otherwise start from tomorrow.
    if dt.weekday() in _CLOSE and dt.time() < _OPEN:
        return datetime.combine(dt.date(), _OPEN, tzinfo=dt.tzinfo)
    while True:
        day = day + timedelta(days=1)
        if day.weekday() in _CLOSE:
            return datetime.combine(day.date(), _OPEN, tzinfo=dt.tzinfo)
