#!/usr/bin/env python3
"""E1 benchmark report: retries, time, wait and tokens per step, from the companion's run records.

Roadmap 25-27 Nov, E1: "A script turns the run records (D1) and pilot-stats into one table:
retries, tokens and wait per step, by OS." It reads, for each run in the benchmark set
(benchmarks/set.json):

- runs/<run>/state.json: steps, attempts (cause, outcome, band, started_at, decided_at) and, from
  D1 on, each attempt's `metrics` (tokens, wait_s, active_ms);
- runs/<run>/feedback/<step>.a<n>.json: why an attempt was retried (review findings, or a
  verifier build, lint or test failure, or a harness check);
- runs/<run>/ide-questions.json (B2): the engineer's wait, when the attempt has no D1 metrics;
- runs/<run>/ide-answers.md: how many questions each step asked;
- runs/<run>/tool-log.jsonl: the OS, from the paths the tools touched, when the set gives none.

Runs from before D1 (0.1.7) have no tokens and no recorded wait: those cells show "n/r" (not
recorded) and their AI time is the attempt's wall time, questions included. A run's owner can
add its tokens from the transcripts on their laptop (D1, tsl 0.1.8+), from the companion root:
`tsl state show <run_id> --metrics --json > <repo>/benchmarks/metrics/<run_id>.json`. Only the
tokens are taken from such an export.

Usage (from the repo root; Python 3.10+, standard library only):

    python3 benchmarks/bench_report.py --companion ../cl-int-sys-smp2-companion --ref origin/main
    python3 benchmarks/bench_report.py --companion ... --release 0.1.7 --format json --out x.json
    python3 benchmarks/bench_report.py --companion ... --bench-only      # the fixed set only

`--ref` reads the files from that git ref of the companion (no checkout or pull needed);
without it the working tree is read.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import statistics
import subprocess
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SET = ROOT / "benchmarks" / "set.json"
DEFAULT_METRICS = ROOT / "benchmarks" / "metrics"

PASS = ("PASS", "PASS-WITH-FINDINGS")
# Why a retry happened, in table order, with the one-letter code used in the matrix.
REASONS = {"review": "R", "build": "B", "lint": "L", "test": "T", "checks": "C", "verifier": "V"}
CAUSE_REASON = {"retry_review": "review", "retry_verifier": "verifier", "retry_checks": "checks"}
SLIP = re.compile(r"^\s*(build|lint|test) (exit|timed out)\b")
TOKEN_KEYS = ("input", "output", "cache_read", "cache_write", "calls")


# --- reading ---------------------------------------------------------------------------------


class Source:
    """The companion repo: its working tree, or one git ref of it (read with `git show`)."""

    def __init__(self, root: Path, ref: str | None = None) -> None:
        self.root = Path(root)
        self.ref = ref

    def read(self, rel: str) -> str | None:
        if self.ref is None:
            p = self.root / rel
            try:
                return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None
            except OSError:
                return None
        r = subprocess.run(
            ["git", "-C", str(self.root), "show", f"{self.ref}:{rel}"],
            capture_output=True,
            check=False,
        )
        return r.stdout.decode("utf-8", errors="replace") if r.returncode == 0 else None

    def json(self, rel: str) -> Any:
        text = self.read(rel)
        if text is None:
            return None
        try:
            return json.loads(text)
        except ValueError:
            return None


def _ts(s: Any) -> dt.datetime | None:
    if not s:
        return None
    try:
        t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def _ms(a: Any, b: Any) -> int | None:
    t0, t1 = _ts(a), _ts(b)
    return int((t1 - t0).total_seconds() * 1000) if t0 and t1 and t1 >= t0 else None


# Where an absolute path starts, per OS. Windows first: `C:\`, `C:/`, and a drive mounted by
# Git Bash (`/c/Users/...`) or WSL (`/mnt/c/Users/...`), which also contain `/Users/`.
OS_PATHS = (
    ("Windows", re.compile(r"^(?:[A-Za-z]:[\\/]|/(?:mnt/)?[A-Za-z]/)")),
    ("macOS", re.compile(r"^/Users/")),
    ("Linux", re.compile(r"^/home/")),
)


def infer_os(tool_log: str | None) -> str:
    """Windows, Linux or macOS, from the absolute paths in the run's tool log (one vote a line)."""
    counts = {name: 0 for name, _ in OS_PATHS}
    for line in (tool_log or "").splitlines():
        try:
            target = str(json.loads(line).get("target") or "")
        except (ValueError, AttributeError):
            continue
        # A Bash target is a command line: look at where each word starts.
        words = [w for w in re.split(r"[\s\"'=(),;]+", target) if w]
        hit = next((n for n, rx in OS_PATHS for w in words if rx.match(w)), None)
        if hit:
            counts[hit] += 1
    best = max(counts, key=lambda k: counts[k])
    return best if counts[best] else "unknown"


