"""A failed lint step shows its errors, for the files the step changed (roadmap C4).

ESLint and ruff write their results only to lint.sarif; lint.log stays empty, so the H3 detail
used to end at "lint exit 1; log .../lint.log" and the retry had to guess what to fix.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from e2e_steps import SESSION
from helpers import World
from test_e2e_code import _code_run
from tsl.harness.verifier import DockerVerifier, StepResult, sarif_errors
from tsl.harness.verify import LINT_DETAIL_MAX, _with_log

REL = "runs/r/verifier/impl/a1"
LINT = StepResult("lint", "fail", 1, 10, None, "E-H3-03", "lint exit 1", "lint.log")


def _res(path: str, line: int, rule: str, msg: str, **extra: Any) -> dict[str, Any]:
    loc = {
        "physicalLocation": {
            "artifactLocation": {"uri": f"file:///cache/w/{path}"},
            "region": {"startLine": line, "startColumn": 3},
        }
    }
    return {"ruleId": rule, "level": "error", "message": {"text": msg}, "locations": [loc], **extra}


def _sarif(out: Path, results: list[dict[str, Any]]) -> None:
    doc = {
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "ESLint"}}, "results": results}],
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "lint.sarif").write_text(json.dumps(doc), encoding="utf-8")


def _detail(out: Path, files: list[str] | None, log: str = "") -> str:
    out.mkdir(parents=True, exist_ok=True)
    (out / "lint.log").write_text(log, encoding="utf-8")
    return _with_log(LINT, out, REL, "lint.sarif", files)


def test_errors_in_changed_files_are_listed_first(tmp_path: Path) -> None:
    _sarif(
        tmp_path,
        [
            _res("api/src/app.ts", 4, "no-unused-vars", "'x' is assigned a value but never used."),
            _res("api/src/old.ts", 9, "eqeqeq", "Expected '===' and instead saw '=='."),
            _res("api/src/app.ts", 7, "semi", "Missing semicolon.", level="warning"),
            _res("api/src/app.ts", 8, "no-console", "Unexpected console.", suppressions=[{}]),
        ],
    )
    d = _detail(tmp_path, ["api/src/app.ts"])
    assert d == (
        f"lint exit 1; report {REL}/lint.sarif: 1 error(s) in the files this step changed"
        " (1 more in other files): api/src/app.ts:4:3 no-unused-vars:"
        " 'x' is assigned a value but never used."
    )


def test_errors_outside_the_change_are_shown_and_marked(tmp_path: Path) -> None:
    """They still fail H3, so the retry must see them, and know it did not cause them."""
    _sarif(tmp_path, [_res("api/src/old.ts", 9, "eqeqeq", "Expected '==='.")])
    d = _detail(tmp_path, ["api/src/app.ts"])
    assert ": none in the files this step changed, 1 in other files: " in d
    assert d.endswith("other files: api/src/old.ts:9:3 eqeqeq: Expected '==='.")


def test_many_errors_fit_the_detail_and_say_how_many_are_left(tmp_path: Path) -> None:
    msg = "Unsafe member access on an `any` value, which the type checker cannot follow."
    _sarif(tmp_path, [_res("api/src/app.ts", i, "no-unsafe-member-access", msg) for i in range(40)])
    d = _detail(tmp_path, ["api/src/app.ts"])
    assert len(d) <= LINT_DETAIL_MAX
    assert ": 40 error(s) in the files this step changed: api/src/app.ts:0:3 " in d
    shown = d.count("no-unsafe-member-access")
    assert 1 <= shown < 40 and d.endswith(f"... {40 - shown} more")


def test_no_changed_files_known_lists_all_errors(tmp_path: Path) -> None:
    _sarif(tmp_path, [_res("a.py", 1, "F401", "`os` imported but unused")])
    assert _detail(tmp_path, None).endswith(": 1 error(s): a.py:1:3 F401: `os` imported but unused")


def test_a_linter_crash_shows_the_error_lines_of_the_log(tmp_path: Path) -> None:
    """No SARIF errors (ESLint could not load its config): the log says why."""
    log = (
        "\nOops! Something went wrong! :(\n\nESLint: 9.1.0\n\n"
        'TypeError: Key "rules": Key "semi": Could not find plugin "@stylistic".\n'
        "npm error code 2\n"
    )
    d = _detail(tmp_path, ["api/src/app.ts"], log)
    assert d == (
        f"lint exit 1; log {REL}/lint.log: "
        'TypeError: Key "rules": Key "semi": Could not find plugin "@stylistic".'
    )


def test_without_a_report_or_error_line_the_log_tail_stays(tmp_path: Path) -> None:
    d = _detail(tmp_path, ["api/src/app.ts"], "step one\nstep two\n")
    assert d == f"lint exit 1; log {REL}/lint.log: step one | step two"


def test_other_steps_keep_the_log_tail(tmp_path: Path) -> None:
    _sarif(tmp_path, [_res("api/src/app.ts", 4, "no-unused-vars", "unused")])
    (tmp_path / "build.log").write_text("compiling\nfailed\n", encoding="utf-8")
    build = StepResult("build", "fail", 2, 10, None, "E-H3-01", "build exit 2", "build.log")
    assert _with_log(build, tmp_path, REL, None, ["api/src/app.ts"]) == (
        f"build exit 2; log {REL}/build.log: compiling | failed"
    )


def test_a_stale_report_is_not_read_as_this_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """H3 reruns reuse the a<n> folder; a lint step that writes no report leaves no report."""
    monkeypatch.setattr(DockerVerifier, "available", lambda self: True)
    monkeypatch.setattr(DockerVerifier, "probe", lambda self: None)
    monkeypatch.setattr("tsl.harness.verifier.available_memory_mb", lambda: None)
    out = tmp_path / "a1"
    _sarif(out, [_res("api/src/app.ts", 4, "no-unused-vars", "from the last run")])
    steps = iter([0, 1])  # prepare passes; lint crashes before writing its report

    def fake_run(cmd: list[str], **kw: Any) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(cmd, next(steps), b"", b"Oops! Something went wrong!")

    monkeypatch.setattr(subprocess, "run", fake_run)
    profile = {
        "id": "node-22@1",
        "image": "img@sha256:" + "1" * 64,
        "steps": {
            "prepare": {"cmd": "npm ci", "timeout_s": 60},
            "lint": {"cmd": "eslint", "timeout_s": 60, "parse": "sarif", "report": "lint.sarif"},
        },
    }
    (lint,) = DockerVerifier().run(profile, tmp_path, out, with_coverage=False).steps
    assert lint.status == "fail" and lint.report_sha256 is None
    assert not (out / "lint.sarif").exists()
    assert "from the last run" not in _with_log(lint, out, REL, "lint.sarif", ["api/src/app.ts"])


def test_h3_lint_failure_names_the_error_in_the_changed_file(world: World) -> None:
    """End to end: run_h3 hands the step's changed files to the lint detail."""
    _run_id, info = _code_run(world)
    world.verifier.fail_step = "lint"
    prof = world.plugin / "verifiers/node-20@1/profile.yaml"  # the fixture names no report
    text = prof.read_text(encoding="utf-8")
    prof.write_text(text.replace("parse: sarif}", "parse: sarif, report: lint.sarif}", 1))
    run = world.verifier.run

    def run_with_report(
        profile: dict[str, Any], worktree: Path, out_dir: Path, with_coverage: bool
    ) -> Any:
        _sarif(
            out_dir,
            [
                _res("api/src/routes/orders.js", 12, "no-var", "Unexpected var."),
                _res("api/src/app.js", 3, "eqeqeq", "Expected '==='."),
            ],
        )
        return run(profile, worktree, out_dir, with_coverage)

    world.verifier.run = run_with_report  # type: ignore[method-assign]
    code, env, _, err = world.cli(
        ["verify", info["artifact"], "--gates", "H3", "--json"], session=SESSION
    )
    assert code == 2 and env is not None, (env, err)
    h3 = next(g for g in env["data"]["gates"] if g["id"] == "H3")
    assert h3["codes"] == ["E-H3-03"]
    assert "1 error(s) in the files this step changed (1 more in other files)" in h3["detail"]
    assert "api/src/routes/orders.js:12:3 no-var: Unexpected var." in h3["detail"]
    assert "app.js" not in h3["detail"].split("lint.sarif", 1)[1]


