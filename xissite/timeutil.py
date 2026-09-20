"""Timezone helpers.

SQLite has no timezone type, so every DateTime column comes back naive on
the next request even when it was written as an aware UTC value (and even
when declared DateTime(timezone=True)). Comparing or subtracting such a
value against datetime.now(timezone.utc) raises TypeError. Normalise DB
values through as_utc() before any arithmetic with utcnow().
"""

from datetime import datetime, timezone


def utcnow():
    """Aware current time in UTC."""
    return datetime.now(timezone.utc)


def as_utc(dt):
    """Return dt as an aware UTC datetime; naive values are assumed UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
