"""JSON logs, one object per line (OPS-02 §6). Never logs bodies, tokens or headers (§6.2)."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from app import __version__

SAFE_EXTRA = {
    "request_id",
    "route",
    "method",
    "status",
    "duration_ms",
    "caller",
    "token_kind",
    "events",
    "code",
    "job",
    "batch",
    "projected",
    "parked",
    "view",
}


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        out: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
            + "Z",
            "level": record.levelname.lower(),
            "service": self.service,
            "version": __version__,
            "msg": record.getMessage(),
        }
        for k in SAFE_EXTRA:
            if hasattr(record, k):
                out[k] = getattr(record, k)
        if record.exc_info and record.exc_info[0] is not None:
            out["exc_type"] = record.exc_info[0].__name__
        return json.dumps(out, separators=(",", ":"))


def setup(service: str, level: int = logging.INFO) -> None:
    root = logging.getLogger()
    for h in list(root.handlers):
        if getattr(h, "_insights", False):
            root.removeHandler(h)
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter(service))
    h._insights = True  # type: ignore[attr-defined]  # marker to make setup idempotent
    root.addHandler(h)
    root.setLevel(level)
    for noisy in ("uvicorn.access",):
        logging.getLogger(noisy).disabled = True


log = logging.getLogger("insights")
