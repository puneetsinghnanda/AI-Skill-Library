"""Local checks of `tsl verify --self-check --local` (harness/local.py, roadmap A3).

A fake runner stands in for npm, node, tsc, eslint, uv and ruff, so every branch runs without a
toolchain; the output shapes are the real tools' (tsc --pretty false, eslint -f json, ruff SARIF)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from tsl.harness import local


class Fake:
    """Answers each command by the first matching key in `answers`; records every call."""

    def __init__(self, answers: dict[str, tuple[int | None, str]]) -> None:
        self.answers = answers
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str], cwd: Path, timeout: int) -> tuple[int | None, str]:
        self.calls.append(cmd)
        line = " ".join(cmd)
        for key, ans in self.answers.items():
            if key in line:
                return ans
        return 0, ""

    def ran(self, word: str) -> bool:
        return any(word in " ".join(c) for c in self.calls)


@pytest.fixture(autouse=True)
def _tools_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tsl.harness.local.shutil.which", lambda name: f"/usr/bin/{name}")


def _node_repo(tmp_path: Path, *, installed: bool = True, same: bool = True) -> Path:
    root = tmp_path / "repo"
    (root / "api/src").mkdir(parents=True)
    (root / "api/test").mkdir(parents=True)
    (root / "api/tsconfig.json").write_text("{}")
    (root / "api/src/a.ts").write_text("export const a = 1\n")
    (root / "api/src/b.js").write_text("x\n")
    (root / "api/test/a.test.ts").write_text("x\n")
    lock = {"packages": {"": {}, "node_modules/typescript": {"version": "5.6.3"},
                         "node_modules/fsevents": {"version": "2.3.3", "optional": True},
                         "api": {"link": True}}}  # fmt: skip
    (root / "package.json").write_text("{}")
    (root / "package-lock.json").write_text(json.dumps(lock))
    if installed:
        nm = root / "node_modules"
        (nm / "typescript/bin").mkdir(parents=True)
        (nm / "typescript/bin/tsc").write_text("")
        (nm / "eslint/bin").mkdir(parents=True)
        (nm / "eslint/bin/eslint.js").write_text("")
        hidden = {
            "packages": {"node_modules/typescript": {"version": "5.6.3" if same else "5.4.0"}}
        }
        (nm / ".package-lock.json").write_text(json.dumps(hidden))
    return root


FILES = ["api/src/a.ts", "api/src/b.js", "api/test/a.test.ts"]
TSC_OUT = (
    "api/src/other.ts(3,1): error TS2741: Property 'visitSummary' is missing.\n"
    "api/src/a.ts(1,14): error TS2322: Type 'string' is not assignable to type 'number'.\n"
    "  Extra detail line\n"
)


def _eslint_json(root: Path, *msgs: tuple[str, int, str | None]) -> str:
    by: dict[str, list[dict[str, Any]]] = {}
    for rel, sev, rule in msgs:
        by.setdefault(rel, []).append(
            {"ruleId": rule, "severity": sev, "message": f"bad {rel}", "line": 2, "column": 9,
             **({"fatal": True} if rule is None else {})}
        )  # fmt: skip
    return json.dumps([{"filePath": str(root / rel), "messages": m} for rel, m in by.items()])


def _run(
    root: Path, fake: Fake, files: list[str] = FILES, tmp: Path | None = None
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    log = (tmp or root.parent) / "tool-log.jsonl"
    return local.check_repos([("app", "node-22@1", root, files)], log, fake)


# ------------------------------------------------------------------------------- node
def test_node_typecheck_and_lint_errors_become_fix_items(tmp_path: Path) -> None:
    root = _node_repo(tmp_path)
    fake = Fake({
        "tsc": (2, TSC_OUT),
        "eslint.js": (1, _eslint_json(root, ("api/src/b.js", 2, "no-unused-vars"), ("api/src/b.js", 1, "semi"),
                                      ("api/test/a.test.ts", 2, None))),
    })  # fmt: skip
    info, fix = _run(root, fake)
    assert not fake.ran("npm ci")  # installed packages match the lock: no install
    tsc = next(c for c in fake.calls if "tsc" in " ".join(c))
    assert tsc[-2:] == ["-p", "api/tsconfig.json"] and "--noEmit" in tsc
    assert info["status"] == "fail"
    assert [(c["name"], c["status"], c.get("errors")) for c in info["checks"]] == [
        ("typecheck", "fail", 2),
        ("lint", "fail", 2),
    ]
    by = {f["id"]: f["detail"] for f in fix}
    assert {f["kind"] for f in fix} == {"local"}
    assert (
        by["typecheck"].splitlines()
        == [
            "app: 2 typecheck error(s), 1 in files this step changed:",
            "api/src/a.ts:1:14 TS2322: Type 'string' is not assignable to type 'number'.",  # own file first
            "api/src/other.ts:3:1 TS2741: Property 'visitSummary' is missing.",
        ]
    )
    assert "api/src/b.js:2:9 no-unused-vars: bad api/src/b.js" in by["lint"]
    assert "api/test/a.test.ts:2:9 parse: bad api/test/a.test.ts" in by["lint"]
    assert "semi" not in by["lint"]  # warnings never fail lint


def test_node_clean_run_passes(tmp_path: Path) -> None:
    root = _node_repo(tmp_path)
    info, fix = _run(root, Fake({"eslint.js": (0, "[]")}))
    assert info == {
        "status": "pass",
        "checks": [
            {"repo": "app", "name": "typecheck", "status": "pass"},
            {"repo": "app", "name": "lint", "status": "pass"},
        ],
    }
    assert fix == []


@pytest.mark.parametrize(
    ("installed", "same", "why"),
    [
        (False, True, "node_modules is missing"),
        (
            True,
            False,
            "1 installed package(s) differ from package-lock.json (node_modules/typescript)",
        ),
    ],
)
def test_node_installs_only_when_the_install_does_not_match_the_lock(
    tmp_path: Path, installed: bool, same: bool, why: str
) -> None:
    root = _node_repo(tmp_path, installed=installed, same=same)
    fake = Fake({"eslint.js": (0, "[]")})
    info, _ = _run(root, fake)
    ci = next(c for c in fake.calls if "ci" in c)
    assert ci[1:] == [
        "ci",
        "--ignore-scripts",
        "--no-audit",
        "--no-fund",
    ]  # never runs package scripts
    assert info["installed"] == [{"repo": "app", "reason": why}]


def test_node_failed_install_is_not_run_not_an_item(tmp_path: Path) -> None:
    root = _node_repo(tmp_path, installed=False)
    info, fix = _run(
        root, Fake({"npm ci": (1, "npm error code ENOTFOUND\nnpm error network request failed")})
    )
    assert fix == [] and info["status"] == "skip"
    assert info["not_run"][0]["detail"].startswith("npm ci failed: ")


def test_node_tsconfig_error_without_a_position_is_reported(tmp_path: Path) -> None:
    root = _node_repo(tmp_path)
    _, fix = _run(
        root,
        Fake(
            {
                "tsc": (1, "error TS5023: Unknown compiler option 'strictt'.\n"),
                "eslint.js": (0, "[]"),
            }
        ),
    )
    assert "api/tsconfig.json: error TS5023" in fix[0]["detail"]


def test_node_eslint_crash_is_skipped_not_an_item(tmp_path: Path) -> None:
    root = _node_repo(tmp_path)
    info, fix = _run(
        root, Fake({"eslint.js": (2, "Oops! Something went wrong! :(\nTypeError: bad config")})
    )
    assert fix == []
    lint = next(c for c in info["checks"] if c["name"] == "lint")
    assert lint["status"] == "skip" and "TypeError: bad config" in lint["detail"]


def test_tools_not_installed_or_nothing_to_check_is_a_skip(tmp_path: Path) -> None:
    root = _node_repo(tmp_path)
    info, fix = _run(root, Fake({}), files=["README.md"])
    assert fix == [] and info["status"] == "skip"
    assert {c["detail"] for c in info["checks"]} == {
        "no TypeScript file changed",
        "no JavaScript or TypeScript file changed",
    }


# ------------------------------------------------------------------------------ guards
def test_a_step_that_changed_package_or_lint_config_is_not_run_locally(tmp_path: Path) -> None:
    root = _node_repo(tmp_path)
    for changed in ("package.json", "package-lock.json", "eslint.config.mjs", "web/.eslintrc.json"):
        fake = Fake({})
        info, fix = _run(root, fake, files=[*FILES, changed])
        assert fake.calls == [] and fix == [] and info["status"] == "skip", changed
        assert changed in info["not_run"][0]["detail"]


def test_a_run_that_wrote_into_an_install_is_not_run_locally(tmp_path: Path) -> None:
    root = _node_repo(tmp_path)
    log = tmp_path / "tool-log.jsonl"
    log.write_text(
        json.dumps({"tool": "Read", "target": f"{root}/node_modules/x.js"}) + "\n"
        + json.dumps({"tool": "Edit", "target": f"{root}\\node_modules\\typescript\\lib\\tsc.js"}) + "\n"
    )  # fmt: skip
    fake = Fake({})
    info, fix = local.check_repos([("app", "node-22@1", root, FILES)], log, fake)
    assert fake.calls == [] and fix == [] and info["status"] == "skip"
    assert "wrote into an install folder" in info["detail"]


def test_repos_without_changes_clone_or_known_profile(tmp_path: Path) -> None:
    root = _node_repo(tmp_path)
    info, _ = local.check_repos(
        [
            ("a", "node-22@1", root, []),
            ("b", "go-1@1", root, FILES),
            ("c", "node-22@1", None, FILES),
        ],
        tmp_path / "none.jsonl",
        Fake({}),
    )
    assert info == {
        "status": "skip",
        "checks": [],
        "not_run": [
            {"repo": "b", "detail": "no local checks for its profile"},
            {"repo": "c", "detail": "no clone"},
        ],
    }


# ----------------------------------------------------------------------------- python
def _py_repo(tmp_path: Path, synced: bool) -> Path:
    root = tmp_path / "py"
    (root / "app").mkdir(parents=True)
    (root / "app/x.py").write_text("x = (\n")
    (root / "app/y.py").write_text("import os\n")
    (root / "uv.lock").write_text("lock v1\n")
    if synced:
        (root / ".venv").mkdir()
        from tsl.core.hashing import sha256_file

        (root / ".venv/.tsl-uv-lock.sha256").write_text(sha256_file(root / "uv.lock"))
    return root


def test_python_compile_and_ruff_sarif(tmp_path: Path) -> None:
    root = _py_repo(tmp_path, synced=True)
    sarif = {"runs": [{"results": [{
        "level": "error", "ruleId": "F401", "message": {"text": "`os` imported but unused"},
        "locations": [{"physicalLocation": {"artifactLocation": {"uri": (root / "app/y.py").as_uri()},
                                            "region": {"startLine": 1, "startColumn": 8}}}]}]}]}  # fmt: skip
    fake = Fake({
        "py_compile app/x.py": (1, '  File "app/x.py", line 1\n    x = (\n        ^\nSyntaxError: \'(\' was never closed\n'),
        "check --output-format sarif": (1, json.dumps(sarif)),
    })  # fmt: skip
    info, fix = local.check_repos(
        [("svc", "python-312@1", root, ["app/x.py", "app/y.py"])], tmp_path / "l", fake
    )
    assert not fake.ran("sync --frozen")  # uv.lock unchanged since the last sync
    by = {f["id"]: f["detail"] for f in fix}
    assert "app/x.py: SyntaxError: '(' was never closed" in by["compile"]
    assert "app/y.py:1:8 F401: `os` imported but unused" in by["lint"]
    assert info["status"] == "fail"


def test_python_syncs_when_the_lock_changed(tmp_path: Path) -> None:
    root = _py_repo(tmp_path, synced=True)
    (root / "uv.lock").write_text("lock v2\n")
    fake = Fake({"check --output-format sarif": (0, json.dumps({"runs": [{"results": []}]}))})
    info, _ = local.check_repos([("svc", "python-312@1", root, ["app/y.py"])], tmp_path / "l", fake)
    assert fake.ran("sync --frozen")
    assert info["installed"] == [{"repo": "svc", "reason": "uv.lock changed since tsl last synced"}]
    fake2 = Fake({"check --output-format sarif": (0, json.dumps({"runs": [{"results": []}]}))})
    local.check_repos([("svc", "python-312@1", root, ["app/y.py"])], tmp_path / "l", fake2)
    assert not fake2.ran("sync --frozen")  # the stamp now matches


# ---------------------------------------------------------------------------- run_tool
def test_run_tool_never_raises() -> None:
    code, out = local.run_tool(["/no/such/program-xyz"], Path.cwd(), 5)
    assert code is None and "could not start" in out
    code, out = local.run_tool([sys.executable, "-c", "import time; time.sleep(5)"], Path.cwd(), 1)
    assert code is None and "timed out after 1 s" in out
    code, out = local.run_tool(
        [sys.executable, "-c", "import sys; print('o'); print('e', file=sys.stderr); sys.exit(3)"],
        Path.cwd(),
        30,
    )
    assert code == 3 and "o" in out and "e" in out