@pytest.mark.parametrize(
    ("uri", "base"),
    [
        ("api/src/routes/x.ts", None),  # relative: "/src/" inside it is part of the path
        ("./api/src/routes/x.ts", None),
        ("api/src/routes/x.ts", "file:///cache/w/"),  # relative to a uriBaseId
        ("file:///cache/w/api/src/routes/x.ts", None),
        ("/src/api/src/routes/x.ts", None),  # Semgrep's mount: only the leading /src/ goes
    ],
)
def test_sarif_paths_keep_a_src_folder_inside_the_repo(
    tmp_path: Path, uri: str, base: str | None
) -> None:
    """Review on #72: "/src/" was cut wherever it appeared, so api/src/routes/x.ts became
    routes/x.ts and an error in a changed file showed as outside the change."""
    art: dict[str, Any] = {"uri": uri, **({"uriBaseId": "W"} if base else {})}
    loc = {"physicalLocation": {"artifactLocation": art, "region": {"startLine": 1}}}
    res = {"ruleId": "no-var", "level": "error", "message": {"text": "m"}, "locations": [loc]}
    run: dict[str, Any] = {"tool": {"driver": {"name": "ESLint"}}, "results": [res]}
    if base:
        run["originalUriBaseIds"] = {"W": {"uri": base}}
    (tmp_path / "lint.sarif").write_text(json.dumps({"runs": [run]}), encoding="utf-8")
    lines, mine, total = sarif_errors(tmp_path / "lint.sarif", ["api/src/routes/x.ts"])
    assert (mine, total) == (1, 1)
    assert lines == ["api/src/routes/x.ts:1:? no-var: m"]
