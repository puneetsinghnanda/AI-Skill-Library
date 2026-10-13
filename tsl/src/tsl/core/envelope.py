"""tsl-output.v1 envelope and rendering (SDD-04 §4)."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from tsl import __version__


class Warning_(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    message: str = Field(max_length=300)


class Envelope(BaseModel):
    """Typed form of tsl-output.v1; tests check it against the JSON Schema."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    schema_: str = Field(default="tsl-output.v1", alias="schema")
    ok: bool
    code: str
    exit: int
    message: str = Field(max_length=300)
    next: str | None = Field(default=None, max_length=300)
    data: dict[str, Any] = {}
    warnings: list[Warning_] = []
    tsl_version: str = __version__

    def to_json(self) -> str:
        return json.dumps(self.model_dump(by_alias=True), ensure_ascii=False, sort_keys=False)


def make(
    code: str,
    exit_: int,
    message: str,
    next_: str | None,
    data: dict[str, Any] | None,
    warnings: list[dict[str, str]] | None,
) -> Envelope:
    seen: set[tuple[str, str]] = set()
    ws = []
    for w in warnings or []:
        key = (w["code"], w["message"])
        if key not in seen:
            seen.add(key)
            ws.append(Warning_(code=w["code"], message=w["message"][:300]))
    return Envelope(
        ok=exit_ == 0,
        code="OK" if exit_ == 0 else code,
        exit=exit_,
        message=message[:300],
        next=(next_ or None) and next_[:300],
        data=data or {},
        warnings=ws,
    )


def human(env: Envelope, color: bool) -> str:
    icon = "✔" if env.ok else ("⏸" if env.exit == 4 else "✖")
    status = "OK" if env.ok else env.code
    lines = [f"{icon} {env.message}    [{status}]"]
    for w in env.warnings:
        lines.append(f"  ⚠ {w.code}: {w.message}")
    if env.next:
        lines.append(f"  Next:   {env.next}")
    for k, v in env.data.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            lines.append(f"  {k}: {v}")
    text = "\n".join(lines)
    if color and not env.ok:
        return f"\x1b[31m{text}\x1b[0m"
    return text
