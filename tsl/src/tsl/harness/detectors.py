"""H4a secrets and H4b personal data detectors (SDD-03 §4.6, SEC-01 §7.2-§7.3).

A hit reports the rule id and line number only, never the matched text (TM-09).
"""

from __future__ import annotations

import fnmatch
import hashlib
import ipaddress
import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any

from tsl.core.jsonio import load_yaml


@dataclass(frozen=True)
class Hit:
    rule_id: str
    kind: str  # secret | pii | pii-soft | term
    line: int
    start: int
    end: int


@lru_cache(maxsize=1)
def rules() -> tuple[dict[str, Any], dict[str, Any]]:
    from tsl.schemas.registry import require_valid

    base = resources.files("tsl.harness").joinpath("rules")
    sec = load_yaml(base.joinpath("secrets.v1.yaml").read_text(encoding="utf-8"))
    pii = load_yaml(base.joinpath("pii.v1.yaml").read_text(encoding="utf-8"))
    require_valid("secrets.v1", sec, "secrets.v1.yaml")
    require_valid("pii.v1", pii, "pii.v1.yaml")
    return sec, pii


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _entropy(s: str) -> float:
    c = Counter(s)
    n = len(s)
    return -sum(v / n * math.log2(v / n) for v in c.values())


SAFE_TOKEN = re.compile(
    r"^(?:(?:run|evt|key|dev|imp|flg)_[0-9A-HJKMNP-TV-Z]{26}|[0-9a-f]{40}|[0-9a-f]{64})$"
)


def luhn(digits: str) -> bool:
    d = [int(c) for c in digits if c.isdigit()]
    if not 13 <= len(d) <= 19:
        return False
    s = 0
    for i, v in enumerate(reversed(d)):
        if i % 2 == 1:
            v *= 2
            if v > 9:
                v -= 9
        s += v
    return s % 10 == 0


_VD = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_VP = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]


def verhoeff(digits: str) -> bool:
    d = [int(c) for c in digits if c.isdigit()]
    if len(d) != 12 or d[0] in (0, 1):
        return False
    c = 0
    for i, v in enumerate(reversed(d)):
        c = _VD[c][_VP[i % 8][v]]
    return c == 0


def mod97(s: str) -> bool:
    s = s.replace(" ", "")
    if len(s) < 15:
        return False
    r = s[4:] + s[:4]
    num = "".join(str(int(ch, 36)) for ch in r)
    try:
        return int(num) % 97 == 1
    except ValueError:
        return False


def pan(s: str) -> bool:
    return len(s) == 10 and s[3] in "PCHABGJLFT"


def ipv4_public(s: str) -> bool:
    try:
        ip = ipaddress.IPv4Address(s)
    except ValueError:
        return False
    return ip.is_global


VALIDATORS = {
    "none": lambda s: True,
    "luhn": luhn,
    "verhoeff": verhoeff,
    "mod97": mod97,
    "pan": pan,
    "ipv4-public": ipv4_public,
}


def _ignored(value: str, patterns: list[str]) -> bool:
    v = value.lower()
    for p in patterns:
        p = p.lower()
        if "@" in v and (v.endswith("@" + p) or fnmatch.fnmatch(v.split("@", 1)[1], p)):
            return True
        if fnmatch.fnmatch(v, p):
            return True
    return False


def scan(
    text: str,
    allow_sha256: frozenset[str] = frozenset(),
    deny_term_hashes: frozenset[str] = frozenset(),
) -> list[Hit]:
    sec, pii = rules()
    hits: list[Hit] = []
    placeholders = [p.lower() for p in sec.get("placeholders", [])]

    def allowed(val: str) -> bool:
        return hashlib.sha256(val.encode()).hexdigest() in allow_sha256

    for r in sec["rules"]:
        for m in re.finditer(r["pattern"], text):
            val = m.group(0)
            low = val.lower()
            if any(x.lower() in low for x in r.get("exclude_values", [])) or allowed(val):
                continue
            if r["id"] != "SEC-P-08" and any(p in low for p in placeholders):
                continue
            hits.append(Hit(r["id"], "secret", _line_of(text, m.start()), m.start(), m.end()))
    ent = sec.get("entropy") or {}
    if ent:
        kw = re.compile("|".join(re.escape(k) for k in ent.get("keywords", [])), re.I)
        window = int(ent.get("keyword_window", 40))
        minlen = int(ent.get("min_length", 20))
        for m in re.finditer(r"[A-Za-z0-9+/=_-]{" + str(minlen) + ",}", text):
            tok = m.group(0)
            if SAFE_TOKEN.match(tok) or allowed(tok) or ("/" in tok and "." in tok):
                continue
            if not (re.search(r"[A-Za-z]", tok) and re.search(r"[0-9]", tok)):
                continue
            if any(p in tok.lower() for p in placeholders) or re.fullmatch(r"[a-z0-9-]+", tok):
                continue
            if _entropy(tok) < float(ent.get("min_bits_per_char", 4.0)):
                continue
            around = text[max(0, m.start() - window) : m.end() + window]
            if kw.search(around.replace(tok, "")):
                hits.append(
                    Hit("SEC-ENT-01", "secret", _line_of(text, m.start()), m.start(), m.end())
                )
    for r in pii["rules"]:
        validator = VALIDATORS[r.get("validator", "none")]
        for m in re.finditer(r["pattern"], text):
            val = m.group(0)
            if _ignored(val, r.get("ignore", [])) or allowed(val) or not validator(val.strip()):
                continue
            if r.get("context_words"):
                w = int(r.get("context_window", 30))
                around = text[max(0, m.start() - w) : m.end() + w].lower()
                if not any(cw in around for cw in r["context_words"]):
                    continue
            kind = "pii" if r["action"] == "H4" else "pii-soft"
            hits.append(Hit(r["id"], kind, _line_of(text, m.start()), m.start(), m.end()))
    if deny_term_hashes:
        for m in re.finditer(r"[A-Za-z][A-Za-z0-9&.-]*(?:\s+[A-Za-z][A-Za-z0-9&.-]*){0,3}", text):
            words = m.group(0).split()
            for n in range(1, len(words) + 1):
                for i in range(len(words) - n + 1):
                    t = " ".join(words[i : i + n]).lower()
                    if hashlib.sha256(t.encode()).hexdigest() in deny_term_hashes:
                        hits.append(
                            Hit("TERM-01", "term", _line_of(text, m.start()), m.start(), m.end())
                        )
    return sorted(set(hits), key=lambda h: (h.line, h.rule_id))


def mask(text: str, hits: list[Hit]) -> str:
    """Replace each hit with [REDACTED:<kind>:<8 hex>] (SDD-06 §9.3)."""
    out = text
    for h in sorted(hits, key=lambda x: x.start, reverse=True):
        val = out[h.start : h.end]
        tag = hashlib.sha256(val.encode()).hexdigest()[:8]
        kind = "pii" if h.kind.startswith("pii") else h.kind
        out = out[: h.start] + f"[REDACTED:{kind}:{tag}]" + out[h.end :]
    return out
