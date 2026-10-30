"""tsl init: set up an empty companion repo (SDD-12 §5.3, SDD-04 §6.4)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tsl.context.build import JUDGEMENT, _template
from tsl.core.errors import TslError
from tsl.core.jsonio import atomic_write, dump_yaml
from tsl.core.runtime import Runtime
from tsl.gitops.git import Git, GitError
from tsl.identity import me as memod
from tsl.telemetry.emit import emit

GITIGNORE = """# tsl companion repo (SDD-12 §3.1)
.tsl/
**/.local.lock
node_modules/
dist/
build/
.env
.env.*
*.pem
*.key
# verifier output stays local: scanner reports can quote what they found (hashes are recorded)
runs/*/verifier/
"""

# Where CI installs tsl from; the plugin marketplace repo (SDD-05 §6.2).
LIBRARY_URL = "https://github.com/puneetsinghnanda/AI-Skill-Library.git"

CI_WORKFLOW = """name: tsl-companion-check
# Pushes to main (run commits) and pull requests; a feature branch is checked by its pull request.
on:
  push:
    branches: [main]
  pull_request:
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: astral-sh/setup-uv@v6
      - name: Install tsl from the skill library (it is not on PyPI; the check needs no org file)
        run: |
          git clone --depth 1 "$TSL_LIBRARY" "$RUNNER_TEMP/lib"
          uv tool install --python 3.12 "$RUNNER_TEMP/lib/tsl"
        env:
          TSL_LIBRARY: {library}
      - name: tsl companion check (only the commits this push or pull request adds)
        env:
          EVENT: ${{{{ github.event_name }}}}
          BEFORE: ${{{{ github.event.before }}}}
          PR_BASE: ${{{{ github.event.pull_request.base.sha }}}}
        run: |
          base="$BEFORE"
          if [ "$EVENT" = pull_request ]; then base="$PR_BASE"; fi
          args=(--event "$EVENT" --json)
          if [ -n "$base" ] && [ "$base" != 0000000000000000000000000000000000000000 ]; then
            args+=(--base "$base")
          fi
          tsl companion check "${{args[@]}}"
"""


def parse_product_repo(spec: str) -> dict[str, Any]:
    head, *opts = spec.split(",")
    if "=" not in head:
        raise TslError("E-USE-01", detail=f"--product-repo {spec}: use <name>=<url>", cmd="init")
    name, url = head.split("=", 1)
    repo: dict[str, Any] = {"name": name, "url": url, "path": ".", "default_branch": "main"}
    for o in opts:
        k, _, v = o.partition("=")
        key = {"path": "path", "branch": "default_branch", "verifier": "verifier_profile"}.get(k)
        if key is None or not v:
            raise TslError("E-USE-01", detail=f"--product-repo option {o}", cmd="init")
        repo[key] = v
    if "verifier_profile" not in repo:
        raise TslError(
            "E-USE-01",
            detail=f"--product-repo {name}: verifier=<profile@major> is required",
            cmd="init",
        )
    return repo


def init(
    rt: Runtime, system: str, product_repos: list[str], clone_dir: Path | None
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    if not product_repos:
        raise TslError("E-USE-01", detail="at least one --product-repo", cmd="init")
    repos = [parse_product_repo(s) for s in product_repos]
    rec = memod.system_record(rt, system)
    if not rec.get("companion_repo"):
        raise TslError("E-INIT-01", system=system)
    memod.require_grant(rt, {"tech_lead"}, system, "E-AUTH-04", action="init")
    consent = rec.get("consent") or {}
    for s in ("code_processing", "companion_storage"):
        if not consent.get("recorded") or s not in (consent.get("scope") or []):
            raise TslError("E-CONS-01", client=rec.get("client", "?"), scope=s)
    companion = str(rec["companion_repo"])
    name = companion.split("/", 1)[1]
    target = (clone_dir or Path.cwd()) / name
    url = rt.org.companion_remote_template.format(repo=companion)
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    try:
        Git(parent).run("clone", "-q", url, str(target), timeout=120)
    except GitError as exc:
        raise exc.tsl() from None
    g = Git(target)
    if g.resolve("HEAD") is not None or g.out("ls-remote", "--heads", "origin"):
        raise TslError("E-INIT-02", repo=companion)
    g.run("symbolic-ref", "HEAD", "refs/heads/main")
    cfg = {
        "schema": "tsl-config.v1",
        "system": {
            "code": rec.get("code", system),
            "project": rec["project"],
            "client": rec["client"],
        },
        "companion": {"repo": companion, "default_branch": "main"},
        "product_repos": repos,
        "gates": {"self_approval": False, "lock_timeout_hours": 24},
        "pr": {"branch_prefix": "tsl/", "labels": ["truminds"]},
        "telemetry": {"enabled": True},
    }
    from tsl.schemas.registry import require_valid

    require_valid("tsl-config.v1", cfg, "tsl.yaml")
    client, sysc = str(rec["client"]).lower(), str(rec.get("code", system)).lower()
    org = companion.split("/", 1)[0]
    files: dict[str, str] = {
        "tsl.yaml": dump_yaml(cfg),
        "policy.yaml": dump_yaml({"schema": "policy.v2", "merge_and_deploy": "never"}),
        ".gitignore": GITIGNORE,
        ".gitattributes": "* text=auto eol=lf\n",
        "CODEOWNERS": (
            f"tsl.yaml @{org}/tsl-{client}-{sysc}-leads\n"
            f"policy.yaml @{org}/tsl-{client}-{sysc}-leads\n"
            f"context/ @{org}/tsl-{client}-{sysc}-leads\n.github/ @{org}/tsl-admins\n"
        ),
        "README.md": (
            f"# {companion}\n\nCompanion repo for system {rec.get('code', system)}: run state, "
            "artifacts, signed records and the context pack. Written by `tsl`; see SDD-12.\n"
        ),
        ".github/workflows/tsl-companion-check.yml": CI_WORKFLOW.format(library=LIBRARY_URL),
        "runs/active/.gitkeep": "",
        "artifacts/.gitkeep": "",
    }
    me = memod.current_me(rt)
    for sec in JUDGEMENT:
        files[f"context/{sec}.md"] = _template(sec, str(me.get("pseudonym", "tl-0000")))
    for rel, text in files.items():
        atomic_write(target / rel, text)
    local = {
        "schema": "tsl-local.v1",
        "product_repos": {r["name"]: str((target.parent / r["name"]).resolve()) for r in repos},
    }
    require_valid("tsl-local.v1", local, ".tsl/local.yaml")
    atomic_write(target / ".tsl" / "local.yaml", dump_yaml(local))
    try:
        sha = g.commit("tsl: init companion repo", list(files))
        if not g.push("main"):
            raise TslError("E-GIT-01", op="push", detail="initial commit not pushed")
    except GitError as exc:
        raise exc.tsl() from None
    emit(
        rt,
        "companion.lifecycle",
        {"system": system, "from": "PROVISIONED", "to": "INITIALISED", "reason_code": "init"},
    )
    return {"files": sorted(files), "commit": sha, "path": str(target)}, []


SAFE = re.compile(r"^[A-Z][A-Z0-9-]{1,31}$")