def retry_reason(feedback: Any, cause: str | None) -> str:
    """Why the attempt that wrote this feedback was retried: review, build, lint, test, checks."""
    if isinstance(feedback, dict):
        kind = feedback.get("kind")
        if kind == "verifier":
            for g in feedback.get("gate_failures") or []:
                m = SLIP.match(str((g or {}).get("detail") or ""))
                if m:
                    return m.group(1)
            return "verifier"
        if kind in ("review", "checks"):
            return str(kind)
    return CAUSE_REASON.get(cause or "", "review")


def ide_waits(doc: Any) -> dict[tuple[str, int], int] | None:
    """Seconds the engineer took to answer, per (step, attempt); None when B2 did not record."""
    if not isinstance(doc, dict) or not isinstance(doc.get("asks"), list):
        return None
    out: dict[tuple[str, int], int] = {}
    for a in doc["asks"]:
        if not isinstance(a, dict):
            continue
        ms = _ms(a.get("asked_at"), a.get("answered_at") or a.get("closed_at"))
        if ms is None:
            continue
        key = (str(a.get("step")), int(a.get("attempt") or 0))
        out[key] = out.get(key, 0) + ms // 1000
    return out


def questions_per_step(md: str | None) -> dict[str, int]:
    """Questions answered in the IDE, per step (one `## A-nn` entry each)."""
    out: dict[str, int] = {}
    for block in re.split(r"^## A-\d+\s*$", md or "", flags=re.M)[1:]:
        m = re.search(r"^- step:\s*(\S+)", block, flags=re.M)
        if m:
            out[m.group(1)] = out.get(m.group(1), 0) + 1
    return out


def _int(v: Any) -> int:
    try:
        return max(0, int(v or 0))
    except (TypeError, ValueError):
        return 0


def _tokens(t: Any) -> dict[str, int] | None:
    if not isinstance(t, dict):
        return None
    return {k: _int(t.get(k)) for k in TOKEN_KEYS}


