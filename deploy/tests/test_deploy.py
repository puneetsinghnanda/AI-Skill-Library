"""Checks for deploy/ (OPS-01). Run with the insights venv: ``pytest deploy/tests``.

Static checks always run. ``docker compose config`` runs when the Docker CLI is present (no daemon
needed). The edge test starts a real nginx (``NGINX_BIN`` or ``nginx`` on PATH) against a stub
upstream and checks the routing and the E1 path allowlist; it is skipped when nginx is absent.
"""

from __future__ import annotations

import http.server
import os
import re
import shutil
import socket
import ssl
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

DEPLOY = Path(__file__).resolve().parent.parent
ROOT = DEPLOY.parent
COMPOSE = DEPLOY / "compose" / "compose.prod.yml"
NGINX_CONF = DEPLOY / "compose" / "edge" / "nginx.conf"
FETCH = DEPLOY / "scripts" / "fetch-secrets.sh"
CI_TOKEN = "tsi_ci_" + "A" * 43
KEY_PATH = "/v1/keys/key_01J9ZZZZZZZZZZZZZZZZZZZZZZ"


def _compose() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    return data


# ----------------------------------------------------------------------------- static checks
def test_only_edge_publishes_ports_and_networks_are_internal() -> None:
    c = _compose()
    published = {name for name, svc in c["services"].items() if svc.get("ports")}
    assert published == {"edge"}
    assert c["networks"]["app"] == {"internal": True}
    assert c["networks"]["db"] == {"internal": True}
    assert "db" in c["services"]["postgres"]["networks"]
    assert "edge" not in c["services"]["postgres"]["networks"]


def test_images_pinned_by_digest() -> None:
    images = [svc["image"] for svc in _compose()["services"].values() if "image" in svc]
    assert images and all("@${" in i and "DIGEST" in i for i in images), images


def test_hardened_insights_services() -> None:
    c = _compose()
    for name in ("api", "worker", "migrate", "admin"):
        svc = c["services"][name]
        assert svc["read_only"] is True and svc["user"] == "10001", name
        assert "no-new-privileges:true" in svc["security_opt"], name
        assert svc["command"][0] in {"api", "worker", "migrate", "admin"}, name
    assert c["services"]["api"]["deploy"]["replicas"] == 2
    assert c["services"]["api"]["healthcheck"]["test"][-2:] == ["probe", "ready"]
    assert c["services"]["api"]["depends_on"]["migrate"]["condition"] == (
        "service_completed_successfully"
    )


def test_every_compose_secret_is_fetched_from_tmpfs() -> None:
    c = _compose()
    fetch = FETCH.read_text(encoding="utf-8")
    block = fetch[fetch.index("SECRETS=(") : fetch.index(")", fetch.index("SECRETS=("))]
    names = set(block.replace("SECRETS=(", "").split())
    for name, spec in c["secrets"].items():
        assert spec["file"].startswith("/run/truminds-secrets/"), name
        if name != "db_ca":
            assert name in names, f"{name} not fetched by fetch-secrets.sh"
    used = {s for svc in c["services"].values() for s in svc.get("secrets", [])}
    assert used <= set(c["secrets"]), used - set(c["secrets"])


def test_no_secret_material_in_deploy_tree() -> None:
    bad = re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----|ghp_[A-Za-z0-9]{20,}|tsi_(ci|otel)_[A-Za-z0-9_-]{20,}"
        r"|(?i:password)(?:=|:[ \t])[ \t]*['\"]?[^\s'\"$:{}]{6,}"
    )
    for f in DEPLOY.rglob("*"):
        if not f.is_file() or "tests" in f.parts or f.suffix in {".pyc"}:
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        assert not bad.search(text), f"possible secret in {f.relative_to(ROOT)}"
    for example in DEPLOY.rglob("*.example"):
        assert "example" in example.read_text(encoding="utf-8").lower() or "0000" in (
            example.read_text(encoding="utf-8")
        )


def test_shell_scripts_parse() -> None:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash not available")
    scripts = [
        FETCH,
        DEPLOY / "images" / "pg-backup" / "pgbr",
        DEPLOY / "images" / "pg-backup" / "pg-backup-entry",
        DEPLOY / "compose" / "postgres-init" / "10-insights-roles.sh",
    ]
    for s in scripts:
        subprocess.run([bash, "-n", str(s)], check=True)
        assert os.access(s, os.X_OK), f"{s.name} is not executable"


def test_compose_config_validates(tmp_path: Path) -> None:
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("docker CLI not available")
    probe = subprocess.run([docker, "compose", "version"], capture_output=True)
    if probe.returncode != 0:
        pytest.skip("docker compose plugin not available")
    env = DEPLOY / "compose" / "env"
    text = COMPOSE.read_text(encoding="utf-8")
    text = text.replace("/etc/truminds/prod.env", str(env / "prod.env.example"))
    text = text.replace("/etc/truminds/backup.env", str(env / "backup.env.example"))
    check = DEPLOY / "compose" / f".compose.check.{os.getpid()}.yml"
    check.write_text(text, encoding="utf-8")
    try:
        r = subprocess.run(
            [
                docker,
                "compose",
                "-f",
                str(check),
                "--env-file",
                str(DEPLOY / "compose" / ".env.example"),
                "--profile",
                "admin",
                "config",
                "-q",
            ],
            capture_output=True,
            text=True,
        )
    finally:
        check.unlink()
    assert r.returncode == 0, r.stderr


