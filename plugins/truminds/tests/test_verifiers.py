"""Verifier container profiles and images (SDD-03 §4.5, §5.5; SEC-01 §5.5, §7.1, §8.4; OPS-03 §2.1).

No network and no Docker needed. Dockerfiles are linted with hadolint when it is on PATH (or HADOLINT
points at it); otherwise a basic built-in lint runs. Real image builds run only when a Docker daemon is
up and VERIFIER_BUILD=1 is set, because they download base images and tools.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from conftest import DOCS, PLUGIN, ROOT, SKILLS, errors

VERIFIERS = PLUGIN / "verifiers"
WORKFLOW = ROOT / ".github" / "workflows" / "verifier-images.yml"
PROFILE_ID = re.compile(r"\b([a-z][a-z0-9-]*@[0-9]+)\b")
PLACEHOLDER = "sha256:" + "0" * 64
NO_NETWORK_STEPS = ("build", "test", "lint", "sast", "secrets", "coverage")


def profile_dirs() -> list[Path]:
    return sorted(p for p in VERIFIERS.iterdir() if p.is_dir())


def profiles() -> dict[str, dict[str, Any]]:
    return {d.name: yaml.safe_load((d / "profile.yaml").read_text(encoding="utf-8")) for d in profile_dirs()}


def referenced_profiles() -> dict[str, set[str]]:
    """Profile ids named by SDD-03, SDD-06 (sample system), the plugin, and example tsl.yaml files."""
    refs: dict[str, set[str]] = {}

    def add(pid: str, where: Path) -> None:
        refs.setdefault(pid, set()).add(where.relative_to(ROOT).as_posix())

    for doc in (DOCS / "design" / "SDD-03-harness.md", DOCS / "design" / "SDD-06-context-pack.md"):
        for line in doc.read_text(encoding="utf-8").splitlines():
            if "verifier_profile" in line or re.match(r"^id: ", line) or "`node-" in line:
                for pid in PROFILE_ID.findall(line):
                    add(pid, doc)
    tsl_yamls = [*(ROOT / "examples").rglob("tsl.yaml"), *PLUGIN.rglob("tsl.yaml")]
    plugin_files = [
        p for p in PLUGIN.rglob("*") if p.suffix in (".yaml", ".yml", ".md", ".json") and "tests" not in p.parts
    ]
    for p in [*tsl_yamls, *plugin_files]:
        if "node_modules" in p.parts or VERIFIERS in p.parents:
            continue
        for m in re.finditer(r"verifier_profile\"?\s*:\s*\"?([a-z][a-z0-9-]*@[0-9]+)", p.read_text(encoding="utf-8")):
            add(m.group(1), p)
    return refs


def test_profiles_exist() -> None:
    names = {d.name for d in profile_dirs()}
    assert {"node-20@1", "node-22@1", "python-312@1"} <= names


@pytest.mark.parametrize("d", profile_dirs(), ids=lambda d: d.name)
def test_profile_manifest_validates(d: Path) -> None:
    assert (d / "Dockerfile").is_file() and (d / "profile.yaml").is_file()
    prof = yaml.safe_load((d / "profile.yaml").read_text(encoding="utf-8"))
    assert errors("verifier-profile.v1", prof) == []
    assert prof["id"] == d.name  # tsl resolves verifiers/<id>/profile.yaml (tsl/src/tsl/harness/verify.py)


@pytest.mark.parametrize("d", profile_dirs(), ids=lambda d: d.name)
def test_image_pinned_by_digest_with_workflow_name(d: Path) -> None:
    prof = yaml.safe_load((d / "profile.yaml").read_text(encoding="utf-8"))
    name, major = d.name.split("@")
    repo, digest = prof["image"].split("@", 1)
    # verifier-images.yml tags <REGISTRY>/truminds/verifier-<name>:<major>-<sha>
    assert repo.endswith(f"/truminds/verifier-{name}"), prof["image"]
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
    if digest == PLACEHOLDER:
        text = (d / "profile.yaml").read_text(encoding="utf-8")
        assert "PLACEHOLDER" in text and "verifier-images.yml" in text and "OQ-10" in text
    assert major.isdigit()


@pytest.mark.parametrize("d", profile_dirs(), ids=lambda d: d.name)
def test_only_prepare_uses_network(d: Path) -> None:
    prof = yaml.safe_load((d / "profile.yaml").read_text(encoding="utf-8"))
    for step in NO_NETWORK_STEPS:
        if step in prof["steps"]:
            assert prof["steps"][step].get("network", "none") == "none", step
    # prepare writes only to the cache volume; the source stays read-only
    assert "/cache" in prof["steps"]["prepare"]["cmd"]
    for step, spec in prof["steps"].items():
        if step != "prepare":
            assert "cd /src" not in spec["cmd"], step  # /src is read-only; work happens in /cache/w
        if spec.get("report"):
            assert f"/out/{spec['report']}" in spec["cmd"], step


def test_every_referenced_profile_exists() -> None:
    refs = referenced_profiles()
    assert "node-22@1" in refs  # the sample system (examples/sample-system/companion-example/tsl.yaml)
    missing = {pid: sorted(where) for pid, where in refs.items() if not (VERIFIERS / pid / "profile.yaml").is_file()}
    assert missing == {}


def test_every_container_step_a_skill_uses_is_in_every_profile() -> None:
    steps: dict[str, set[str]] = {}
    for f in SKILLS.glob("*/checks.yaml"):
        for c in yaml.safe_load(f.read_text(encoding="utf-8")).get("checks", []) or []:
            if c.get("kind") == "container":
                steps.setdefault(c["profile_step"], set()).add(f.parent.name)
    assert {"build", "test", "lint", "sast", "secrets", "coverage"} <= set(steps)
    for pid, prof in profiles().items():
        missing = sorted(set(steps) - set(prof["steps"]))
        assert missing == [], f"{pid} lacks steps {missing} used by {[sorted(steps[m]) for m in missing]}"


# ------------------------------------------------------------------------------------- Dockerfiles
def _instructions(text: str) -> list[tuple[str, str]]:
    """(INSTRUCTION, args) with line continuations joined and comments dropped."""
    out: list[tuple[str, str]] = []
    buf = ""
    for raw in text.splitlines():
        line = raw.rstrip()
        if not buf and (not line.strip() or line.lstrip().startswith("#")):
            continue
        buf += line[:-1] + " " if line.endswith("\\") else line
        if not line.endswith("\\"):
            word, _, rest = buf.strip().partition(" ")
            out.append((word.upper(), rest.strip()))
            buf = ""
    assert buf == "", "dangling line continuation"
    return out


KNOWN = {"FROM", "RUN", "CMD", "LABEL", "EXPOSE", "ENV", "ADD", "COPY", "ENTRYPOINT", "VOLUME", "USER",
         "WORKDIR", "ARG", "ONBUILD", "STOPSIGNAL", "HEALTHCHECK", "SHELL"}


def basic_lint(text: str) -> list[str]:
    problems: list[str] = []
    ins = _instructions(text)
    if not ins or ins[0][0] not in ("FROM", "ARG"):
        problems.append("first instruction must be FROM or ARG")
    stages: list[str] = []
    for word, args in ins:
        if word not in KNOWN:
            problems.append(f"unknown instruction {word}")
        if word == "FROM":
            image = args.split()[0]
            stages.append(args.split()[-1] if " AS " in args.upper() else image)
            if image not in stages[:-1]:
                tag = image.split("@")[0].rsplit(":", 1)
                if len(tag) != 2 or tag[1] == "latest" or not re.search(r"\d+\.\d+", tag[1]):
                    problems.append(f"base image {image} not pinned to an exact version")
        if word == "ADD" and "http" in args:
            problems.append("ADD with a URL; download and verify in RUN instead")
        if word == "RUN" and re.search(r"(curl|wget)[^|]*\|\s*(sh|bash)", args):
            problems.append("pipe to shell")
        if word == "RUN" and "apt-get install" in args and "--no-install-recommends" not in args:
            problems.append("apt-get install without --no-install-recommends")
        if word == "RUN" and "apt-get install" in args and "rm -rf /var/lib/apt/lists" not in args:
            problems.append("apt lists not removed")
        if word == "RUN" and re.search(r"pip install(?![^&]*==)", args):
            problems.append("pip install without pinned versions")
        if word == "RUN" and re.search(r"npm install -g (?!.*@\d)", args):
            problems.append("npm global install without a pinned version")
    final = ins[max(i for i, (w, _) in enumerate(ins) if w == "FROM") :]
    users = [a for w, a in final if w == "USER"]
    if not users or users[-1].split(":")[0] in ("root", "0"):
        problems.append("final stage must end with a non-root USER")
    return problems


@pytest.mark.parametrize("d", profile_dirs(), ids=lambda d: d.name)
def test_dockerfile_basic_lint(d: Path) -> None:
    text = (d / "Dockerfile").read_text(encoding="utf-8")
    assert basic_lint(text) == []
    # runs as the uid tsl passes (--user 1000:1000, SDD-03 §5.5)
    assert re.search(r"^USER 1000:1000$", text, re.M)
    # the scanners the profile calls are in the image (SEC-01 §7.1), pinned
    prof = yaml.safe_load((d / "profile.yaml").read_text(encoding="utf-8"))
    assert "gitleaks" in prof["steps"]["secrets"]["cmd"] and re.search(r"GITLEAKS_VERSION=\d+\.\d+\.\d+", text)
    assert re.search(r"GITLEAKS_SHA256=[0-9a-f]{64}", text)
    assert "semgrep" in prof["steps"]["sast"]["cmd"] and re.search(r"SEMGREP_VERSION=\d+\.\d+\.\d+", text)


def test_basic_lint_catches_problems() -> None:
    bad = (
        "FROM node:latest\nRUN apt-get install -y curl\n"
        "RUN curl -s https://x.invalid/i.sh | sh\nADD https://x.invalid/a /a\n"
    )
    found = basic_lint(bad)
    assert any("not pinned" in p for p in found)
    assert any("--no-install-recommends" in p for p in found)
    assert any("pipe to shell" in p for p in found)
    assert any("ADD with a URL" in p for p in found)
    assert any("non-root USER" in p for p in found)


def _hadolint() -> str | None:
    cand = os.environ.get("HADOLINT") or shutil.which("hadolint")
    return cand if cand and Path(cand).exists() else None


@pytest.mark.skipif(_hadolint() is None, reason="hadolint not installed; basic lint covers the Dockerfiles")
@pytest.mark.parametrize("d", profile_dirs(), ids=lambda d: d.name)
def test_dockerfile_hadolint(d: Path) -> None:
    r = subprocess.run([str(_hadolint()), str(d / "Dockerfile")], capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stdout + r.stderr


def test_workflow_builds_every_profile_folder() -> None:
    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "plugins/truminds/verifiers/**" in text
    assert "-mindepth 2 -maxdepth 2 -name Dockerfile" in text  # discovers verifiers/<id>/Dockerfile
    build = wf["jobs"]["build"]
    assert build["strategy"]["matrix"]["profile"] == "${{ fromJSON(needs.discover.outputs.profiles) }}"
    runs = " ".join(str(s.get("run", "")) for s in build["steps"])
    assert "hadolint" in runs
    assert "verifier-${PROFILE%@*}" in runs


def _docker_up() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=5, check=False).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


@pytest.mark.skipif(
    not (_docker_up() and os.environ.get("VERIFIER_BUILD") == "1"),
    reason="needs a Docker daemon and VERIFIER_BUILD=1 (downloads base images and tools)",
)
@pytest.mark.parametrize("d", profile_dirs(), ids=lambda d: d.name)
def test_docker_build(d: Path) -> None:
    tag = f"tsl-verifier-test-{d.name.replace('@', '-')}"
    r = subprocess.run(["docker", "build", "-q", "-t", tag, str(d)], capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stderr[-2000:]