def load_run(src: Source, entry: dict[str, Any], metrics_dir: Path | None = None) -> dict[str, Any]:
    """One run of the set, as the rows the tables are built from."""
    run_id = entry["run_id"]
    base = f"runs/{run_id}"
    state = src.json(f"{base}/state.json")
    if not isinstance(state, dict):
        raise SystemExit(
            f"bench: no readable {base}/state.json in {src.root} ({src.ref or 'tree'})"
        )
    waits = ide_waits(src.json(f"{base}/ide-questions.json"))
    questions = questions_per_step(src.read(f"{base}/ide-answers.md"))
    # A `tsl state show --metrics --json` export gives tokens only: its wait is 0, not "not
    # recorded", for runs before B2, so the wait and AI time still come from the run record.
    export: dict[tuple[str, int], dict[str, int] | None] = {}
    export_total: dict[str, int] | None = None
    doc = Source(metrics_dir).json(f"{run_id}.json") if metrics_dir is not None else None
    if isinstance(doc, dict) and isinstance(doc.get("data"), dict):  # the tsl --json envelope
        doc = doc["data"].get("metrics") or doc["data"]
    if isinstance(doc, dict):
        for row in doc.get("attempts") or []:
            if isinstance(row, dict):
                key = (str(row.get("step")), _int(row.get("attempt")))
                export[key] = _tokens(row.get("tokens"))
        export_total = _tokens((doc.get("total") or {}).get("tokens"))
    elif metrics_dir is not None and (metrics_dir / f"{run_id}.json").is_file():
        print(f"bench: ignoring unreadable export {metrics_dir / run_id}.json", file=sys.stderr)
    # 2: the run loop's tokens (between attempts) are known only from an export's run total.
    loop = None
    if export_total is not None and export and all(t is not None for t in export.values()):
        att = _sum_tokens(export.values())
        loop = {k: max(0, export_total[k] - att[k]) for k in TOKEN_KEYS}

    steps: list[dict[str, Any]] = []
    for s in state.get("steps") or []:
        if s.get("kind") != "skill":
            continue
        attempts = [a for a in s.get("attempts") or [] if a.get("decided_at")]
        rows = []
        for a in attempts:
            n = int(a["n"])
            m = a.get("metrics")
            span = _ms(a.get("started_at"), a.get("decided_at"))
            ai_ms: int | None
            if m:
                wait_s: int | None = _int(m.get("wait_s"))
                ai_ms = _int(m.get("active_ms")) if m.get("active_ms") is not None else None
                tok = _tokens(m.get("tokens"))
            else:
                wait_s = None if waits is None else waits.get((s["id"], n), 0)
                ai_ms = None if span is None else max(0, span - (wait_s or 0) * 1000)
                tok = export.get((s["id"], n))
            cause = a.get("cause")
            reason = None
            if str(cause or "").startswith("retry_"):
                fb = src.json(a["feedback"]) if a.get("feedback") else None
                if fb is None:
                    fb = src.json(f"{base}/feedback/{s['id']}.a{n - 1}.json")
                reason = retry_reason(fb, cause)
            rows.append(
                {
                    "n": n,
                    "cause": cause,
                    "retry_reason": reason,
                    "outcome": a.get("outcome"),
                    "band": a.get("band"),
                    "ai_ms": ai_ms,
                    "wait_s": wait_s,
                    "tokens": tok,
                }
            )
        steps.append(
            {
                "step": s["id"],
                "status": s.get("status"),
                "attempts": rows,
                "questions": questions.get(s["id"], 0),
            }
        )

    log = src.read(f"{base}/tool-log.jsonl")
    return {
        "ticket": entry.get("ticket") or state.get("ticket"),
        "run_id": run_id,
        "release": entry.get("release") or (state.get("pinned") or {}).get("tsl"),
        "tsl": (state.get("pinned") or {}).get("tsl"),
        "bench": bool(entry.get("bench")),
        "os": entry.get("os") or infer_os(log),
        "workflow": str(state.get("workflow") or "").split("@")[0],
        "status": state.get("status"),
        "end_reason": state.get("end_reason"),
        "wall_ms": _ms(state.get("created_at"), state.get("updated_at")),
        "loop_tokens": loop,
        "steps": steps,
    }


# --- summarising ------------------------------------------------------------------------------


def step_summary(step: dict[str, Any]) -> dict[str, Any]:
    """One step of one run: attempts, retries by reason, first-attempt pass, time, wait, tokens."""
    att = step["attempts"]
    reasons: dict[str, int] = {}
    for a in att:
        if a["retry_reason"]:
            reasons[a["retry_reason"]] = reasons.get(a["retry_reason"], 0) + 1
    waits = [a["wait_s"] for a in att]
    toks = [a["tokens"] for a in att]
    return {
        "attempts": len(att),
        "retries": sum(reasons.values()),
        "reruns": sum(1 for a in att[1:] if not a["retry_reason"]),
        "reasons": reasons,
        "first_pass": bool(att) and att[0]["outcome"] in PASS,
        "ai_ms": _sum_known([a["ai_ms"] for a in att]),
        "wait_s": _sum_known(waits),
        "tokens": None if not toks or any(t is None for t in toks) else _sum_tokens(toks),
        "questions": step["questions"],
    }


def _sum_known(xs: list[int | None]) -> int | None:
    """The sum, or None when any part was not recorded."""
    return None if any(x is None for x in xs) else sum(x for x in xs if x is not None)


def _sum_tokens(toks: Iterable[dict[str, int] | None]) -> dict[str, int]:
    out = dict.fromkeys(TOKEN_KEYS, 0)
    for t in toks:
        for k in TOKEN_KEYS:
            out[k] += (t or {}).get(k, 0)
    return out


def run_summary(run: dict[str, Any]) -> dict[str, Any]:
    per = {s["step"]: step_summary(s) for s in run["steps"]}
    reasons: dict[str, int] = {}
    for v in per.values():
        for k, n in v["reasons"].items():
            reasons[k] = reasons.get(k, 0) + n
    waits = [v["wait_s"] for v in per.values()]
    toks = [v["tokens"] for v in per.values()]
    return {
        "steps": per,
        "attempts": sum(v["attempts"] for v in per.values()),
        "retries": sum(reasons.values()),
        "reasons": reasons,
        "first_pass": sum(v["first_pass"] for v in per.values()),
        "scored_steps": len(per),
        "ai_ms": _sum_known([v["ai_ms"] for v in per.values()]),
        "wait_s": _sum_known(waits),
        # Attempts only, the same for every run; the run loop is `loop_tokens`, where known.
        "tokens": None if not toks or any(t is None for t in toks) else _sum_tokens(toks),
        "loop_tokens": run["loop_tokens"],
        "questions": sum(v["questions"] for v in per.values()),
    }


