"""tsl companion check | archive (SDD-12 §6.4, §8.2). Plain code; no LLM (D-11)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tsl.core.clock import iso
from tsl.core.errors import TslError
from tsl.core.frontmatter import FrontMatterError, split
from tsl.core.globs import any_match
from tsl.core.hashing import sha256_bytes, sha256_text
from tsl.core.jsonio import load_yaml, loads_strict, write_json
from tsl.core.repo import Companion
from tsl.core.runtime import Runtime
from tsl.gitops.git import GitError

MAX_FILE_BYTES = 5 * 1024 * 1024
# SDD-12 §6.4 names "the archive threshold (§8)" without a value; this is the proposal used
# until the owner fixes one (reported as a gap).
MAX_REPO_BYTES = 1024 * 1024 * 1024
PROTECTED = ["tsl.yaml", "policy.yaml", "CODEOWNERS", "context/**", ".github/**"]
RECORD_GLOBS = [
    "artifacts/*/*/*.checks.json",
    "artifacts/*/*/*.review.json",
    "artifacts/*/*/*.verification.json",
    "artifacts/*/*/history/**",
]
ARCHIVE_FILE = "ARCHIVE.json"
ARCHIVE_SCHEMA = "companion-archive.v1"
RUN_IN_PATH = re.compile(
    r"^(?:runs/(run_[0-9A-HJKMNP-TV-Z]{26})/|artifacts/[^/]+/(run_[0-9A-HJKMNP-TV-Z]{26})/)"
)
SQUASH_MARK = re.compile(r"\(#\d+\)\s*$", re.M)
CODE_ORDER = ["E-COMP-01", "E-COMP-02", "E-COMP-03", "E-COMP-04", "E-COMP-05"]


@dataclass
class Finding:
    code: str
    path: str
    line: int
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "path": self.path, "line": self.line, "detail": self.detail}


def _tracked(comp: Companion) -> list[str]:
    out = comp.git.out("ls-files", "-z")
    return sorted(p for p in out.split("\0") if p)


def _schema_of(path: str, data: bytes) -> tuple[str | None, Any]:
    text = data.decode("utf-8")
    if path.endswith(".json"):
        obj = loads_strict(text)
    elif path.endswith((".yaml", ".yml")):
        obj = load_yaml(text)
    elif path.endswith(".md"):
        try:
            obj = split(text).front
        except FrontMatterError:
            return None, None
    else:
        return None, None
    if isinstance(obj, dict) and isinstance(obj.get("schema"), str):
        return str(obj["schema"]), obj
    return None, None


def _check_schemas(comp: Companion, files: list[str], out: list[Finding]) -> None:
    from tsl.schemas.registry import errors, readable

    for rel in files:
        # Artifacts are judged by H1 (their failed attempts are kept on purpose);
        # everything else, ARCHIVE.json (companion-archive.v1) included, must validate.
        if rel.startswith("artifacts/") and rel.endswith(".md"):
            continue
        p = comp.path(rel)
        if not p.is_file() or p.stat().st_size > MAX_FILE_BYTES:
            continue
        try:
            schema, obj = _schema_of(rel, p.read_bytes())
        except (UnicodeDecodeError, ValueError) as exc:
            if rel.endswith((".json", ".yaml", ".yml")):
                out.append(Finding("E-COMP-01", rel, 0, f"not parseable: {type(exc).__name__}"))
            continue
        if schema is None:
            continue
        try:
            sid = readable(schema, rel)
        except TslError:
            out.append(Finding("E-COMP-01", rel, 0, f"schema version {schema} not readable"))
            continue
        if not sid:
            out.append(Finding("E-COMP-01", rel, 0, f"unknown schema {schema}"))
            continue
        errs = errors(sid, obj)
        if errs:
            out.append(Finding("E-COMP-01", rel, 0, f"{errs[0].pointer or '/'} {errs[0].message}"))


def _commits(comp: Companion, base: str | None) -> list[str]:
    if comp.git.resolve("HEAD") is None:
        return []
    rng = f"{base}..HEAD" if base else "HEAD"
    try:
        out = comp.git.out("rev-list", "--reverse", rng)
    except GitError as exc:
        raise exc.tsl() from None
    return [c for c in out.splitlines() if c]


def _raw_diff(comp: Companion, commit: str) -> list[tuple[str, str, str, str]]:
    """(status, old_blob, new_blob, path) for one commit against its first parent."""
    out = comp.git.out(
        "diff-tree",
        "--root",
        "-r",
        "--no-commit-id",
        "--no-renames",
        "--raw",
        "--no-abbrev",
        commit,
    )
    rows = []
    for line in out.splitlines():
        if not line.startswith(":") or "\t" not in line:
            continue
        meta, path = line.split("\t", 1)
        parts = meta[1:].split()
        rows.append((parts[4][0], parts[2], parts[3], path))
    return rows


def _check_history(
    comp: Companion,
    commits: list[str],
    base: str | None,
    event: str | None,
    out: list[Finding],
) -> None:
    # Only commits on the pushed branch's own first-parent line were pushed directly; the
    # others arrived through a merge commit, i.e. a reviewed pull request.
    rng = f"{base}..HEAD" if base else "HEAD"
    direct = set(comp.git.out("rev-list", "--first-parent", rng).split()) if commits else set()
    for c in commits:
        rows = _raw_diff(comp, c)
        paths = [r[3] for r in rows]
        parents = comp.git.out("rev-list", "--parents", "-n", "1", c).split()[1:]
        if event == "push" and len(parents) == 1 and c in direct:
            subject = comp.git.out("log", "-1", "--format=%s", c)
            if not SQUASH_MARK.search(subject):
                for p in paths:
                    if any_match(p, PROTECTED):
                        out.append(
                            Finding(
                                "E-COMP-02", p, 0, f"protected path changed by direct push {c[:12]}"
                            )
                        )
        runs = {m.group(1) or m.group(2) for p in paths if (m := RUN_IN_PATH.match(p))}
        if len(runs) > 1:
            out.append(
                Finding(
                    "E-COMP-02", paths[0], 0, f"commit {c[:12]} changes {len(runs)} run folders"
                )
            )
        moved = {new for st, _old, new, p in rows if st == "A" and "/history/" in p}
        for st, old, _new, p in rows:
            if st in ("M", "D") and any_match(p, RECORD_GLOBS) and old not in moved:
                if _working_record(comp, c, p):
                    continue
                out.append(Finding("E-COMP-03", p, 0, f"changed in {c[:12]}"))


def _working_record(comp: Companion, commit: str, path: str) -> bool:
    """checks.json and review.json are working files until tsl decide writes verification.json.

    A sync point (resume, heartbeat) can commit them before the decision; re-running verify or
    the review then changes them. They are append-only once the attempt has been decided.
    """
    for suffix in (".checks.json", ".review.json"):
        if path.endswith(suffix) and "/history/" not in path:
            ver = path[: -len(suffix)] + ".verification.json"
            try:
                comp.git.out("cat-file", "-e", f"{commit}^:{ver}")
            except GitError:
                return True  # not decided before this commit
            return False
    return False


def _deny_hashes(path: Path | None) -> frozenset[str]:
    if path is None:
        return frozenset()
    lines = path.read_text(encoding="utf-8").splitlines()
    return frozenset(x.strip().lower() for x in lines if re.fullmatch(r"\s*[0-9a-fA-F]{64}\s*", x))


def _check_content(
    comp: Companion, files: list[str], deny: frozenset[str], out: list[Finding]
) -> int:
    from tsl.context.repoview import excluded
    from tsl.harness import detectors

    total = 0
    for rel in files:
        p = comp.path(rel)
        if not p.is_file():
            continue
        size = p.stat().st_size
        total += size
        if size > MAX_FILE_BYTES:
            out.append(Finding("E-COMP-05", rel, 0, f"{size} bytes > {MAX_FILE_BYTES}"))
            continue
        if excluded(rel, []):
            out.append(Finding("E-COMP-04", rel, 0, "excluded file pattern"))
            continue
        data = p.read_bytes()
        if b"\0" in data[:8192]:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for h in detectors.scan(text, deny_term_hashes=deny):
            if h.kind in ("secret", "pii", "term"):
                # file and line only: the matched value is never echoed (SDD-11 §7.3)
                out.append(Finding("E-COMP-04", rel, h.line, f"{h.kind} rule {h.rule_id}"))
    return total


def check(
    rt: Runtime,
    comp: Companion,
    base: str | None = None,
    event: str | None = None,
    deny_hashes: Path | None = None,
) -> dict[str, Any]:
    """Run every companion check; returns data with `codes` (empty when it passes)."""
    findings: list[Finding] = []
    files = _tracked(comp)
    _check_schemas(comp, files, findings)
    commits = _commits(comp, base)
    _check_history(comp, commits, base, event, findings)
    total = _check_content(comp, files, _deny_hashes(deny_hashes), findings)
    if total > MAX_REPO_BYTES:
        findings.append(Finding("E-COMP-05", ".", 0, f"repository {total} bytes"))
    codes = sorted({f.code for f in findings}, key=CODE_ORDER.index)
    pack: dict[str, Any] = {}
    try:
        from tsl.context.freshness import status as fresh_status

        fs = fresh_status(rt, comp, fetch=False)
        pack = {"state": fs["state"], "reasons": fs["reasons"]}
    except Exception as exc:  # informational only (SDD-12 §6.4)
        pack = {"state": "unknown", "reasons": [type(exc).__name__]}
    if "E-COMP-02" in codes:
        from tsl.telemetry.emit import emit

        emit(
            rt,
            "companion.policy_violation",
            {"system": comp.config.system.code, "code": "E-COMP-02"},
            enabled=comp.config.telemetry_enabled,
        )
    return {
        "result": "fail" if codes else "pass",
        "codes": codes,
        "findings": [f.as_dict() for f in findings[:200]],
        "files_checked": len(files),
        "commits_checked": len(commits),
        "pack": pack,
    }


def first_error(data: dict[str, Any]) -> TslError:
    code = data["codes"][0]
    f = next(x for x in data["findings"] if x["code"] == code)
    return TslError(
        code,
        path=f["path"],
        line=f["line"],
        detail=f["detail"],
        data=data,
    )


# ------------------------------------------------------------------------------- archive
def _record_files(files: list[str]) -> list[str]:
    extra = ["runs/*/approvals.md", "context/pack.signature.json"]
    return [f for f in files if any_match(f, [*RECORD_GLOBS, *extra])]


def archive(
    rt: Runtime, comp: Companion, reason: str, abandon_runs: bool
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    from tsl.identity import me as memod
    from tsl.identity.keys import load_signer
    from tsl.identity.signing import sign_object
    from tsl.state.store import RunStore, all_runs, read_state_raw
    from tsl.telemetry.emit import emit

    if not re.fullmatch(r"[a-z][a-z0-9_]{1,39}", reason):
        raise TslError("E-USE-01", detail="--reason must be a code like engagement_ended")
    me = memod.current_me(rt)
    if not memod.has_grant(me, {"admin"}, None):
        raise TslError(
            "E-AUTH-04",
            "Only an admin can archive a companion repo.",
            next="Ask a platform admin",
        )
    if comp.git.out("status", "--porcelain", "--untracked-files=no"):
        raise TslError("E-ENV-01", item="a clean clone of the companion repo")
    rec = memod.system_record(rt, comp.config.system.code)
    signer = load_signer(rt)
    open_runs = []
    for run_id in all_runs(comp):
        st = read_state_raw(comp, run_id) or {}
        if st.get("status") != "COMPLETED":
            open_runs.append((run_id, st))
    if open_runs and not abandon_runs:
        raise TslError("E-COMP-06", n=len(open_runs), data={"runs": [r for r, _ in open_runs]})
    from tsl.state.lock import lock_rel

    abandoned = []
    for run_id, st in open_runs:

        def apply(s: dict[str, Any]) -> None:
            s["status"], s["end_reason"], s["cursor"] = "COMPLETED", "archived", None

        RunStore(rt, comp, run_id).update(apply)
        lk = comp.path(lock_rel(st))
        if lk.is_file():
            lk.unlink()
        abandoned.append(run_id)
    if abandoned:
        try:
            comp.git.commit("tsl: abandon open runs before archive", ["runs"])
        except GitError as exc:
            raise exc.tsl() from None
    result = check(rt, comp)
    if result["codes"]:
        raise first_error(result)
    files = _tracked(comp)
    records = _record_files(files)
    listing = "\n".join(f"{r} {sha256_bytes(comp.path(r).read_bytes())}" for r in records)
    body = {
        "schema": ARCHIVE_SCHEMA,
        "system": comp.config.system.code,
        "last_commit": comp.git.head(),
        "runs": len(all_runs(comp)),
        "records": len(records),
        "records_sha256": sha256_text(listing),
        "reason_code": reason,
        "archived_by": str(me.get("pseudonym", "admin")),
        "archived_at": iso(rt.clock()),
    }
    signed = sign_object(body, signer.key_id, signer.private)
    from tsl.schemas.registry import require_valid

    require_valid(ARCHIVE_SCHEMA, signed, ARCHIVE_FILE)
    write_json(comp.path(ARCHIVE_FILE), signed)
    branch = comp.config.companion_branch
    try:
        comp.git.commit(f"tsl: archive companion ({reason})", [ARCHIVE_FILE])
        comp.git.run("tag", "-f", "archive/final")
    except GitError as exc:
        raise exc.tsl() from None
    warnings: list[dict[str, str]] = []
    pushed = comp.git.has_remote() and comp.git.sync_push(branch)
    if pushed:
        pushed = comp.git.ok("push", "-q", "origin", "refs/tags/archive/final")
    if not pushed:
        raise TslError(
            "E-GIT-01",
            op="push",
            detail="archive commit and tag stay local",
            data={"archive_path": ARCHIVE_FILE},
        )
    prev = str(rec.get("lifecycle_state") or "ACTIVE")
    emit(
        rt,
        "companion.lifecycle",
        {"system": comp.config.system.code, "from": prev, "to": "ARCHIVED", "reason_code": reason},
        enabled=comp.config.telemetry_enabled,
    )
    data = {
        "archive_path": ARCHIVE_FILE,
        "last_commit": body["last_commit"],
        "runs": body["runs"],
        "records": body["records"],
        "records_sha256": body["records_sha256"],
        "tag": "archive/final",
        "abandoned": abandoned,
        "key_id": signer.key_id,
        "archive_sha256": sha256_text(json.dumps(signed, sort_keys=True)),
    }
    return data, warnings
