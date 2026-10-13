"""List every OTel metric name, log/event name and attribute key in the collector's file export (spike S-10).

Usage: python3 list-names.py <path to claude-code-otel.jsonl>
Prints names and attribute keys only, never attribute values, so the output can be pasted into the results table.
"""

import json
import sys
from collections import defaultdict


def keys(attrs: list[dict]) -> set[str]:
    return {a.get("key", "") for a in attrs or []}


def main(path: str) -> None:
    metrics: dict[str, set[str]] = defaultdict(set)
    events: dict[str, set[str]] = defaultdict(set)
    resource: set[str] = set()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            doc = json.loads(line)
            for rm in doc.get("resourceMetrics", []):
                resource |= keys(rm.get("resource", {}).get("attributes"))
                for sm in rm.get("scopeMetrics", []):
                    for m in sm.get("metrics", []):
                        for kind in ("sum", "gauge", "histogram"):
                            for dp in (m.get(kind) or {}).get("dataPoints", []):
                                metrics[m["name"]] |= keys(dp.get("attributes"))
            for rl in doc.get("resourceLogs", []):
                resource |= keys(rl.get("resource", {}).get("attributes"))
                for sl in rl.get("scopeLogs", []):
                    for rec in sl.get("logRecords", []):
                        attrs = keys(rec.get("attributes"))
                        name = next((a["value"].get("stringValue") for a in rec.get("attributes", [])
                                     if a.get("key") == "event.name"), rec.get("body", {}).get("stringValue", "?"))
                        events[name] |= attrs
    print("resource attribute keys:", sorted(resource))
    for name in sorted(metrics):
        print("metric", name, sorted(metrics[name]))
    for name in sorted(events):
        print("event ", name, sorted(events[name]))


if __name__ == "__main__":
    main(sys.argv[1])
