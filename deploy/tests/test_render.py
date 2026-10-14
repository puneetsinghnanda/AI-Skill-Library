"""Hosted TEST environment on Render + Neon (deploy/render/README.md, ADR 0006 addendum).

Static checks always run. hadolint runs through Docker when a daemon is reachable (the same pinned
image as .github/workflows/verifier-images.yml).
"""

from __future__ import annotations

import ast
import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml

DEPLOY = Path(__file__).resolve().parent.parent
ROOT = DEPLOY.parent
RENDER = DEPLOY / "render"
BLUEPRINT = ROOT / "render.yaml"
DOCKERFILE = RENDER / "Dockerfile"
ORG_EXAMPLE = RENDER / "tsl-org.github.toml.example"
HADOLINT = "hadolint/hadolint:v2.12.0"

PROMPTED = {
    "DATABASE_URL",
    "GITHUB_CLIENT_ID",
    "GITHUB_CLIENT_SECRET",
    "GITHUB_WEBHOOK_SECRET",
    "BOOTSTRAP_ADMIN_GITHUB_LOGINS",
    "PUBLIC_BASE_URL",
}
GENERATED = {"DATA_KEY", "PSEUDONYM_PEPPER", "DB_ROLE_PASSWORD_KEY"}
FIXED = {
    "IDENTITY_PROVIDER": "github",
    "ENVIRONMENT": "test",
    "ENV": "test",
    "SERVE_PORTAL_DIR": "/app/portal",
}


def _service() -> dict[str, Any]:
    data = yaml.safe_load(BLUEPRINT.read_text(encoding="utf-8"))
    assert set(data) == {"services"}, "only one web service; the database is Neon"
    (svc,) = data["services"]
    out: dict[str, Any] = svc
    return out


def _env() -> dict[str, dict[str, Any]]:
    return {e["key"]: e for e in _service()["envVars"]}


def test_blueprint_is_one_free_docker_web_service() -> None:
    svc = _service()
    assert svc["type"] == "web" and svc["runtime"] == "docker"
    assert svc["name"] == "truminds-skills-test"
    assert svc["plan"] == "free"
    assert svc["healthCheckPath"] == "/healthz"
    assert svc["region"] == "singapore"
    assert (ROOT / svc["dockerfilePath"]).resolve() == DOCKERFILE
    assert svc["dockerContext"] == "."


def test_blueprint_secrets_are_prompted_or_generated_never_written() -> None:
    env = _env()
    prompted = {k for k, e in env.items() if e.get("sync") is False}
    generated = {k for k, e in env.items() if e.get("generateValue") is True}
    assert prompted == PROMPTED
    assert generated == GENERATED
    for k in PROMPTED | GENERATED:
        assert "value" not in env[k], f"{k} must not have a value in git"
    for k, v in FIXED.items():
        assert env[k]["value"] == v, k


def test_blueprint_values_start_the_service(monkeypatch: pytest.MonkeyPatch) -> None:
    import base64
    import os
    import sys

    sys.path.insert(0, str(ROOT / "services" / "insights"))
    try:
        from app.config import Settings
    finally:
        sys.path.pop(0)

    for k, e in _env().items():
        if "value" in e:
            monkeypatch.setenv(k, str(e["value"]))
    fake = {
        "DATABASE_URL": "postgresql://neondb_owner:x@ep-a-b-1.ap-southeast-1.aws.neon.tech/neondb"
        "?sslmode=require",
        "PUBLIC_BASE_URL": "https://truminds-skills-test.onrender.com",
        "GITHUB_CLIENT_ID": "Ov23liEXAMPLEonly",
        "GITHUB_CLIENT_SECRET": "example-not-a-secret",
        "GITHUB_WEBHOOK_SECRET": "example-not-a-secret-either",
        "BOOTSTRAP_ADMIN_GITHUB_LOGINS": "example-login",
    }
    fake |= {k: base64.b64encode(os.urandom(32)).decode() for k in GENERATED}
    for k, v in fake.items():
        monkeypatch.setenv(k, v)
    s = Settings()
    s.check_identity()
    s.check_hosting()
    assert s.identity_provider == "github" and s.env == "test"
    assert s.portal_dir == Path("/app/portal")
    assert len(s.data_key()) == 32 and len(s.pepper()) >= 32
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("ENVIRONMENT", "prod")
    with pytest.raises(RuntimeError):
        Settings().check_identity()


