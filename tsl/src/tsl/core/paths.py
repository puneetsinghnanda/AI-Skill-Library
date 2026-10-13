"""Path rules: ~/.truminds layout (SDD-04 §7.3) and companion paths (registry §8)."""

from __future__ import annotations

import contextlib
import re
from pathlib import Path


def safe_ticket(ticket: str) -> str:
    """SDD-12 §3.3: upper-case letters, digits and '-' kept; anything else becomes '_'."""
    return re.sub(r"[^A-Z0-9-]", "_", ticket.upper())


class Home:
    def __init__(self, root: Path) -> None:
        self.root = root

    @property
    def config(self) -> Path:
        return self.root / "config.toml"

    @property
    def outbox(self) -> Path:
        return self.root / "outbox.db"

    @property
    def cache(self) -> Path:
        return self.root / "cache"

    @property
    def me(self) -> Path:
        return self.cache / "me.json"

    def key_cache(self, key_id: str) -> Path:
        return self.cache / "keys" / f"{key_id}.json"

    def system_cache(self, code: str) -> Path:
        return self.cache / "systems" / f"{code}.json"

    @property
    def plugin_root_file(self) -> Path:
        return self.cache / "plugin-root.txt"

    @property
    def sessions(self) -> Path:
        return self.root / "sessions"

    def session(self, session_id: str) -> Path:
        return self.sessions / f"{_safe_name(session_id)}.json"

    def session_policy(self, session_id: str) -> Path:
        return self.sessions / f"{_safe_name(session_id)}.policy.json"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def msal_cache(self) -> Path:
        return self.root / "msal-cache.bin"

    @property
    def active_key(self) -> Path:
        return self.root / "keys" / "active.json"

    def eval_dir(self, skill: str, version: str) -> Path:
        return self.root / "eval" / skill / version

    @property
    def improve_cache(self) -> Path:
        return self.cache / "improve"

    def ensure(self) -> None:
        for p in (self.root, self.cache, self.sessions, self.logs):
            p.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(OSError):  # Windows ACLs are set by the installer
            self.root.chmod(0o700)


def _safe_name(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", s)[:128]


# companion-relative paths (registry §8)
def lock_path(ticket: str, workflow: str) -> str:
    return f"runs/active/{safe_ticket(ticket)}__{workflow}.lock"


def run_dir(run_id: str) -> str:
    return f"runs/{run_id}"


def state_path(run_id: str) -> str:
    return f"runs/{run_id}/state.json"


def snapshot_path(run_id: str) -> str:
    return f"runs/{run_id}/workflow.snapshot.yaml"


def questions_path(run_id: str) -> str:
    return f"runs/{run_id}/open-questions.md"


def approvals_path(run_id: str) -> str:
    return f"runs/{run_id}/approvals.md"


def tool_log_path(run_id: str) -> str:
    return f"runs/{run_id}/tool-log.jsonl"


def feedback_path(run_id: str, step: str, attempt: int) -> str:
    return f"runs/{run_id}/feedback/{step}.a{attempt}.json"


def artifact_dir(ticket: str, run_id: str) -> str:
    return f"artifacts/{ticket}/{run_id}"


def artifact_path(ticket: str, run_id: str, step: str) -> str:
    return f"artifacts/{ticket}/{run_id}/{step}.md"


def history_dir(ticket: str, run_id: str, step: str, attempt: int) -> str:
    return f"artifacts/{ticket}/{run_id}/history/{step}/a{attempt}"


RECORD_SUFFIXES = (".checks.json", ".review-package.json", ".review.json", ".verification.json")


def sibling(artifact_rel: str, suffix: str) -> str:
    """artifacts/T/run/design.md -> artifacts/T/run/design.checks.json"""
    if not artifact_rel.endswith(".md"):
        raise ValueError(f"not an artifact path: {artifact_rel}")
    return artifact_rel[: -len(".md")] + suffix


ARTIFACT_RE = re.compile(
    r"^artifacts/(?P<ticket>[A-Za-z][A-Za-z0-9_]*-[0-9]+)/(?P<run_id>run_[0-9A-HJKMNP-TV-Z]{26})/"
    r"(?P<step>[a-z][a-z0-9-]{0,40})\.md$"
)
