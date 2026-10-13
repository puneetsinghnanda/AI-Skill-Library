"""Injectable clock. Tests pass a fake through the runtime, never an env var."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

Clock = Callable[[], datetime]


def system_clock() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def iso(dt: datetime) -> str:
    """ISO 8601 UTC with seconds and Z (SDD-07 §6.2 one spelling per instant)."""
    return dt.astimezone(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)


class FrozenClock:
    """A settable clock for tests and replays."""

    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kw: float) -> None:
        self.now = self.now + timedelta(**kw)
