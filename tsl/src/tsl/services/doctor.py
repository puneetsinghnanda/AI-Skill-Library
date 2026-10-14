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
from tsl.core.errors import TslError
from tsl.core.repo import find_root
from tsl.core.runtime import Runtime


def _chk(cid: str, status: str, detail: str = "", fix: str = "") -> dict[str, str]:
    return {"id": cid, "status": status, "detail": detail, "fix": fix}


def doctor(
    rt: Runtime, plugin_version: str | None, cwd: Path
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
                f"uv tool install truminds-tsl=={want}",
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
    warnings.append({"code": "E-ENV-02", "message": "Full-disk encryption cannot be confirmed."})
    data = {"checks": checks}
    failed = [c for c in checks if c["status"] == "fail"]
    if failed:
        raise TslError(
            "E-ENV-01", item=failed[0]["id"], data=data, next=failed[0]["fix"] or "tsl doctor"
        )
    return data, warnings
