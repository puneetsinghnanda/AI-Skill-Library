"""tsl doctor (SDD-04 §6.3)."""

from __future__ import annotations

import platform
import re
import shutil
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

from tsl.core.clock import parse_iso
from tsl.core.errors import UPDATE_HINT, TslError
from tsl.core.repo import find_root
from tsl.core.runtime import Runtime


def _chk(cid: str, status: str, detail: str = "", fix: str = "") -> dict[str, str]:
    return {"id": cid, "status": status, "detail": detail, "fix": fix}


def _run_checks(rt: Runtime, cwd: Path) -> list[dict[str, str]]:
    """Run-readiness checks (tsl doctor --run): everything that has stopped real runs part-way.
    Live: the service must accept this laptop's sign-in and key, clones must match GitHub."""
    from tsl.gitops.git import Git, GitError
    from tsl.identity.keys import active_info, wake_service

    checks: list[dict[str, str]] = []
    url = rt.org.service_url
    awake = wake_service(rt)
    checks.append(
        _chk(
            "service-awake",
            "pass" if awake else "fail",
            url if awake else f"{url} did not answer within a minute",
            f"Open {url} in a browser, wait for it to load, then repeat",
        )
    )
    if awake:
        try:
            res = rt.insights.get_me(rt.token())
            ok = res.status == 200
            checks.append(
                _chk(
                    "sign-in-live",
                    "pass" if ok else "fail",
                    "the service accepts your sign-in"
                    if ok
                    else f"the service refused your sign-in (HTTP {res.status})",
                    "tsl login",
                )
            )
        except TslError as exc:
            checks.append(_chk("sign-in-live", "fail", exc.message, "tsl login"))
        except Exception as exc:  # network trouble after waking
            checks.append(_chk("sign-in-live", "fail", type(exc).__name__, "Repeat in a minute"))
        info = active_info(rt) or {}
        try:
            # Read the service's copy, not a local cache: approvals are verified against it.
            mine = rt.insights.get_key(rt.token(), str(info.get("key_id")))
            ok = mine.status == 200
            checks.append(
                _chk(
                    "key-registered",
                    "pass" if ok else "fail",
                    str(info.get("key_id"))
                    if ok
                    else "your signing key is not registered on the service",
                    "tsl login",
                )
            )
        except Exception as exc:
            checks.append(_chk("key-registered", "fail", type(exc).__name__, "tsl login"))
    checks.append(
        _chk(
            "docker-running",
            "pass" if rt.verifier.available() else "fail",
            "",
            "Start Docker Desktop and wait for 'Engine running' (code steps need it)",
        )
    )
    root = find_root(cwd)
    if root is None:
        checks.append(
            _chk(
                "companion",
                "fail",
                f"{cwd} is not a companion repo (no tsl.yaml)",
                "cd into your companion repo",
            )
        )
        return checks
    from tsl.core.repo import Companion

    comp = Companion(root)
    git = Git(root)
    attrs = root / ".gitattributes"
    lf = attrs.is_file() and "eol=lf" in attrs.read_text(encoding="utf-8", errors="replace")
    checks.append(
        _chk(
            "line-endings",
            "pass" if lf else "fail",
            ".gitattributes keeps LF" if lf else ".gitattributes with eol=lf is missing",
            "Add a .gitattributes file containing '* text=auto eol=lf', commit and push",
        )
    )
    unmerged = git.run("diff", "--name-only", "--diff-filter=U", check=False).stdout.split()
    checks.append(
        _chk(
            "no-conflicts",
            "fail" if unmerged else "pass",
            f"conflicted: {unmerged[0]}" if unmerged else "",
            f"Keep GitHub's version: git checkout HEAD -- {unmerged[0]}" if unmerged else "",
        )
    )
    edited = git.run("status", "--porcelain", "--untracked-files=no", check=False).stdout.split(
        "\n"
    )
    edited = [line[3:] for line in edited if line.strip() and not line.startswith("UU")]
    checks.append(
        _chk(
            "no-local-edits",
            "warn" if edited else "pass",
            f"uncommitted edits: {', '.join(edited[:3])}" if edited else "",
            "Never edit runs/ files by hand; discard with git checkout HEAD -- <file>",
        )
    )
    stashed = git.run("stash", "list", check=False).stdout.strip()
    checks.append(
        _chk(
            "no-leftover-stash",
            "warn" if stashed else "pass",
            stashed.splitlines()[0] if stashed else "",
            "Inspect with git stash show -p; drop it with git stash drop when it is not needed",
        )
    )
    branches = {r.name: r.default_branch for r in comp.config.product_repos}
    for name, path in comp.local_paths().items():
        cid = f"product-{name}"
        if not (path / ".git").exists():
            checks.append(
                _chk(cid, "fail", f"{path} is not a git clone", "Fix the path in .tsl/local.yaml")
            )
            continue
        pg = Git(path)
        branch = branches.get(name, "main")
        try:
            pg.fetch()
            head, remote = pg.out("rev-parse", "HEAD"), pg.out("rev-parse", f"origin/{branch}")
        except GitError as exc:
            checks.append(_chk(cid, "fail", str(exc), "Check access to the product repo"))
            continue
        same = head == remote
        checks.append(
            _chk(
                cid,
                "pass" if same else "fail",
                f"at origin/{branch} {remote[:7]}"
                if same
                else f"{path} is at {head[:7]}, origin/{branch} is {remote[:7]}",
                f"git -C {path} checkout {branch}; git -C {path} pull",
            )
        )
    try:
        from tsl.context.freshness import status

        st = status(rt, comp, fetch=True)
        checks.append(
            _chk(
                "pack-fresh",
                "pass" if st["state"] == "fresh" else "fail",
                f"context pack {st['state']}",
                "tsl context build, review the sections, tsl context sign",
            )
        )
    except TslError as exc:
        checks.append(_chk("pack-fresh", "fail", exc.message, exc.next))
    return checks


