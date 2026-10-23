"""Test fakes and a temp 'world': companion repo, product repo, plugin, users.

All data is invented (sample order-tracking system). No network, no real tenant,
no committed key material: keys are generated per test.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from tsl.core.clock import FrozenClock, iso
from tsl.core.errors import TslError
from tsl.core.ids import IdFactory
from tsl.core.paths import Home
from tsl.core.runtime import Runtime, use_runtime
from tsl.github.client import PullRequest
from tsl.harness.verifier import StepResult, VerifierResult, VerifierUnavailable
from tsl.identity.keystore import MemoryKeyStore
from tsl.identity.org import OrgConfig
from tsl.identity.signing import b64url_decode, canonical
from tsl.insights.client import HttpResult, InsightsUnavailable

FIXTURES = Path(__file__).parent / "fixtures"
START = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
SYSTEM = "SYS-ORD"

USERS: dict[str, dict[str, Any]] = {
    "eng": {
        "pseudonym": "eng-4f2a",
        "upn": "eng@example.com",
        "oid": "oid-eng",
        "app_roles": ["Engineer"],
        "grants": [
            {"role": "viewer", "scope": "org"},
            {"role": "engineer", "scope": f"system:{SYSTEM}"},
            {"role": "skill_owner", "scope": "skill:requirement-review"},
        ],
    },
    "eng2": {
        "pseudonym": "eng-77b1",
        "upn": "eng2@example.com",
        "oid": "oid-eng2",
        "app_roles": ["Engineer"],
        "grants": [{"role": "engineer", "scope": f"system:{SYSTEM}"}],
    },
    "tl": {
        "pseudonym": "tl-7a1c",
        "upn": "tl@example.com",
        "oid": "oid-tl",
        "app_roles": ["TechLead"],
        "grants": [
            {"role": "tech_lead", "scope": f"system:{SYSTEM}"},
            {"role": "engineer", "scope": f"system:{SYSTEM}"},
        ],
    },
    "biz": {
        "pseudonym": "biz-1e0a",
        "upn": "biz@example.com",
        "oid": "oid-biz",
        "app_roles": ["Business"],
        "grants": [{"role": "viewer", "scope": "org"}],
    },
}


# ------------------------------------------------------------------------------ fakes
class FakeIdentity:
    def __init__(self, user: str) -> None:
        self.user = user
        self.logged_in = False

    def device_login(self, show: Callable[[str], None]) -> dict[str, Any]:
        show("To sign in, open https://microsoft.com/devicelogin and enter the code TEST-CODE.")
        self.logged_in = True
        return {
            "access_token": f"tok:{self.user}",
            "id_token_claims": {"tid": "tenant", "oid": f"oid-{self.user}"},
        }

    def silent_token(self, force_refresh: bool = False) -> str:
        if not self.logged_in:
            raise TslError("E-AUTH-01")
        return f"tok:{self.user}"

    def logout(self) -> None:
        self.logged_in = False


class FakeInsights:
    def __init__(self, clock: FrozenClock) -> None:
        self.clock = clock
        self.keys: dict[str, dict[str, Any]] = {}
        self.events: list[dict[str, Any]] = []
        self.offline = False
        self.event_responses: list[HttpResult] = []
        self.verify_unreachable = False
        self.systems: dict[str, dict[str, Any]] = {
            SYSTEM: {
                "code": SYSTEM,
                "project": "PRJ-07",
                "client": "CL-03",
                "companion_repo": "example-org/cl-03-sys-ord-companion",
                "lifecycle_state": "ACTIVE",
                "consent": {
                    "recorded": True,
                    "ref": "CONSENT-0001",
                    "scope": ["code_processing", "companion_storage", "product_prs", "ci_webhook"],
                },
            }
        }
        self.report: dict[str, Any] = {
            "skill": "requirement-review",
            "version": "1.0.0",
            "flags": [
                {
                    "id": "flg_01JA1Z0000000000000000000A",
                    "signal": "IS-1",
                    "value": 0.71,
                    "sample": 14,
                }
            ],
            "clusters": [
                {
                    "signature": "RETRY|H5|S1<0.75|major:1|-",
                    "count": 6,
                    "examples": [{"system": SYSTEM, "run_id": "run_01JA1Z0000000000000000000B"}],
                }
            ],
        }

    def _user(self, token: str) -> str | None:
        return token.split(":", 1)[1] if token.startswith("tok:") else None

    def _guard(self) -> None:
        if self.offline:
            raise InsightsUnavailable("offline")

    def health(self) -> bool:
        return not self.offline

    def get_me(self, token: str) -> HttpResult:
        self._guard()
        u = self._user(token)
        if u is None or u not in USERS:
            return HttpResult(401, None)
        return HttpResult(200, json.loads(json.dumps(USERS[u])))

    def register_key(self, token: str, body: dict[str, Any]) -> HttpResult:
        self._guard()
        u = self._user(token)
        if u is None:
            return HttpResult(401, None)
        if not set(USERS[u]["app_roles"]) & {"Engineer", "TechLead", "Admin"}:
            return HttpResult(403, None)
        proof = {k: body[k] for k in ("key_id", "public_key", "device_id", "iat")}
        proof["sub"] = USERS[u]["oid"]
        try:
            Ed25519PublicKey.from_public_bytes(b64url_decode(body["public_key"])).verify(
                b64url_decode(body["proof"]), canonical(proof)
            )
        except Exception:
            return HttpResult(400, None)
        old = self.keys.get(body["key_id"])
        if old and old["public_key"] != body["public_key"]:
            return HttpResult(409, None)
        now = self.clock()
        for k in self.keys.values():
            if k["user"] == u and k["device_id"] == body["device_id"] and k["revoked_at"] is None:
                k["revoked_at"], k["revoked_reason"] = iso(now), "replaced"
        self.keys[body["key_id"]] = {
            "key_id": body["key_id"],
            "public_key": body["public_key"],
            "user": u,
            "device_id": body["device_id"],
            "device_label": body.get("device_label"),
            "created_at": iso(now),
            "expires_at": iso(now + timedelta(days=180)),
            "revoked_at": None,
            "revoked_reason": None,
            "compromised_since": None,
        }
        return HttpResult(
            201,
            {
                "key_id": body["key_id"],
                "pseudonym": USERS[u]["pseudonym"],
                "expires_at": iso(now + timedelta(days=180)),
            },
        )

    def revoke_key(self, token: str, key_id: str, body: dict[str, Any]) -> HttpResult:
        self._guard()
        u = self._user(token)
        k = self.keys.get(key_id)
        if k is None or k["user"] != u:
            return HttpResult(404, None)
        k["revoked_at"], k["revoked_reason"] = iso(self.clock()), body["reason"]
        k["compromised_since"] = body.get("compromised_since")
        return HttpResult(200, {"key_id": key_id, "revoked_at": k["revoked_at"]})

    def my_keys(self, token: str) -> HttpResult:
        self._guard()
        u = self._user(token)
        return HttpResult(200, {"keys": [dict(k) for k in self.keys.values() if k["user"] == u]})

    def facts(self, key_id: str) -> dict[str, Any] | None:
        k = self.keys.get(key_id)
        if k is None:
            return None
        return {
            f: k[f]
            for f in (
                "key_id",
                "public_key",
                "created_at",
                "expires_at",
                "revoked_at",
                "revoked_reason",
                "compromised_since",
            )
        }

    def get_key(self, token: str, key_id: str) -> HttpResult:
        self._guard()
        f = self.facts(key_id)
        return HttpResult(200, f) if f else HttpResult(404, None)

    def verify_signatures(self, token: str, body: dict[str, Any]) -> HttpResult:
        if self.verify_unreachable:
            raise InsightsUnavailable("down")
        items = []
        for it in body["items"]:
            k = self.keys.get(it["key_id"])
            if k is None:
                items.append({"key_id": it["key_id"], "known": False})
                continue
            roles = [
                g["role"]
                for g in USERS[k["user"]]["grants"]
                if g["scope"] == f"system:{body['system']}"
            ]
            items.append(
                {
                    **(self.facts(it["key_id"]) or {}),
                    "known": True,
                    "user_pseudonym": USERS[k["user"]]["pseudonym"],
                    "roles_at": roles,
                    "anchored_at": None,
                }
            )
        return HttpResult(200, {"items": items})

    def get_system(self, token: str, code: str) -> HttpResult:
        self._guard()
        s = self.systems.get(code)
        return HttpResult(200, json.loads(json.dumps(s))) if s else HttpResult(404, None)

    def improvement_report(self, token: str, skill: str) -> HttpResult:
        self._guard()
        return HttpResult(200, self.report)

    def post_events(self, token: str, events: list[dict[str, Any]]) -> HttpResult:
        self._guard()
        if self.event_responses:
            return self.event_responses.pop(0)
        self.events.extend(events)
        return HttpResult(202, {"accepted": len(events), "duplicates": [], "rejected": []})


class FakeGitHub:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.prs: dict[tuple[str, int], PullRequest] = {}
        self.unreachable = False

    def create_pull_request(
        self, repo: str, head: str, base: str, title: str, body: str, draft: bool, labels: list[str]
    ) -> PullRequest:
        n = len(self.created) + 1
        pr = PullRequest(
            n, f"https://github.example/{repo}/pull/{n}", draft, "", body, [], base, head
        )
        self.created.append(
            {
                "repo": repo,
                "head": head,
                "base": base,
                "title": title,
                "body": body,
                "draft": draft,
                "labels": labels,
            }
        )
        self.prs[(repo, n)] = pr
        return pr

    def get_pull_request(self, repo: str, number: int) -> PullRequest:
        from tsl.github.client import GitHubUnavailable

        if self.unreachable:
            raise GitHubUnavailable("down")
        return self.prs[(repo, number)]


class FakeVerifier:
    def __init__(self) -> None:
        self.up = True
        self.fail_step: str | None = None
        self.calls = 0

    def available(self) -> bool:
        return self.up

    def run(
        self, profile: dict[str, Any], worktree: Path, out_dir: Path, with_coverage: bool
    ) -> VerifierResult:
        if not self.up:
            raise VerifierUnavailable("docker not running")
        self.calls += 1
        res = VerifierResult(str(profile["id"]), "sha256:" + "0" * 64)
        for s in ("build", "test", "lint", "sast", "secrets"):
            if s == self.fail_step:
                code = {
                    "build": "E-H3-01",
                    "test": "E-H3-02",
                    "lint": "E-H3-03",
                    "sast": "E-H3-04",
                    "secrets": "E-SEC-01",
                }[s]
                res.steps.append(StepResult(s, "fail", 1, 10, None, code, f"{s} exit 1"))
            else:
                res.steps.append(StepResult(s, "pass", 0, 10, None))
        return res


# ------------------------------------------------------------------------------ git
def git(cwd: Path, *args: str) -> str:
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {p.stderr}")
    return p.stdout.strip()


def write(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def make_repo(base: Path, name: str, files: dict[str, str]) -> tuple[Path, Path]:
    remote = base / "remotes" / f"{name}.git"
    remote.parent.mkdir(parents=True, exist_ok=True)
    git(base, "init", "-q", "--bare", "-b", "main", str(remote))
    work = base / name
    git(base, "clone", "-q", str(remote), str(work))
    git(work, "checkout", "-q", "-b", "main")
    write(work, files)
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", "initial")
    git(work, "push", "-q", "origin", "main")
    return work, remote


PRODUCT_FILES = {
    "api/package.json": json.dumps(
        {
            "name": "orders-api",
            "dependencies": {"express": "^4.19.2", "pg": "^8.11.0"},
            "devDependencies": {"jest": "^29.7.0"},
            "scripts": {"test": "jest"},
        }
    ),
    "api/src/app.js": "const express = require('express');\nconst ordersRouter = require('./routes/orders');\n"
    "const app = express();\napp.use('/api/orders', ordersRouter);\nmodule.exports = app;\n",
    "api/src/routes/orders.js": "const router = require('express').Router();\nconst db = require('../db');\n\n"
    "function listOrders(req, res) {\n  return db.query('SELECT * FROM orders "
    "ORDER BY created_at DESC');\n}\n\nfunction getOrder(req, res) {\n  return "
    "db.query('SELECT * FROM orders WHERE id = $1', [req.params.id]);\n}\n\n"
    "router.get('/', listOrders);\nrouter.get('/:id', getOrder);\n"
    "router.get(`/${'dyn'}`, getOrder);\nmodule.exports = router;\n",
    "api/src/db.js": "module.exports = { query: () => [] };\n",
    "api/src/jobs/purge-events.js": "// Deletes order_events older than 24 hours.\nfunction purge(db) {\n"
    '  return db.query("DELETE FROM order_events WHERE created_at < now() - '
    "interval '24 hours'\");\n}\nmodule.exports = { purge };\n",
    "api/migrations/001_create_orders.sql": "CREATE TABLE orders (\n  id serial PRIMARY KEY,\n  customer_ref "
    "text NOT NULL,\n  status text NOT NULL DEFAULT 'new',\n  created_at "
    "timestamptz NOT NULL DEFAULT now()\n);\n",
    "api/migrations/002_add_order_events.sql": "CREATE TABLE order_events (\n  id serial PRIMARY KEY,\n  "
    "order_id integer NOT NULL REFERENCES orders(id),\n  status text,\n"
    "  created_at timestamptz NOT NULL\n);\nCREATE INDEX "
    "order_events_created_at_idx ON order_events (created_at);\n"
    "INSERT INTO order_events (order_id, status, created_at) VALUES "
    "(1, 'new', now());\n",
    "api/test/orders.test.js": "describe('orders', () => {\n  it('lists orders newest first', () => {});\n});\n",
    "web/package.json": json.dumps(
        {
            "name": "orders-web",
            "dependencies": {"react": "^18.3.1", "react-router-dom": "^6.26.0"},
            "devDependencies": {"vitest": "^2.0.0"},
        }
    ),
    "web/src/App.jsx": "import { Route } from 'react-router-dom';\nexport function App() {\n  fetch('/api/orders');\n"
    '  return <Route path="/orders/:id" />;\n}\n',
}


def section(name: str, body: str, sha: str, status: str = "reviewed") -> str:
    fm = {
        "schema": "context-section.v1",
        "section": name,
        "owner": "tl-7a1c",
        "origin": "human",
        "status": status,
        "verified_at": {"sample-orders": sha} if status == "reviewed" else None,
    }
    return "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\n" + body


def judgement(sha: str) -> dict[str, str]:
    return {
        "context/system-baseline.md": section(
            "system-baseline",
            "# System baseline {#system-baseline}\n\n"
            "## Purpose {#purpose}\nAn invented order-tracking system.\n",
            sha,
        ),
        "context/architecture.md": section(
            "architecture",
            "# Architecture {#architecture}\n\n## API {#api}\n"
            "The api module serves `/api/orders`.\n"
            "Sources: context/generated/api-inventory.json#http:GET:/api/orders\n",
            sha,
        ),
        "context/data-model.md": section(
            "data-model",
            "# Data model {#data-model}\n\n## Orders {#orders}\n"
            "Orders live in `orders`.\n"
            "Sources: context/generated/db-schema.json#table:orders, "
            "sample-orders:api/src/jobs/purge-events.js#L1\n",
            sha,
        ),
        "context/glossary.md": section(
            "glossary",
            "# Glossary {#glossary}\n\n## Order history {#order-history}\n"
            "The list of past orders of one customer.\n",
            sha,
        ),
        "context/conventions.md": section(
            "conventions",
            "# Conventions {#conventions}\n\n## Errors {#errors}\nErrors return JSON.\n",
            sha,
        ),
        "context/test-strategy.md": section(
            "test-strategy",
            "# Test strategy {#test-strategy}\n\n## Unit {#unit}\nJest in api/test.\n",
            sha,
        ),
        "context/intent-baseline.md": section(
            "intent-baseline",
            "# Intent baseline {#intent-baseline}\n\n"
            "## Goals {#goals}\nCustomers can see their orders.\n\n"
            "## Data retention {#data-retention}\nOrder events are kept 24 hours.\n",
            sha,
        ),
    }


# ------------------------------------------------------------------------------ world
@dataclass
class World:
    base: Path
    clock: FrozenClock
    insights: FakeInsights
    github: FakeGitHub
    verifier: FakeVerifier
    plugin: Path
    companion: Path
    companion_remote: Path
    product: Path
    product_remote: Path
    runtimes: dict[str, Runtime] = field(default_factory=dict)
    identities: dict[str, FakeIdentity] = field(default_factory=dict)

    def rt(self, user: str = "eng", session: str | None = None) -> Runtime:
        if user not in self.runtimes:
            ident = FakeIdentity(user)
            self.identities[user] = ident
            org = OrgConfig(
                configured=True,
                tenant_id="tenant",
                tsl_client_id="client",
                api_scope="api://truminds-insights/Events.Write",
                service_url="https://insights.example.invalid",
                companion_remote_template=str(self.base / "remotes" / "{repo}.git"),
                github_api_url="https://api.github.example",
                link_hosts=("github.example",),
            )
            self.runtimes[user] = Runtime(
                home=Home(self.base / "homes" / user / ".truminds"),
                clock=self.clock,
                ids=IdFactory(self.clock, seed=hash(user) % 1000),
                org=org,
                keystore=MemoryKeyStore(),
                insights=self.insights,
                github=self.github,
                verifier=self.verifier,
                env={"CLAUDE_PLUGIN_ROOT": str(self.plugin)},
                identity_provider=ident,
                strict_events=True,
            )
        rt = self.runtimes[user]
        env = dict(rt.env)
        if session:
            env["TSL_SESSION_ID"] = session
        else:
            env.pop("TSL_SESSION_ID", None)
        rt.env = env
        return rt

    def cli(
        self,
        args: list[str],
        user: str = "eng",
        session: str | None = None,
        stdin: str = "",
        repo: Path | None = None,
    ) -> tuple[int, dict[str, Any] | None, str, str]:
        from tsl.cli.app import run_cli

        rt = self.rt(user, session)
        full = ["--repo", str(repo or self.companion), *args]
        out, err = io.StringIO(), io.StringIO()
        old_stdin = sys.stdin
        sys.stdin = io.StringIO(stdin)
        try:
            with use_runtime(rt), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = run_cli(full)
        finally:
            sys.stdin = old_stdin
        text = out.getvalue()
        env = None
        if "--json" in args:
            lines = [x for x in text.splitlines() if x.strip()]
            env = json.loads(lines[-1]) if lines else None
        return code, env, text, err.getvalue()

    def login(self, user: str) -> dict[str, Any]:
        from tsl.services.identity_cmds import login

        rt = self.rt(user)
        with use_runtime(rt):
            return login(rt, rotate_key=False, interactive=True)

    def sync_companion(self) -> None:
        git(self.companion, "pull", "-q", "--rebase", "origin", "main")

    @contextlib.contextmanager
    def using(self, user: str = "eng", session: str | None = None) -> Iterator[Runtime]:
        rt = self.rt(user, session)
        with use_runtime(rt):
            yield rt


def make_world(base: Path, signed_pack: bool = True) -> World:
    clock = FrozenClock(START)
    plugin = base / "plugin"
    shutil.copytree(FIXTURES / "plugin", plugin)
    product, product_remote = make_repo(base, "sample-orders", PRODUCT_FILES)
    (product / ".env").write_text(
        "DB_PASSWORD=" + "x" * 3 + "\n", encoding="utf-8"
    )  # excluded, never read
    psha = git(product, "rev-parse", "HEAD")
    cfg = {
        "schema": "tsl-config.v1",
        "system": {"code": SYSTEM, "project": "PRJ-07", "client": "CL-03"},
        "companion": {"repo": "example-org/cl-03-sys-ord-companion", "default_branch": "main"},
        "product_repos": [
            {
                "name": "sample-orders",
                "url": "git@github.example:example-org/sample-orders.git",
                "path": ".",
                "default_branch": "main",
                "verifier_profile": "node-20@1",
            }
        ],
        "context": {"drift_files": 50, "critical_paths": ["sample-orders:api/src/auth/**"]},
        "gates": {"self_approval": False, "lock_timeout_hours": 24},
        "pr": {"branch_prefix": "tsl/", "labels": ["truminds"]},
        "telemetry": {"enabled": True},
    }
    files = {
        "tsl.yaml": yaml.safe_dump(cfg, sort_keys=False),
        "policy.yaml": yaml.safe_dump(
            {"schema": "policy.v2", "write_scope": {"deny": ["**/secrets/**"]}}
        ),
        ".gitignore": ".tsl/\n**/.local.lock\n",
        ".gitattributes": "* text=auto eol=lf\n",
        "runs/active/.gitkeep": "",
        "artifacts/.gitkeep": "",
        **judgement(psha),
    }
    companion, companion_remote = make_repo(base, "companion", files)
    write(
        companion,
        {
            ".tsl/local.yaml": yaml.safe_dump(
                {"schema": "tsl-local.v1", "product_repos": {"sample-orders": str(product)}}
            )
        },
    )
    w = World(
        base,
        clock,
        FakeInsights(clock),
        FakeGitHub(),
        FakeVerifier(),
        plugin,
        companion,
        companion_remote,
        product,
        product_remote,
    )
    for u in ("eng", "tl"):
        w.login(u)
    if signed_pack:
        sign_pack(w)
    return w


def sign_pack(w: World) -> None:
    from tsl.context.build import build, sign
    from tsl.core.repo import Companion

    with w.using("tl") as rt:
        comp = Companion(w.companion)
        build(rt, comp, check=False, commits=None)
        sign(rt, comp)
    git(w.companion, "push", "-q", "origin", "main")


def ticket_snapshot(run_id: str, ticket: str = "ABC-142") -> str:
    fm = {
        "schema": "ticket-snapshot.v1",
        "run_id": run_id,
        "ticket": ticket,
        "source": "file",
        "fetched_at": "2026-01-01T00:00:00Z",
    }
    return (
        "---\n"
        + yaml.safe_dump(fm, sort_keys=False)
        + "---\n"
        + f"# {ticket}\nShow order history on the order page.\nNewest first.\n20 orders per page.\n"
    )


def intent_artifact(
    env: dict[str, Any],
    ticket_rel: str,
    *,
    known_value: str = "newest first",
    blocking_question: bool = False,
    drop_section: str | None = None,
) -> str:
    fm: dict[str, Any] = dict(env)
    fm["claims"] = [
        {
            "id": "C1",
            "text": "Order events are kept `24 hours`",
            "cites": ["context/intent-baseline.md#data-retention"],
        }
    ]
    fm["trace"] = ["REQ-1", "REQ-2"]
    fm["known"] = ["REQ-1"]
    fm["assumed"] = ["REQ-2"]
    fm["unknown"] = []
    fm["requirements"] = [
        {
            "id": "REQ-1",
            "title": "Show order history",
            "type": "functional",
            "status": "known",
            "statement": f"The order page shows past orders, {known_value}.",
            "cites": [f"{ticket_rel}#L10"],
        },
        {
            "id": "REQ-2",
            "title": "Page size",
            "type": "functional",
            "status": "assumed",
            "statement": "The list shows 20 orders per page.",
            "basis": "The ticket asks for it",
            "cites": [f"{ticket_rel}#L11"],
        },
    ]
    fm["unknowns"] = []
    fm["questions"] = []
    fm["glossary"] = [{"term": "Order history", "found": True}]
    if blocking_question:
        fm["unknown"] = ["U-1"]
        fm["unknowns"] = [{"id": "U-1", "text": "Retention differs", "question": "Q-01"}]
        fm["questions"] = [
            {
                "id": "Q-01",
                "blocking": True,
                "ask": "product owner",
                "text": "Ticket wants history; the baseline keeps 24 hours. Which applies?",
                "why": "Decides retention",
                "evidence": ["context/intent-baseline.md#data-retention"],
                "options": ["Extend retention", "Keep 24 hours"],
                "default": None,
            }
        ]
    sections = {
        "Summary": "The ticket asks for order history on the order page.",
        "Requirements": "REQ-1 history list; REQ-2 page size.",
        "Known": "REQ-1 from the ticket.",
        "Assumed": "REQ-2 page size.",
        "Unknown": "U-1 retention." if blocking_question else "None.",
        "Open questions": "Q-01 (U-1)." if blocking_question else "None.",
        "Out of scope": "Nothing.",
    }
    body = "# Requirements review\n\n" + "\n".join(
        f"## {k}\n{v}\n" for k, v in sections.items() if k != drop_section
    )
    return "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\n" + body


def review_json(
    pkg: dict[str, Any],
    *,
    findings: list[dict[str, Any]] | None = None,
    questions: list[dict[str, Any]] | None = None,
    score: int = 5,
    rubric_ids: list[str] | None = None,
    version: str = "0.1.3",
) -> str:
    ids = rubric_ids or ["RR-R1", "RR-R2", "RR-R3", "RR-R4", "RR-R5", "RR-R6"]
    obj = {
        "schema": "review.v1",
        "run_id": pkg["run_id"],
        "step": pkg["step"],
        "attempt": pkg["attempt"],
        "artifact_sha256": pkg["artifact_sha256"],
        "package_sha256": pkg["package_sha256"],
        "status": "ok",
        "reviewer": {
            "agent": "truminds:reviewer",
            "skill": "review",
            "version": version,
            "rubric_sha256": pkg["rubric"]["sha256"],
        },
        "rubric_score": float(score),
        "rubric_items": [{"id": i, "score": score, "reason": "ok"} for i in ids],
        "findings": findings or [],
        "claims_checked": [{"claim_id": "C1", "verdict": "supported"}],
        "questions": questions or [],
    }
    return "Here is my review:\n```json\n" + json.dumps(obj) + "\n```\n"
