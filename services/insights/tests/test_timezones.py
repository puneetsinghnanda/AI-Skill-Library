"""E16 /v1/me/home takes the browser's IANA zone; slim images ship no system zone database."""

from __future__ import annotations

import zoneinfo
from collections.abc import Iterator

import pytest


@pytest.fixture
def no_system_tzdb() -> Iterator[None]:
    # python:3.12-slim has no /usr/share/zoneinfo; only the tzdata package can answer
    zoneinfo.reset_tzpath(to=[])
    zoneinfo.ZoneInfo.clear_cache()
    try:
        yield
    finally:
        zoneinfo.reset_tzpath()
        zoneinfo.ZoneInfo.clear_cache()


@pytest.mark.parametrize(
    "tz", ["Asia/Kolkata", "Asia/Calcutta", "Europe/London", "America/New_York"]
)
def test_browser_zones_resolve_without_a_system_database(no_system_tzdb: None, tz: str) -> None:
    assert zoneinfo.ZoneInfo(tz).key == tz