def doctor(
    rt: Runtime, plugin_version: str | None, cwd: Path, run: bool = False
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    checks: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    checks.append(
        _chk(
            "python",
            "pass" if sys.version_info[:2] == (3, 12) else "fail",
            platform.python_version(),
            "Install Python 3.12",
        )
    )
    checks.append(
        _chk(
            "uv", "pass" if shutil.which("uv") or shutil.which("pipx") else "fail", "", "Install uv"
        )
    )
    git_ok, gv = False, ""
    if shutil.which("git"):
        out = subprocess.run(
            ["git", "--version"], capture_output=True, text=True, check=False
        ).stdout
        m = re.search(r"(\d+)\.(\d+)", out)
        gv = out.strip()
        git_ok = m is not None and (int(m.group(1)), int(m.group(2))) >= (2, 40)
    checks.append(_chk("git", "pass" if git_ok else "fail", gv, "Install git 2.40 or later"))
    checks.append(
        _chk(
            "docker",
            "pass" if rt.verifier.available() else "warn",
            "",
            "Start Docker (needed for H3 verifier containers)",
        )
    )
    want = plugin_version
    if want is None:
        try:
            want = rt.plugin_version()
        except TslError:
            want = None
    if want is None:
        checks.append(
            _chk("version", "warn", "plugin not found", "Open a Claude Code session once")
        )
    else:
        checks.append(
            _chk(
                "version",
                "pass" if want == rt.tsl_version else "fail",
                f"tsl {rt.tsl_version}, plugin {want}",
                UPDATE_HINT,
            )
        )
    try:
        rt.keystore.get("doctor-probe")
        checks.append(_chk("keychain", "pass"))
    except TslError:
        checks.append(_chk("keychain", "fail", "no allowed keyring backend", "See SDD-07 §4.3"))
    try:
        rt.token()
        checks.append(_chk("login", "pass", f"provider {rt.org.provider}"))
    except TslError:
        checks.append(_chk("login", "fail", "no silent token", "tsl login"))
    from tsl.identity.keys import active_info, load_signer

    info = active_info(rt)
    try:
        load_signer(rt)
        exp = parse_iso(str((info or {}).get("expires_at")))
        if exp - rt.clock() < timedelta(days=14):
            checks.append(_chk("key", "warn", "key expires within 14 days", "tsl keys rotate"))
        else:
            checks.append(_chk("key", "pass", str((info or {}).get("key_id"))))
    except TslError as exc:
        checks.append(_chk("key", "fail", exc.code, "tsl login"))
    checks.append(
        _chk("service", "pass" if rt.insights.health() else "warn", "", "Check the network")
    )
    stats = rt.outbox().stats()
    age = rt.outbox().oldest_pending_age()
    ok = stats["dead"] == 0 and (age is None or age < timedelta(hours=24))
    checks.append(
        _chk(
            "outbox",
            "pass" if ok else "warn",
            f"{stats['pending']} pending, {stats['dead']} dead",
            "tsl events flush",
        )
    )
    root = find_root(cwd)
    if root is not None:
        from tsl.core.repo import Companion

        try:
            comp = Companion(root)
            _ = comp.config
            from tsl.context.freshness import status

            st = status(rt, comp, fetch=False)
            checks.append(
                _chk(
                    "repo",
                    "pass" if st["state"] == "fresh" else "warn",
                    f"pack {st['state']}",
                    "tsl context build, then tsl context sign",
                )
            )
        except TslError as exc:
            checks.append(_chk("repo", "fail", exc.message, "tsl validate tsl.yaml"))
    if run:
        checks += _run_checks(rt, cwd)
    warnings.append({"code": "E-ENV-02", "message": "Full-disk encryption cannot be confirmed."})
    data = {"checks": checks}
    failed = [c for c in checks if c["status"] == "fail"]
    if failed:
        raise TslError(
            "E-ENV-01", item=failed[0]["id"], data=data, next=failed[0]["fix"] or "tsl doctor"
        )
    return data, warnings
