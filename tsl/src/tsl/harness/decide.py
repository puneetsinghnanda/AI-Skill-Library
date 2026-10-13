"""Citation verification, signals S1-S6, band and the decision table (SDD-03 §8-§11).

Pure functions: the same inputs give the same decision on a laptop and in CI (NFR-14).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from tsl.core.globs import any_match as globs_any
from tsl.harness import citations
from tsl.harness.citations import Resolver

ABORT_CODES = ("E-SEC-01", "E-SEC-02", "E-POL-01", "E-POL-02", "E-POL-03", "E-POL-04", "E-POL-05")
BAND_ORDER = {"Low": 0, "Medium": 1, "High": 2}
CAP_MAX = {
    "pack-stale": "Medium",
    "reviewer-missing": "Low",
    "no-verifier": "Medium",
    "format-only-cites": "Medium",
}


@dataclass
class DecideInput:
    checks: dict[str, Any]
    review: dict[str, Any] | None
    front: dict[str, Any]
    rubric: dict[str, Any]
    limits: dict[str, int]
    used: dict[str, int]
    thresholds: dict[str, dict[str, float]]
    s5: str  # fresh | stale | missing
    requires_fresh_pack: bool
    is_code: bool
    change_limits: dict[str, Any]
    resolver: Resolver
    repos: set[str]
    answered: set[str] = field(default_factory=set)
    prev_feedback: dict[str, Any] | None = None
    stale_steps: list[str] = field(default_factory=list)
    generated: dict[str, Any] | None = None


@dataclass
class Decision:
    outcome: str
    band: str | None
    caps: list[str]
    signals: dict[str, Any]
    r6: float
    kept: list[dict[str, Any]]
    dropped: list[dict[str, str]]
    claims_total: int
    claims_verified: int
    gate_failures: list[str]
    codes: list[str]
    reasons: list[str]
    row: int
    budget_kind: str | None = None
    escalate_reason: str | None = None
    rerun_step: str | None = None
    questions: list[dict[str, Any]] = field(default_factory=list)
    s3_note: str | None = None


def _sensitive(path: str, globs: list[str]) -> bool:
    return globs_any(path, globs)


def verify_findings(inp: DecideInput) -> tuple[list[dict[str, Any]], list[dict[str, str]], bool]:
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, str]] = []
    format_only = False
    if not inp.review or inp.review.get("status") != "ok":
        return kept, dropped, format_only
    for f in inp.review.get("findings", []):
        reason = None
        fo = False
        for c in f.get("cites", []):
            cite = citations.parse(str(c["ref"]), inp.repos)
            if cite is None:
                reason = f"bad citation format {str(c['ref'])[:80]}"
                break
            r = citations.verify(cite, str(c["quote"]), [], inp.resolver, inp.generated)
            if not r.ok:
                reason = r.reason or "not verified"
                break
            fo = fo or r.format_only
        if reason:
            dropped.append({"id": str(f["id"]), "reason": reason[:200]})
            continue
        item = {
            "id": str(f["id"]),
            "severity": str(f["severity"]),
            "text": str(f["text"]),
            "category": str(f.get("category", "other")),
            "cites": list(f.get("cites", [])),
        }
        if item["severity"] == "minor":
            paths = [str(c["ref"]).split("#", 1)[0].split(":", 1)[-1] for c in item["cites"]]
            if item["category"] == "security" or any(
                _sensitive(p, list(inp.change_limits.get("sensitive_paths", []))) for p in paths
            ):
                item["raised_from"] = "minor"
                item["severity"] = "major"
        format_only = format_only or fo
        kept.append(item)
    return kept, dropped, format_only


def verify_claims(inp: DecideInput) -> tuple[int, int, bool]:
    claims = inp.front.get("claims", []) or []
    unsupported: set[str] = set()
    if inp.review and inp.review.get("status") == "ok":
        for cc in inp.review.get("claims_checked", []):
            if cc.get("verdict") != "unsupported":
                continue
            ok = False
            for c in cc.get("cites", []):
                cite = citations.parse(str(c["ref"]), inp.repos)
                if (
                    cite
                    and citations.verify(cite, str(c["quote"]), [], inp.resolver, inp.generated).ok
                ):
                    ok = True
            if ok:
                unsupported.add(str(cc["claim_id"]))
    verified = 0
    format_only = False
    for cl in claims:
        cites = cl.get("cites") or []
        good = bool(cites)
        fo = False
        for c in cites:
            ref = str(c["ref"]) if isinstance(c, dict) else str(c)
            quote = str(c["quote"]) if isinstance(c, dict) else None
            cite = citations.parse(ref, inp.repos)
            if cite is None:
                good = False
                break
            r = citations.verify(
                cite, quote, citations.elements_of(cl), inp.resolver, inp.generated
            )
            if not r.ok:
                good = False
                break
            fo = fo or r.format_only
        if good and str(cl.get("id")) not in unsupported:
            verified += 1
            format_only = format_only or fo
    return len(claims), verified, format_only


def _evidence_ok(inp: DecideInput, refs: list[Any]) -> bool:
    for ref in refs:
        cite = citations.parse(str(ref), inp.repos)
        if cite is None:
            return False
        text, _ = inp.resolver.read(cite)
        if text is None or citations.span_for(cite, text, inp.generated)[0] is None:
            return False
    return True


ASK_FROM_ROLE = {
    "tech_lead": "tech lead",
    "engineer": "tech lead",
    "product_owner": "product owner",
    "stage_approver": "tech lead",
}


def collect_questions(inp: DecideInput, kept: list[dict[str, Any]]) -> list[dict[str, Any]]:
    qs: list[dict[str, Any]] = []
    for f in kept:
        if f["severity"] == "blocker":
            qs.append(
                {
                    "source_id": f["id"],
                    "blocking": True,
                    "ask": "tech lead",
                    "question": f["text"],
                    "evidence": [str(c["ref"]) for c in f["cites"]],
                }
            )
    if inp.review and inp.review.get("status") == "ok":
        for q in inp.review.get("questions", []):
            qs.append(
                {
                    "source_id": q["id"],
                    "blocking": bool(q["blocking"]),
                    "ask": ASK_FROM_ROLE.get(str(q["ask_role"]), "tech lead"),
                    "question": str(q["text"]),
                    "evidence": [],
                }
            )
    for q in inp.front.get("questions", []) or []:
        if q.get("id") in inp.answered:
            continue
        if not _evidence_ok(inp, list(q.get("evidence") or [])):
            continue
        qs.append(
            {
                "source_id": q["id"],
                "blocking": bool(q.get("blocking")),
                "ask": q.get("ask"),
                "question": str(q.get("text")),
                "why": q.get("why"),
                "evidence": list(q.get("evidence") or []),
                "options": list(q.get("options") or []),
                "proposed_default": q.get("default"),
            }
        )
    linked = {u.get("id") for u in inp.front.get("unknowns", []) or []}
    for u in inp.front.get("unknown", []) or []:
        if isinstance(u, dict) and u.get("blocking") and u.get("id") not in linked:
            qs.append(
                {
                    "source_id": u["id"],
                    "blocking": True,
                    "ask": "tech lead",
                    "question": f"Unknown {u['id']} needs a decision",
                    "evidence": [],
                }
            )
    return qs


def compute_s3(inp: DecideInput) -> tuple[float | None, str | None]:
    rv = inp.review
    if not rv or rv.get("status") != "ok":
        return None, None
    weights = {str(c["id"]): float(c.get("weight", 1)) for c in inp.rubric.get("criteria", [])}
    items = rv.get("rubric_items", [])
    tw = sum(weights.get(str(i["id"]), 1.0) for i in items)
    if tw <= 0:
        return None, None
    s3 = round(sum(weights.get(str(i["id"]), 1.0) * int(i["score"]) for i in items) / tw, 2)
    note = None
    if rv.get("rubric_score") is not None and abs(float(rv["rubric_score"]) - s3) > 0.05:
        note = f"reviewer rubric_score {rv['rubric_score']} replaced by code value {s3}"
    return s3, note


def compute_s6(inp: DecideInput) -> tuple[dict[str, Any], float]:
    changes = inp.checks.get("product_changes") or []
    if not inp.is_code or not changes:
        return {"lines": 0, "files": 0, "sensitive": False}, 0.0
    lines = sum(int(c.get("lines_added", 0)) + int(c.get("lines_deleted", 0)) for c in changes)
    files = [f for c in changes for f in c.get("files", [])]
    sens = any(_sensitive(f, list(inp.change_limits.get("sensitive_paths", []))) for f in files)
    lmax, fmax = int(inp.change_limits.get("lines", 400)), int(inp.change_limits.get("files", 15))
    r6 = math.inf if sens else max(lines / lmax, len(files) / fmax)
    return {"lines": lines, "files": len(files), "sensitive": sens}, r6


def compute_band(
    s: dict[str, Any], r6: float, t: dict[str, dict[str, float]], caps: list[str]
) -> str:
    def holds(level: str, need_fresh: bool) -> bool:
        x = t[level]
        return (
            s["S1"] >= x["S1_min"]
            and s["S2"] >= x["S2_min"]
            and s["S3"] is not None
            and s["S3"] >= x["S3_min"]
            and s["S4"] == 0
            and (not need_fresh or s["S5"] == "fresh")
            and r6 <= x["S6_max_ratio"]
        )

    band = "High" if holds("high", True) else "Medium" if holds("medium", False) else "Low"
    for cap in caps:
        if BAND_ORDER[CAP_MAX[cap]] < BAND_ORDER[band]:
            band = CAP_MAX[cap]
    return band


def _low_reasons(s: dict[str, Any], r6: float, t: dict[str, float]) -> list[str]:
    out = []
    if s["S1"] < t["S1_min"]:
        out.append("S1")
    if s["S2"] < t["S2_min"]:
        out.append("S2")
    if s["S3"] is None or s["S3"] < t["S3_min"]:
        out.append("S3")
    if r6 > t["S6_max_ratio"]:
        out.append("S6")
    return out


def _same_finding(f: dict[str, Any], prev: dict[str, Any] | None) -> bool:
    if not prev:
        return False
    for p in prev.get("findings", []):
        pc = sorted(str(c["ref"]) if isinstance(c, dict) else str(c) for c in p.get("cites", []))
        fc = sorted(str(c["ref"]) for c in f.get("cites", []))
        if p.get("id") == f["id"] and p.get("severity") == f["severity"] and pc == fc:
            return True
    return False


def evaluate(inp: DecideInput) -> Decision:
    gates = {g["id"]: g for g in inp.checks["gates"]}
    failed = [g["id"] for g in inp.checks["gates"] if g.get("status") == "fail"]
    codes = [c for g in inp.checks["gates"] for c in g.get("codes", [])]
    kept, dropped, fo_f = verify_findings(inp)
    total, verified, fo_c = verify_claims(inp)
    denom = total + len(kept) + len(dropped)
    s1 = 1.0 if denom == 0 else round((verified + len(kept)) / denom, 4)
    soft = [x for x in inp.checks.get("soft", [])]
    s2 = 1.0 if not soft else round(sum(1 for x in soft if x["pass"]) / len(soft), 4)
    s3, note = compute_s3(inp)
    questions = collect_questions(inp, kept)
    s4 = sum(1 for q in questions if q["blocking"])
    s6, r6 = compute_s6(inp)
    signals: dict[str, Any] = {"S1": s1, "S2": s2, "S3": s3, "S4": s4, "S5": inp.s5, "S6": s6}
    caps: list[str] = []
    if inp.s5 in ("stale", "missing") and inp.requires_fresh_pack:
        caps.append("pack-stale")
    if not inp.review or inp.review.get("status") != "ok":
        caps.append("reviewer-missing")
    h3 = gates.get("H3", {})
    if (
        inp.is_code
        and h3.get("status") == "skip"
        and "no verifier profile" in str(h3.get("detail"))
    ):
        caps.append("no-verifier")
    if fo_f or fo_c:
        caps.append("format-only-cites")
    reasons: list[str] = [g for g in failed]
    if "pack-stale" in caps:
        reasons.append("CAP-PACK")
    if "reviewer-missing" in caps:
        reasons.append("REVIEWER-ERROR")

    def mk(outcome: str, row: int, band: str | None = None, **kw: Any) -> Decision:
        return Decision(
            outcome,
            band,
            caps,
            signals,
            r6,
            kept,
            dropped,
            total,
            verified,
            failed,
            codes,
            list(dict.fromkeys(reasons)),
            row,
            questions=questions,
            s3_note=note,
            **kw,
        )

    if any(c in ABORT_CODES for c in codes):
        return mk("ABORT", 1)
    other = [g for g in failed if g not in ("H3",)]
    if ("H3" in failed and inp.used.get("verifier", 0) >= inp.limits["verifier"]) or (
        other and inp.used.get("checks", 0) >= inp.limits["checks"]
    ):
        kind = (
            "verifier"
            if "H3" in failed and inp.used.get("verifier", 0) >= inp.limits["verifier"]
            else "checks"
        )
        return mk("ESCALATE", 2, escalate_reason=f"retry budget exhausted ({kind})")
    if "H6" in failed:
        return mk(
            "RETRY", 3, budget_kind=None, rerun_step=inp.stale_steps[0] if inp.stale_steps else None
        )
    if "H3" in failed:
        return mk("RETRY", 4, budget_kind="verifier")
    if failed:
        return mk("RETRY", 5, budget_kind="checks")
    band = compute_band(signals, r6, inp.thresholds, caps)
    if s4 > 0:
        reasons.append("S4")
        return mk("NEEDS-INPUT", 6, band)
    majors = [f for f in kept if f["severity"] == "major"]
    if majors and inp.used.get("review", 0) < inp.limits["review"]:
        reasons.append("REVIEW-MAJOR")
        if any(_same_finding(f, inp.prev_feedback) for f in majors):
            return mk("ESCALATE", 7, band, escalate_reason="the same finding came back")
        return mk("RETRY", 7, band, budget_kind="review")
    if band == "Low":
        reasons.extend(_low_reasons(signals, r6, inp.thresholds["medium"]))
        return mk("ESCALATE", 8, band, escalate_reason="band Low")
    if kept:
        return mk("PASS-WITH-FINDINGS", 9, band)
    return mk("PASS", 10, band)
