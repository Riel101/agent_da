"""Time helpers.

Agenda reminder times are stored as *local wall time* plus an IANA timezone, so
the UTC fire time must be recomputed for each date (a fixed UTC offset would
drift across daylight-saving transitions).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

UTC_ZONE = UTC


def resolve_timezone(name: str | None, fallback: str = "UTC") -> ZoneInfo:
    for candidate in (name, fallback):
        if not candidate:
            continue
        try:
            return ZoneInfo(candidate)
        except (ZoneInfoNotFoundError, ValueError, KeyError):
            continue
    return ZoneInfo("UTC")


def local_now(tz_name: str | None) -> datetime:
    return datetime.now(resolve_timezone(tz_name))


def local_today(tz_name: str | None) -> date:
    return local_now(tz_name).date()


def to_utc_naive(value: datetime) -> datetime:
    """Normalise to UTC. SQLite returns naive datetimes; assume UTC for those."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def utc_now() -> datetime:
    return datetime.now(UTC)


def combine_local(date_: date, at: time, tz_name: str | None) -> datetime:
    """Local wall-clock datetime -> UTC datetime."""
    tz = resolve_timezone(tz_name)
    local_dt = datetime.combine(date_, at, tzinfo=tz)
    return local_dt.astimezone(UTC)


def add_days(value: date, days: int) -> date:
    return value + timedelta(days=days)


def day_diff(later: date, earlier: date) -> int:
    return (later - earlier).days


def iso_week_key(value: date) -> str:
    year, week, _ = value.isocalendar()
    return f"{year}-W{week:02d}"


def describe_local_time(tz_name: str | None) -> str:
    now = local_now(tz_name)
    offset = now.utcoffset()
    if offset is None:
        return tz_name or "UTC"
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    hours, minutes = divmod(abs(total_minutes), 60)
    return f"{tz_name or 'UTC'} (UTC{sign}{hours:02d}:{minutes:02d})"
