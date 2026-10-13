"""Queue events from services. Honours tsl.yaml telemetry.enabled; never fails a command."""

from __future__ import annotations

from typing import Any

from tsl.core.errors import TslError
from tsl.core.runtime import Runtime


def emit(
    rt: Runtime, type_: str, body: dict[str, Any], run_id: str | None = None, enabled: bool = True
) -> None:
    if not enabled:
        return
    try:
        rt.outbox().enqueue(type_, body, run_id)
    except TslError:
        raise
    except Exception as exc:  # outbox trouble must not break the command (R-04)
        rt.warn(f"outbox unavailable: {type(exc).__name__}")


def flush(rt: Runtime, max_seconds: float) -> Any:
    def token(force: bool) -> str:
        return rt.identity().silent_token(force_refresh=force)

    return rt.outbox().flush(token, rt.insights.post_events, max_seconds)
