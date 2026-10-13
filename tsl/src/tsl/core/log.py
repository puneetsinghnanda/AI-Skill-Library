"""Structured JSON-lines logging with redaction (SDD-04 §9)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

JWT = re.compile(r"eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*")
PEM = re.compile(r"-----BEGIN [A-Z ]+-----.*?-----END [A-Z ]+-----", re.S)
SECRET_KEYS = ("token", "secret", "password", "key")


def redact(value: Any, key: str = "") -> Any:
    if any(s in key.lower() for s in SECRET_KEYS) and key not in ("key_id", "key_status"):
        return "[REDACTED]"
    if isinstance(value, str):
        return PEM.sub("[REDACTED:pem]", JWT.sub("[REDACTED:jwt]", value))
    if isinstance(value, dict):
        return {k: redact(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, key) for v in value]
    return value


def append_line(
    path: Path, record: dict[str, Any], max_bytes: int = 10 * 1024 * 1024, backups: int = 3
) -> None:
    """Append one redacted JSON line; rotate at max_bytes. Never raises."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > max_bytes:
            for i in range(backups, 0, -1):
                src = path.with_name(f"{path.name}.{i - 1}") if i > 1 else path
                dst = path.with_name(f"{path.name}.{i}")
                if src.exists():
                    src.replace(dst)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(redact(record), sort_keys=True) + "\n")
    except OSError:
        pass