# ----------------------------------------------------------------------------- live edge test
def _port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class _Upstream(http.server.BaseHTTPRequestHandler):
    def _ok(self) -> None:
        body = f"upstream {self.command} {self.path}".encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = _ok
    do_POST = _ok

    def log_message(self, *args: Any) -> None:
        return


@pytest.fixture(scope="module")
def edge(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, int]]:
    nginx = os.environ.get("NGINX_BIN") or shutil.which("nginx")
    openssl = shutil.which("openssl")
    if not nginx or not openssl:
        pytest.skip("nginx or openssl not available")
    work = tmp_path_factory.mktemp("edge")
    (work / "tls").mkdir()
    for name in ("intranet", "public"):
        subprocess.run(
            [
                openssl,
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-days",
                "1",
                "-subj",
                "/CN=edge-test",
                "-keyout",
                str(work / "tls" / f"{name}.key"),
                "-out",
                str(work / "tls" / f"{name}.crt"),
            ],
            check=True,
            capture_output=True,
        )
    up = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Upstream)
    threading.Thread(target=up.serve_forever, daemon=True).start()
    upstream = f"127.0.0.1:{up.server_address[1]}"
    ports = {"http": _port(), "intranet": _port(), "public": _port()}
    conf = NGINX_CONF.read_text(encoding="utf-8")
    mime = work / "mime.types"
    mime.write_text("types { text/html html; application/json json; }\n", encoding="utf-8")
    conf = (
        conf.replace("/tmp/", f"{work}/")
        .replace("/etc/nginx/tls", str(work / "tls"))
        .replace("/etc/nginx/mime.types", str(mime))
        .replace("api:8000", upstream)
        .replace("portal:8080", upstream)
        .replace("resolver 127.0.0.11 valid=10s ipv6=off;", "")
        .replace("listen 8080 ", f"listen 127.0.0.1:{ports['http']} ")
        .replace("listen 8443 ", f"listen 127.0.0.1:{ports['intranet']} ")
        .replace("listen 9443 ", f"listen 127.0.0.1:{ports['public']} ")
    )
    if os.geteuid() == 0:
        conf = "user root;\n" + conf
    cfg = work / "nginx.conf"
    cfg.write_text(conf, encoding="utf-8")
    test = subprocess.run(
        [nginx, "-t", "-c", str(cfg), "-p", str(work), "-e", "stderr"],
        capture_output=True,
        text=True,
    )
    assert test.returncode == 0, test.stderr
    proc = subprocess.Popen(
        [nginx, "-c", str(cfg), "-p", str(work), "-e", "stderr", "-g", "daemon off;"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            socket.create_connection(("127.0.0.1", ports["public"]), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    yield ports
    proc.terminate()
    proc.wait(timeout=10)
    up.shutdown()


def _req(
    port: int, path: str, method: str = "GET", headers: dict[str, str] | None = None
) -> tuple[int, str]:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    data = b"{}" if method == "POST" else None
    req = urllib.request.Request(
        f"https://127.0.0.1:{port}{path}", data=data, method=method, headers=headers or {}
    )
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=5) as r:  # noqa: S310 - test URL
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, ""


def test_intranet_routes(edge: dict[str, int]) -> None:
    p = edge["intranet"]
    assert _req(p, "/v1/me") == (200, "upstream GET /v1/me")
    assert _req(p, "/otel/v1/metrics", "POST")[0] == 200
    assert _req(p, "/")[1] == "upstream GET /"
    assert _req(p, "/metrics")[0] == 404
    assert _req(p, "/v1/health/ready")[0] == 404
    assert _req(p, "/v1/health")[0] == 200


def test_public_allowlist(edge: dict[str, int]) -> None:
    p = edge["public"]
    ci = {"Authorization": f"Bearer {CI_TOKEN}"}
    entra = {"Authorization": "Bearer eyJhbGciOiJSUzI1NiJ9.e30.sig"}
    # GitHub webhook: POST only, HMAC is checked by the service
    assert _req(p, "/v1/webhooks/github", "POST")[0] == 200
    assert _req(p, "/v1/webhooks/github", "GET")[0] == 403
    # CI paths need the CI ingest token; an Entra token is intranet-only
    assert _req(p, "/v1/events", "POST", ci)[0] == 200
    assert _req(p, "/v1/events", "POST", entra)[0] == 404
    assert _req(p, "/v1/events", "POST")[0] == 404
    assert _req(p, KEY_PATH, "GET", ci)[0] == 200
    assert _req(p, KEY_PATH, "GET", entra)[0] == 404
    assert _req(p, "/v1/signatures/verify", "POST", ci)[0] == 200
    # everything else is 404 at the edge
    for path in ("/", "/v1/me", "/v1/keys", "/v1/runs", "/otel/v1/logs", "/metrics", "/v1/health"):
        assert _req(p, path, "GET", ci)[0] == 404, path
    assert _req(p, "/v1/keys", "POST", ci)[0] == 404