def test_dockerfile_contract() -> None:
    df = DOCKERFILE.read_text(encoding="utf-8")
    assert "FROM node:22-alpine AS portal" in df
    assert "FROM python:3.12-slim" in df
    assert "VITE_IDENTITY_PROVIDER=github" in df and "VITE_ENVIRONMENT=test" in df
    assert "VITE_API_BASE_URL= " in df, "the portal calls the API on its own origin"
    assert "COPY --from=portal /app/dist /app/portal" in df
    assert "SERVE_PORTAL_DIR=/app/portal" in df and "PORT=10000" in df
    assert "EXPOSE 10000" in df
    assert "USER 10001" in df and "useradd --uid 10001" in df
    assert df.rstrip().endswith('CMD ["allinone"]')
    # the start-up catalogue sync reads these (services/insights/app/catalogue/sync.py)
    for src in ("plugins/truminds", "pods", "tsl/src/tsl/__init__.py"):
        assert f"COPY {src} /srv/catalogue/{src}" in df, src
    assert "/srv/catalogue/.release-tag" in df
    ignore = (RENDER / "Dockerfile.dockerignore").read_text(encoding="utf-8")
    assert "**/node_modules" in ignore and "**/.env" in ignore and "deploy/*.toml" in ignore


def _docker_ok() -> bool:
    docker = shutil.which("docker")
    if not docker:
        return False
    return subprocess.run([docker, "info"], capture_output=True).returncode == 0


@pytest.mark.skipif(not _docker_ok(), reason="hadolint runs in Docker; no Docker daemon")
def test_hadolint() -> None:
    r = subprocess.run(
        ["docker", "run", "--rm", "-i", HADOLINT],
        input=DOCKERFILE.read_bytes(),
        capture_output=True,
        timeout=300,
    )
    assert r.returncode == 0, r.stdout.decode() + r.stderr.decode()


def _hatch_keys() -> tuple[set[str], set[str]]:
    tree = ast.parse((ROOT / "tsl" / "hatch_build.py").read_text(encoding="utf-8"))
    found: dict[str, set[str]] = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in ("ORG_KEYS", "OPTIONAL_KEYS")
        ):
            found[node.targets[0].id] = set(ast.literal_eval(node.value))
    return found["ORG_KEYS"], found["OPTIONAL_KEYS"]


def test_tsl_org_example_passes_the_build_hook_rules() -> None:
    data = tomllib.loads(ORG_EXAMPLE.read_text(encoding="utf-8"))
    required, optional = _hatch_keys()
    assert required <= set(data)
    assert set(data) <= {"configured"} | required | optional
    assert data["configured"] is True and data["provider"] == "github"
    assert data["github_client_id"]
    assert data["service_url"].startswith("https://") and data["service_url"].endswith(
        ".onrender.com"
    )
    text = ORG_EXAMPLE.read_text(encoding="utf-8")
    assert "uv tool install --python 3.12 --reinstall --no-cache" in text
    assert "TSL_ORG_FILE" in text
    assert "render/tsl-org.github.toml" in (DEPLOY / ".gitignore").read_text(encoding="utf-8")


def test_readme_covers_every_step() -> None:
    text = (RENDER / "README.md").read_text(encoding="utf-8")
    for heading in (
        "## A. Neon",
        "## B. GitHub OAuth App",
        "## C. Render",
        "## D. Add the testers",
        "## E. Tester set-up",
        "## F. GitHub webhook",
        "## G. Free-tier behaviour",
        "## H. Security notes",
    ):
        assert heading in text, heading
    for must in (
        "/auth/github/callback",
        "/v1/webhooks/github",
        "Enable Device Flow",
        "GITHUB_WEBHOOK_HOOKS",
        "/truminds:run brownfield-change ABC-142",
        "companion-example",
        "-pooler",
    ):
        assert must in text, must
