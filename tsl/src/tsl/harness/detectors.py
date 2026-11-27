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


RUN_ID_IN_PATH = re.compile(r"run_[0-9A-HJKMNP-TV-Z]{26}")
# A code citation `<repo>:<relative path>.<ext>#<anchor>` of a product repo the caller names
# (`sample-system:db/migrations/20261016T090000__create_reference_lists.sql#L16`) is a file
# reference. Such a token is not checked as a whole, because a long path to a dated file looks
# random. Instead these are checked: each directory, the file name, each piece of the file name
# (split at `_` and `-`), and every piece of the whole path that is not a plain word, number or
# date, joined (so a secret split across `/` is still found). Known ids (`run_`, `evt_`, ...)
# are kept out. The shape is exact: a repo name the caller passes (never `https`), right before
# `:`, a path with `/`, no leading `/` and no `+` or `=`, then a lower-case source extension or
# a known extension-less file name (`Dockerfile`), then `#` and an anchor.
CITE_EXTS = (
    "sql|md|mdx|rst|adoc|txt|json|jsonc|jsonl|yaml|yml|toml|ini|cfg|conf|env|properties|xml|"
    "html|htm|css|scss|sass|less|vue|svelte|astro|js|jsx|mjs|cjs|ts|tsx|mts|cts|py|pyi|ipynb|"
    "rb|go|rs|java|kt|kts|scala|groovy|gradle|cs|fs|vb|php|swift|m|mm|c|h|cc|cpp|cxx|hpp|hh|"
    "dart|lua|pl|pm|r|ex|exs|erl|hrl|clj|cljs|elm|hs|ml|zig|nim|sh|bash|zsh|fish|ps1|psm1|bat|"
    "cmd|tf|tfvars|hcl|nix|proto|graphql|gql|prisma|csv|tsv|lock|mk|cmake|dockerfile|tmpl|j2"
)
# Up to two short parts before the extension (`.spec.ts`, `.d.ts`, `.test.py`).
CITE_AFTER = re.compile(r"(?:\.[a-z0-9]{1,10}){0,2}\.(?:" + CITE_EXTS + r")#[A-Za-z0-9]")
CITE_ANCHOR = re.compile(r"#[A-Za-z0-9]")
NOEXT_NAMES = frozenset(
    {
        "Dockerfile",
        "Containerfile",
        "Makefile",
        "GNUmakefile",
        "Procfile",
        "Jenkinsfile",
        "Gemfile",
        "Rakefile",
        "Vagrantfile",
        "Brewfile",
        "Justfile",
        "Earthfile",
        "Tiltfile",
        "CODEOWNERS",
        "LICENSE",
    }
)
CITE_DELIMS = " \t\n\"'`([,{*|<>"
ID_IN_NAME = re.compile(r"(?:run|evt|key|dev|imp|flg)_[0-9A-HJKMNP-TV-Z]{26}")
# Path pieces that are words, numbers or dates, never secrets: `migrations`, `Doctor`,
# `DoctorDetailPage`, `API`, `0008`, `v2`, `20261016T090000`.
PLAIN_PIECE = re.compile(r"[a-z]+|[A-Z]+|(?:[A-Z][a-z]+)+|[0-9]+|v[0-9]+|[0-9]{8}T[0-9]{4,6}")


def _cite_pieces(
    text: str, start: int, end: int, repos: frozenset[str]
) -> list[tuple[str, int, int]] | None:
    """The parts of a code citation to check, or None when text[start:end] is not one."""
    tok = text[start:end]
    if not repos or "/" not in tok or tok.startswith("/") or "+" in tok or "=" in tok:
        return None
    if start < 2 or text[start - 1] != ":":
        return None
    *dirs, name = tok.split("/")
    if not (CITE_AFTER.match(text, end) or (name in NOEXT_NAMES and CITE_ANCHOR.match(text, end))):
        return None
    i = start - 1
    while i > 0 and (text[i - 1].isalnum() or text[i - 1] in "._-"):
        i -= 1
    if text[i : start - 1] not in repos or (i > 0 and text[i - 1] not in CITE_DELIMS):
        return None
    masked_tok = ID_IN_NAME.sub(lambda m: "_" * len(m.group(0)), tok)  # ids are not secrets
    # Every piece of the path that is not a plain word, number or date, joined: catches a
    # secret split into short parts across `/`, `_` or `-`. Reported on the whole token.
    odd = "".join(
        p.group(0)
        for p in re.finditer(r"[^/_\-]+", masked_tok)
        if not PLAIN_PIECE.fullmatch(p.group(0))
    )
    pieces: list[tuple[str, int, int]] = [(odd, start, end)]
    pos = start
    for d in dirs:  # a directory is checked whole
        pieces.append((d, pos, pos + len(d)))
        pos += len(d) + 1
    masked = masked_tok[pos - start :]
    pieces.append((masked, pos, pos + len(name)))  # the whole file name, and each piece of it
    for p in re.finditer(r"[^_\-]+", masked):
        pieces.append((p.group(0), pos + p.start(), pos + p.end()))
    return pieces


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
    cite_repos: frozenset[str] = frozenset(),
) -> list[Hit]:
    """`cite_repos`: product repo names whose code citations get the narrow cite rule above;
    empty (the default) keeps every token checked whole."""
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
            whole = m.group(0)
            if SAFE_TOKEN.match(whole) or allowed(whole):
                continue
            if RUN_ID_IN_PATH.search(whole):
                continue  # citation paths carry ULID run ids; they are ids, not secrets
            parts = _cite_pieces(text, m.start(), m.end(), cite_repos)
            if parts is None:
                parts = [(whole, m.start(), m.end())]  # anything else: one token, as always
            around = text[max(0, m.start() - window) : m.end() + window].replace(whole, "")
            for tok, start, end in parts:
                if len(tok) < minlen or SAFE_TOKEN.match(tok):
                    continue
                if allowed(tok) or allowed(text[start:end]):  # the span the finding reports
                    continue
                if not (re.search(r"[A-Za-z]", tok) and re.search(r"[0-9]", tok)):
                    continue
                low = tok.lower()
                if any(p in low for p in placeholders) or re.fullmatch(r"[a-z0-9-]+", tok):
                    continue
                if _entropy(tok) < float(ent.get("min_bits_per_char", 4.0)):
                    continue
                if kw.search(around):
                    hits.append(Hit("SEC-ENT-01", "secret", _line_of(text, start), start, end))
                    break  # one finding per token
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
