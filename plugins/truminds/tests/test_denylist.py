"""Forbidden-content scan over everything this build ships: plugin, pods, spikes, marketplace (C-09, T-01, SKL-V12).

- Secrets: cloud keys, private-key headers, tokens, JWTs, connection strings with passwords.
- The reserved fake key pattern FAKE-KEY-* (SDD-01 §10.4) may appear only inside evals/**.
- Personal data: email addresses outside the reserved example domains, phone numbers.
- Domain words the brief rules out (the library is domain-agnostic; examples never use a networking domain).
- Client names: compared as salted SHA-256 hashes of normalised 1-3 word n-grams against a list that lives
  outside the repository (SDD-11 §7.3, SEC-01 §7.4), so the list itself never leaks a name. Point
  TRUMINDS_DENYLIST_FILE at that file (first line `salt:<salt>`, then one hex digest per line). Without it the
  client-name test is skipped, never passed silently.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

import pytest

from conftest import PLUGIN, PODS, ROOT

SCAN_ROOTS = [PLUGIN, PODS, ROOT / "spikes", ROOT / ".claude-plugin"]
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".venv", ".ruff_cache", "uv.lock"}
TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".txt", ".py", ".sh", ".cmd", ".toml", ".log", "", ".jsonl"}

SECRET_RULES = {
    "aws-access-key": re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"),
    "private-key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "github-token": re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})\b"),
    "slack-token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    "conn-string-password": re.compile(r"\b[a-z][a-z0-9+]*://[^/\s:@]+:[^@\s<>]{3,}@"),
    "assigned-secret": re.compile(
        r"(?i)\b(api[_-]?key|secret|password|passwd|access[_-]?token)\b\s*[:=]\s*['\"]?(?!<)(?!FAKE-KEY)[A-Za-z0-9/+_=-]{16,}"
    ),
}
FAKE_KEY = re.compile(r"FAKE-KEY-[0-9A-Z][0-9A-Z-]*")
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@((?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,})\b")
ALLOWED_EMAIL_DOMAINS = {
    "example.com",
    "example.org",
    "example.net",
    "example.test",
    "truminds.example",
    "anthropic.com",
}
PHONE = re.compile(r"(?<![\w.:-])\+[1-9][0-9 ()-]{9,16}[0-9](?![\w.-])")
DOMAIN_WORDS = re.compile(r"(?i)\b(wi-?fi|wlan|ssid|wireless access point)\b")


def _files() -> list[Path]:
    out = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for p in sorted(root.rglob("*")):
            if (
                p.is_file()
                and not (SKIP_PARTS & set(p.parts))
                and p.suffix in TEXT_SUFFIXES
                and p.name != "test_denylist.py"
            ):
                out.append(p)
    return out


FILES = _files()


def _rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


def _hits(pattern: re.Pattern[str], text: str) -> list[int]:
    return [text.count("\n", 0, m.start()) + 1 for m in pattern.finditer(text)]


def test_scan_covers_the_build() -> None:
    assert len(FILES) > 200


@pytest.mark.parametrize("path", FILES, ids=_rel)
def test_no_secrets(path: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    found = {rule: _hits(rx, text) for rule, rx in SECRET_RULES.items()}
    found = {k: v for k, v in found.items() if v}
    assert not found, f"{_rel(path)}: secret-like content (rule: lines) {found}"  # lines only, never the value


@pytest.mark.parametrize("path", FILES, ids=_rel)
def test_fake_keys_only_inside_evals(path: Path) -> None:
    """Instructions may name the reserved pattern (FAKE-KEY-*); a concrete fake key value lives only in evals/**."""
    if "evals" in path.relative_to(ROOT).parts:
        return
    lines = _hits(FAKE_KEY, path.read_text(encoding="utf-8", errors="replace"))
    assert not lines, f"{_rel(path)}: fake key outside evals/** at lines {lines}"


@pytest.mark.parametrize("path", FILES, ids=_rel)
def test_no_personal_data(path: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    bad = [
        text.count("\n", 0, m.start()) + 1
        for m in EMAIL.finditer(text)
        if m.group(1).lower() not in ALLOWED_EMAIL_DOMAINS
    ]
    assert not bad, f"{_rel(path)}: email outside reserved example domains at lines {bad}"
    assert not _hits(PHONE, text), f"{_rel(path)}: phone-number-like content at lines {_hits(PHONE, text)}"


@pytest.mark.parametrize("path", FILES, ids=_rel)
def test_domain_agnostic_wording(path: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    assert not _hits(DOMAIN_WORDS, text), f"{_rel(path)}: domain-specific wording at lines {_hits(DOMAIN_WORDS, text)}"


def _ngrams(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    grams = set(words)
    grams |= {" ".join(words[i : i + 2]) for i in range(len(words) - 1)}
    grams |= {" ".join(words[i : i + 3]) for i in range(len(words) - 2)}
    return grams


def test_no_client_names() -> None:
    src = os.environ.get("TRUMINDS_DENYLIST_FILE")
    if not src:
        pytest.skip("TRUMINDS_DENYLIST_FILE not set: the hashed client deny list lives outside the repo (SDD-11 §7.3)")
    lines = Path(src).read_text(encoding="utf-8").split()
    assert lines and lines[0].startswith("salt:"), "first line must be salt:<salt>"
    salt = lines[0][5:]
    deny = {h.lower() for h in lines[1:] if re.fullmatch(r"[0-9a-fA-F]{64}", h)}
    hits = []
    for p in FILES:
        for g in _ngrams(p.read_text(encoding="utf-8", errors="replace")):
            if hashlib.sha256((salt + g).encode()).hexdigest() in deny:
                hits.append(_rel(p))  # report the file only, never the matched token
                break
    assert not hits, f"client identifiers found in: {hits}"


def test_hashing_scheme_detects_a_planted_token(tmp_path: Path) -> None:
    """Self-test of the n-gram hashing with an invented token, so the scan cannot silently match nothing."""
    salt = "s4lt"
    planted = "invented client co"
    digest = hashlib.sha256((salt + planted).encode()).hexdigest()
    sample = "Notes for Invented Client Co. about orders."
    assert digest in {hashlib.sha256((salt + g).encode()).hexdigest() for g in _ngrams(sample)}