def step_order(runs: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for r in runs:
        for s in r["steps"]:
            if s["step"] not in out:
                out.append(s["step"])
    return out


def group_steps(
    runs: list[dict[str, Any]], sums: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Per step over a group of runs: first-attempt pass, retries, median AI time, wait, tokens."""
    rows = []
    for step in step_order(runs):
        got = [sums[r["run_id"]]["steps"][step] for r in runs if step in sums[r["run_id"]]["steps"]]
        reasons: dict[str, int] = {}
        for g in got:
            for k, n in g["reasons"].items():
                reasons[k] = reasons.get(k, 0) + n
        waits = [g["wait_s"] for g in got if g["wait_s"] is not None]
        outs = [g["tokens"]["output"] for g in got if g["tokens"] is not None]
        ins = [_input(g["tokens"]) for g in got if g["tokens"] is not None]
        rows.append(
            {
                "step": step,
                "runs": len(got),
                "first_pass": sum(g["first_pass"] for g in got),
                "runs_with_retry": sum(1 for g in got if g["retries"]),
                "retries": sum(g["retries"] for g in got),
                "reasons": reasons,
                "ai_runs": sum(1 for g in got if g["ai_ms"] is not None),
                "ai_min_median": _median(
                    [g["ai_ms"] / 60000 for g in got if g["ai_ms"] is not None]
                ),
                "wait_min_total": sum(waits) / 60 if len(waits) == len(got) and got else None,
                "tokens_runs": len(outs),
                "tokens_out_median": _median(outs),
                "tokens_in_median": _median(ins),
                "questions": sum(g["questions"] for g in got),
            }
        )
    return rows


def _input(t: dict[str, int]) -> int:
    return t["input"] + t["cache_read"] + t["cache_write"]


def _median(xs: Sequence[float]) -> float | None:
    return float(statistics.median(xs)) if xs else None


# --- rendering --------------------------------------------------------------------------------

NR = "n/r"


def _min(ms: float | None) -> str:
    return NR if ms is None else f"{ms / 60000:.1f}"


def _k(n: float | None) -> str:
    if n is None:
        return NR
    if n >= 1e6 or round(n / 1e3, 1) >= 1000:  # 999,950 is 1.0M, not 1000.0k
        return f"{n / 1e6:.1f}M"
    return f"{n / 1e3:.1f}k" if n >= 1e3 else str(int(n))


def release_key(r: str) -> tuple[tuple[int, int | str], ...]:
    """Sorts 0.1.7 before 0.1.10; a part that is not a number sorts after the numbers."""
    return tuple((0, int(p)) if p.isdigit() else (1, p) for p in re.split(r"[.\-]", r))


def releases(runs: list[dict[str, Any]]) -> list[str]:
    return sorted({str(r["release"]) for r in runs}, key=release_key)


def _reasons(r: dict[str, int]) -> str:
    return ", ".join(f"{k} {r[k]}" for k in REASONS if r.get(k)) or "-"


def _table(head: list[str], rows: list[list[str]], right: int = 1) -> list[str]:
    out = ["| " + " | ".join(head) + " |"]
    out.append("|" + "|".join(" --- " if i < right else " ---: " for i in range(len(head))) + "|")
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return out


def render_md(
    runs: list[dict[str, Any]], sums: dict[str, dict[str, Any]], title: str, source: str = ""
) -> str:
    steps = step_order(runs)
    lines = [f"# {title}", ""]
    rel = releases(runs)
    lines.append(
        f"{len(runs)} runs ({sum(r['bench'] for r in runs)} in the fixed benchmark set, marked *), "
        f"release {', '.join(rel)}, workflow {', '.join(sorted({r['workflow'] for r in runs}))}. "
        "Generated by `benchmarks/bench_report.py` from the companion run records"
        f"{f' at {source}' if source else ''}."
    )
    lines.append("")
    slips = sum(
        sums[r["run_id"]]["reasons"].get(k, 0) for r in runs for k in ("build", "lint", "test")
    )
    lines.append(
        f"Retries: {sum(sums[r['run_id']]['retries'] for r in runs)} in all; "
        f"{slips} from a verifier build, lint or test slip (R1 target: 0 from build or lint)."
    )
    lines += ["", "## Runs", ""]
    head = ["Ticket", "OS", "tsl", "Status", "Why retried", "1st-attempt pass"]
    head += ["Retries", "AI min", "Wait min", "Questions", "Tokens out", "Tokens in"]
    head += ["Run loop out", "Wall min"]
    rows = []
    for r in runs:
        s = sums[r["run_id"]]
        t = s["tokens"]
        rows.append(
            [
                f"{r['ticket']}{' *' if r['bench'] else ''}",
                r["os"],
                str(r["tsl"]),
                str(r["status"]),
                _reasons(s["reasons"]),
                f"{s['first_pass']}/{s['scored_steps']}",
                str(s["retries"]),
                _min(s["ai_ms"]),
                NR if s["wait_s"] is None else f"{s['wait_s'] / 60:.1f}",
                str(s["questions"]),
                _k(None if t is None else t["output"]),
                _k(None if t is None else _input(t)),
                _k(None if s["loop_tokens"] is None else s["loop_tokens"]["output"]),
                _min(r["wall_ms"]),
            ]
        )
    lines += _table(head, rows, right=5)

    lines += ["", "## Attempts per step", ""]
    lines.append(
        "Attempts each step took. Letters are the retries' reasons: R review, B build, L lint, "
        "T test, C harness checks, V other verifier failure."
    )
    lines.append("")
    rows = []
    for r in runs:
        cells = [f"{r['ticket']}{' *' if r['bench'] else ''}", r["os"]]
        for st in steps:
            g = next((x for x in r["steps"] if x["step"] == st), None)
            if g is None:
                cells.append("-")
                continue
            codes = "".join(REASONS[a["retry_reason"]] for a in g["attempts"] if a["retry_reason"])
            cells.append(f"{len(g['attempts'])}{f' ({codes})' if codes else ''}")
        rows.append(cells)
    lines += _table(["Ticket", "OS", *steps], rows, right=2)

    for rel_name in rel:
        in_rel = [r for r in runs if str(r["release"]) == rel_name]
        groups = [("all OSes", in_rel)]
        groups += [
            (o, [r for r in in_rel if r["os"] == o]) for o in sorted({r["os"] for r in in_rel})
        ]
        if len(groups) == 2:
            groups = groups[:1]
        for name, grp in groups:
            lines += ["", f"## Per step: {rel_name}, {name} ({len(grp)} runs)", ""]
            lines += _step_table(group_steps(grp, sums))

    benched = [r for r in runs if r["bench"]]
    if len(rel) > 1 and benched:
        lines += ["", "## Benchmark set by release", ""]
        lines.append("The fixed set only, so releases compare on the same tickets.")
        for rel_name in rel:
            grp = [r for r in benched if str(r["release"]) == rel_name]
            if grp:
                lines += ["", f"### {rel_name} ({', '.join(r['ticket'] for r in grp)})", ""]
                lines += _step_table(group_steps(grp, sums))

    lines += ["", "## Notes", ""]
    lines.append(
        "- AI min: the attempt's time less the engineer's wait (D1 `active_ms`). Where the wait "
        "was not recorded (`n/r`, all runs before B2 and D1) it is the attempt's wall time, "
        "questions included, so `req` and `design` read high."
    )
    lines.append(
        "- Tokens: the step attempts' tokens, from D1 metrics in the run record or a "
        "`tsl state show --metrics --json` export in `benchmarks/metrics/` (tokens only). The "
        "run loop's own tokens (between attempts) are not in them: they are in Run loop out, "
        "known only from an export. Tokens in = input + cache read + cache write. A step median "
        "over fewer runs than the group says how many. `n/r`: not recorded."
    )
    lines.append(
        "- A retry is an attempt with cause `retry_*` (it uses retry budget). Reruns for other "
        "causes (answers, stale inputs, repin) are not counted as retries."
    )
    lines.append(
        "- OS is read from the paths in each run's tool log unless the set gives one. Wall min is "
        "run created to last update."
    )
    return "\n".join(lines) + "\n"


def _step_table(rows: list[dict[str, Any]]) -> list[str]:
    head = ["Step", "Why retried", "1st-attempt pass", "Runs with a retry", "Retries"]
    head += ["AI min (median)", "Wait min (total)", "Questions", "Tokens out (median)"]
    head += ["Tokens in (median)"]
    out = []
    for g in rows:
        part = (
            "" if g["tokens_runs"] in (0, g["runs"]) else f" ({g['tokens_runs']}/{g['runs']} runs)"
        )
        out.append(
            [
                g["step"],
                _reasons(g["reasons"]),
                f"{g['first_pass']}/{g['runs']}",
                f"{g['runs_with_retry']}/{g['runs']}",
                str(g["retries"]),
                NR
                if g["ai_min_median"] is None
                else f"{g['ai_min_median']:.1f}"
                + ("" if g["ai_runs"] == g["runs"] else f" ({g['ai_runs']}/{g['runs']} runs)"),
                NR if g["wait_min_total"] is None else f"{g['wait_min_total']:.1f}",
                str(g["questions"]),
                _k(g["tokens_out_median"]) + part,
                _k(g["tokens_in_median"]) + part,
            ]
        )
    return _table(head, out, right=2)


# --- main ---------------------------------------------------------------------------------


def build(
    src: Source,
    entries: list[dict[str, Any]],
    metrics_dir: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    runs = [load_run(src, e, metrics_dir) for e in entries]
    return runs, {r["run_id"]: run_summary(r) for r in runs}


def select(doc: dict[str, Any], bench_only: bool) -> list[dict[str, Any]]:
    """The set's runs; `--release` is applied after loading, on the release each run reports
    (the set's `release`, else the tsl the run pinned), as the tables label it."""
    return [e for e in doc.get("runs") or [] if e.get("bench") or not bench_only]


def per_step_json(
    runs: list[dict[str, Any]], sums: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Per step, by release, then for all OSes and each OS (as the Markdown tables)."""
    out: dict[str, dict[str, Any]] = {}
    for rel in releases(runs):
        grp = [r for r in runs if str(r["release"]) == rel]
        out[rel] = {"all": group_steps(grp, sums)}
        for o in sorted({r["os"] for r in grp}):
            out[rel][o] = group_steps([r for r in grp if r["os"] == o], sums)
    return out


def _source_label(companion: Path, ref: str | None) -> str:
    """`origin/main (b51c7f1)`, so a committed report says which records it was made from."""
    if ref is None:
        return ""
    r = subprocess.run(
        ["git", "-C", str(companion), "rev-parse", "--short", ref],
        capture_output=True,
        text=True,
        check=False,
    )
    return f"`{ref}` ({r.stdout.strip()})" if r.returncode == 0 else f"`{ref}`"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--companion", required=True, type=Path, help="companion repo checkout")
    ap.add_argument("--ref", help="read the run files from this git ref (e.g. origin/main)")
    ap.add_argument("--set", type=Path, default=DEFAULT_SET, help="benchmark set (set.json)")
    ap.add_argument("--release", help="only the runs of this release (e.g. 0.1.7)")
    ap.add_argument("--bench-only", action="store_true", help="only the fixed benchmark set")
    ap.add_argument(
        "--metrics-dir",
        type=Path,
        default=DEFAULT_METRICS,
        help="`tsl state show <run> --metrics --json` exports, one <run_id>.json each",
    )
    ap.add_argument("--format", choices=("md", "json"), default="md")
    ap.add_argument("--title", default="Brownfield lite benchmark")
    ap.add_argument("--out", type=Path, help="write here instead of stdout")
    a = ap.parse_args(argv)

    doc = json.loads(a.set.read_text(encoding="utf-8"))
    runs, sums = build(Source(a.companion, a.ref), select(doc, a.bench_only), a.metrics_dir)
    if a.release:
        runs = [r for r in runs if str(r["release"]) == a.release]
    if not runs:
        print("bench: no runs match", file=sys.stderr)
        return 1
    if a.format == "json":
        text = json.dumps(
            {
                "schema": "bench-report.v1",
                "runs": [{**r, "summary": sums[r["run_id"]]} for r in runs],
                "per_step": per_step_json(runs, sums),
            },
            indent=2,
            sort_keys=True,
        )
        text += "\n"
    else:
        text = render_md(runs, sums, a.title, _source_label(a.companion, a.ref))
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
