"""Free-text checks for event string fields (SDD-08 §4.4, TM-08; SEC-01 §7.4).

The same pattern list is shared with the marketplace CI test. A hit returns a rule id only; the
offending value is never logged or stored.
"""

from __future__ import annotations

import hashlib
import math
import re
import string
import unicodedata
from collections.abc import Iterator
from typing import Any

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("pem", re.compile(r"-----BEGIN [A-Z ]+-----")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")),
    ("aws_key", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("gcp_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("github_token", re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b")),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("azure_conn", re.compile(r"(AccountKey|SharedAccessKey)=", re.IGNORECASE)),
]
URL = re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s]+", re.IGNORECASE)
ALLOWED_URL = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?$")
TOKEN_LIKE = re.compile(r"[A-Za-z0-9+/=_-]{40,}")
PATH_PREFIXES = ("context/", "artifacts/", "runs/")
PATH_FIELDS = {"evidence_ref"}
MAX_LEN = 200
MAX_LEN_BY_FIELD = {"ticket_ref": 40}


def _entropy(s: str) -> float:
    counts = {c: s.count(c) for c in set(s)}
    return -sum(n / len(s) * math.log2(n / len(s)) for n in counts.values())


def high_entropy(s: str) -> bool:
    for m in TOKEN_LIKE.finditer(s):
        tok = m.group(0)
        if all(c in string.hexdigits for c in tok) and len(tok) in (40, 64):
            continue  # git SHAs and sha256 digests are ids, not secrets
        if _entropy(tok) >= 4.0:
            return True
    return False


def walk_strings(obj: Any, key: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(obj, str):
        yield key, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_strings(k, "<key>")
            yield from walk_strings(v, str(k))
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_strings(v, key)


def check_string(field: str, value: str) -> str | None:
    """Return the failing rule id, or None."""
    if len(value) > MAX_LEN_BY_FIELD.get(field, MAX_LEN):
        return "length"
    for rule, pat in PATTERNS:
        if pat.search(value):
            return rule
    for m in URL.finditer(value):
        if not ALLOWED_URL.match(m.group(0)):
            return "url"
    if high_entropy(value):
        return "entropy"
    if field in PATH_FIELDS:
        if not value.startswith(PATH_PREFIXES):
            return "path"
    elif "/" in value and not ALLOWED_URL.match(value) and re.search(r"\w/\w", value):
        return "path"
    return None


def check_body(body: Any) -> str | None:
    for field, value in walk_strings(body):
        rule = check_string(field, value)
        if rule:
            return rule
    return None


# ----- client-name denylist (SEC-01 §7.4) -----
def normalise(text: str) -> list[str]:
    t = unicodedata.normalize("NFKC", text).lower()
    t = "".join(c if c.isalnum() or c.isspace() else " " for c in t)
    return t.split()


def ngrams(words: list[str], max_n: int = 4) -> Iterator[str]:
    for n in range(1, max_n + 1):
        for i in range(len(words) - n + 1):
            yield " ".join(words[i : i + n])


def ngram_hash(salt: bytes, gram: str) -> str:
    return hashlib.sha256(salt + gram.encode("utf-8")).hexdigest()


def name_hashes(salt: bytes, name: str) -> set[str]:
    return {ngram_hash(salt, g) for g in ngrams(normalise(name))}


def client_hit(salt: bytes, hashes: frozenset[str], body: Any) -> bool:
    if not hashes:
        return False
    for _f, value in walk_strings(body):
        for g in ngrams(normalise(value)):
            if ngram_hash(salt, g) in hashes:
                return True
    return False


FORBIDDEN_KEYS = {"user", "email", "name"}


def forbidden_key(obj: Any) -> bool:
    if isinstance(obj, dict):
        return any(k in FORBIDDEN_KEYS or forbidden_key(v) for k, v in obj.items())
    if isinstance(obj, list):
        return any(forbidden_key(v) for v in obj)
    return False
