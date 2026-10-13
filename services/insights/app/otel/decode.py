"""OTLP/HTTP decoding (SDD-08 §5): protobuf (``application/x-protobuf``) and JSON.

Protobuf is parsed with ``opentelemetry-proto`` and converted to the OTLP JSON mapping, so one code
path applies the allowlist. Only allowlisted names and attributes are kept; any attribute that
could hold prompt, response, tool input or file content is dropped, and log bodies are never kept.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from google.protobuf.json_format import MessageToDict
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import (
    ExportLogsServiceRequest,
    ExportLogsServiceResponse,
)
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
    ExportMetricsServiceRequest,
    ExportMetricsServiceResponse,
)

CONTENT_ATTR = re.compile(
    r"(prompt|response|content|input|output|body|text|message|file|path|command|query|args)",
    re.IGNORECASE,
)
ALWAYS_KEEP = {"session.id"}


class DecodeError(ValueError):
    pass


@dataclass(frozen=True)
class MetricRule:
    name: str
    keep_attrs: frozenset[str]
    unit: str | None
    usage: tuple[tuple[str, tuple[tuple[str, str], ...]], ...]


@dataclass(frozen=True)
class LogRule:
    event: str
    keep_attrs: frozenset[str]


@dataclass
class Allowlist:
    metrics: dict[str, MetricRule] = field(default_factory=dict)
    logs: dict[str, LogRule] = field(default_factory=dict)


def load_allowlist(path: Path) -> Allowlist:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    al = Allowlist()
    for m in raw.get("metrics") or []:
        usage = tuple(
            (
                str(u["field"]),
                tuple(sorted((str(k), str(v)) for k, v in (u.get("when") or {}).items())),
            )
            for u in m.get("usage") or []
        )
        al.metrics[str(m["name"])] = MetricRule(
            str(m["name"]), frozenset(m.get("keep_attrs") or []), m.get("unit"), usage
        )
    for lg in raw.get("logs") or []:
        al.logs[str(lg["event"])] = LogRule(str(lg["event"]), frozenset(lg.get("keep_attrs") or []))
    return al


@dataclass
class Row:
    signal: str
    name: str
    ts: datetime
    session_id: str | None
    value: float | None
    attributes: dict[str, Any]
    usage: list[str] = field(default_factory=list)


@dataclass
class Decoded:
    rows: list[Row] = field(default_factory=list)
    dropped: dict[str, int] = field(default_factory=dict)

    def drop(self, reason: str, n: int = 1) -> None:
        self.dropped[reason] = self.dropped.get(reason, 0) + n


def parse(body: bytes, content_type: str, signal: str) -> dict[str, Any]:
    ctype = content_type.split(";")[0].strip().lower()
    try:
        if ctype == "application/x-protobuf":
            msg = (
                ExportMetricsServiceRequest() if signal == "metric" else ExportLogsServiceRequest()
            )
            msg.ParseFromString(body)
            out: dict[str, Any] = MessageToDict(msg)
            return out
        if ctype == "application/json":
            import json

            data = json.loads(body or b"{}")
            if not isinstance(data, dict):
                raise DecodeError("not an object")
            return data
    except DecodeError:
        raise
    except Exception as exc:
        raise DecodeError(type(exc).__name__) from exc
    raise DecodeError(f"unsupported content type {ctype}")


def empty_response(signal: str) -> bytes:
    msg = ExportMetricsServiceResponse() if signal == "metric" else ExportLogsServiceResponse()
    out: bytes = msg.SerializeToString()
    return out


def _attr_value(v: dict[str, Any]) -> Any:
    for k in ("stringValue", "boolValue", "doubleValue"):
        if k in v:
            return v[k]
    if "intValue" in v:
        return int(v["intValue"])
    return None


def _attrs(lst: list[dict[str, Any]] | None) -> dict[str, Any]:
    return {str(a.get("key")): _attr_value(a.get("value") or {}) for a in lst or []}


def _ts(nanos: Any) -> datetime:
    try:
        n = int(nanos)
    except (TypeError, ValueError):
        n = 0
    if n <= 0:
        return datetime.now(UTC)
    return datetime.fromtimestamp(n / 1e9, UTC)


def _filter(attrs: dict[str, Any], keep: frozenset[str], dec: Decoded) -> dict[str, Any]:
    out = {}
    for k, v in attrs.items():
        if k in ALWAYS_KEEP or (
            k in keep and not (CONTENT_ATTR.search(k) and k not in ALWAYS_KEEP)
        ):
            if isinstance(v, str) and len(v) > 200:
                dec.drop("content_attr")
                continue
            out[k] = v
        elif CONTENT_ATTR.search(k):
            dec.drop("content_attr")
    return out


def metrics_rows(data: dict[str, Any], al: Allowlist) -> Decoded:
    dec = Decoded()
    for rm in data.get("resourceMetrics") or []:
        res_attrs = _attrs((rm.get("resource") or {}).get("attributes"))
        for sm in rm.get("scopeMetrics") or []:
            for m in sm.get("metrics") or []:
                name = str(m.get("name", ""))
                points: list[dict[str, Any]] = []
                for kind in ("sum", "gauge", "histogram", "exponentialHistogram", "summary"):
                    if kind in m:
                        points = list((m[kind] or {}).get("dataPoints") or [])
                rule = al.metrics.get(name)
                if rule is None:
                    dec.drop("not_allowlisted", max(1, len(points)))
                    continue
                for dp in points:
                    attrs = {**res_attrs, **_attrs(dp.get("attributes"))}
                    if "asDouble" in dp:
                        value: float | None = float(dp["asDouble"])
                    elif "asInt" in dp:
                        value = float(int(dp["asInt"]))
                    elif "sum" in dp:
                        value = float(dp["sum"])
                    else:
                        value = None
                    kept = _filter(attrs, rule.keep_attrs, dec)
                    usage = [
                        f for f, when in rule.usage if all(str(attrs.get(k)) == v for k, v in when)
                    ]
                    sid = attrs.get("session.id")
                    dec.rows.append(
                        Row(
                            "metric",
                            name,
                            _ts(dp.get("timeUnixNano")),
                            str(sid) if sid is not None else None,
                            value,
                            kept,
                            usage,
                        )
                    )
    return dec


def logs_rows(data: dict[str, Any], al: Allowlist) -> Decoded:
    dec = Decoded()
    for rl in data.get("resourceLogs") or []:
        res_attrs = _attrs((rl.get("resource") or {}).get("attributes"))
        for sl in rl.get("scopeLogs") or []:
            for rec in sl.get("logRecords") or []:
                attrs = {**res_attrs, **_attrs(rec.get("attributes"))}
                event = str(rec.get("eventName") or attrs.get("event.name") or "")
                rule = al.logs.get(event)
                if rule is None:
                    dec.drop("not_allowlisted")
                    continue
                kept = _filter(attrs, rule.keep_attrs, dec)
                sid = attrs.get("session.id")
                dec.rows.append(
                    Row(
                        "log",
                        event,
                        _ts(rec.get("timeUnixNano") or rec.get("observedTimeUnixNano")),
                        str(sid) if sid is not None else None,
                        None,
                        kept,
                    )
                )
    return dec
