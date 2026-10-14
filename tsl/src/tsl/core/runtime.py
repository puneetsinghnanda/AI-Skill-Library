"""Runtime: everything a service needs from the outside world, injected (SDD-04 §2.3, §12).

The CLI builds the default runtime. Tests build one with a frozen clock, a
seeded id factory, an in-memory key store and fake network clients, and install
it with `use_runtime`. There is no flag or environment variable that does this.
"""

from __future__ import annotations

import contextlib
import os
import sys
import tomllib
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tsl import __version__
from tsl.core.clock import Clock, system_clock
from tsl.core.errors import TslError
from tsl.core.ids import IdFactory
from tsl.core.paths import Home
from tsl.github.client import GitHubClient
from tsl.harness.verifier import VerifierRunner
from tsl.identity.entra import IdentityProvider
from tsl.identity.keystore import KeyStore
from tsl.identity.org import OrgConfig
from tsl.insights.client import InsightsClient


@dataclass
class Runtime:
    home: Home
    clock: Clock
    ids: IdFactory
    org: OrgConfig
    keystore: KeyStore
    insights: InsightsClient
    github: GitHubClient
    verifier: VerifierRunner
    env: Mapping[str, str]
    identity_provider: IdentityProvider | None = None
    tsl_version: str = __version__
    strict_events: bool = False
    stderr_lines: list[str] = field(default_factory=list)
    # Lines shown at once by prompt(): instructions the user must act on while the command waits.
    prompt_lines: list[str] = field(default_factory=list)

    # ---- user config (SDD-04 §7.1)
    def user_config(self) -> dict[str, Any]:
        p = self.home.config
        if not p.exists():
            return {"schema": "user-config.v1"}
        from tsl.schemas.registry import require_valid

        data = tomllib.loads(p.read_text(encoding="utf-8"))
        require_valid("user-config.v1", data, str(p))
        return data

    def write_user_config(self, data: dict[str, Any]) -> None:
        from tsl.core.jsonio import atomic_write
        from tsl.schemas.registry import require_valid

        require_valid("user-config.v1", data, str(self.home.config))
        lines = [f'schema = "{data["schema"]}"']
        for section in ("device", "service", "telemetry", "logging", "ui"):
            values = data.get(section)
            if not values:
                continue
            lines.append(f"\n[{section}]")
            for k, v in values.items():
                lines.append(f"{k} = {v}" if isinstance(v, int) else f'{k} = "{v}"')
        self.home.ensure()
        atomic_write(self.home.config, "\n".join(lines) + "\n")

    def device_id(self) -> str | None:
        dev = self.user_config().get("device", {}).get("device_id")
        return str(dev) if dev else None

    def ensure_device(self) -> str:
        cfg = self.user_config()
        dev = cfg.get("device", {}).get("device_id")
        if dev:
            return str(dev)
        import hashlib
        import socket

        cfg.setdefault("device", {})
        cfg["device"]["device_id"] = self.ids.new("dev")
        host = hashlib.sha256(socket.gethostname().encode()).hexdigest()[:4]
        cfg["device"]["label"] = f"laptop-{host}"
        self.write_user_config(cfg)
        return str(cfg["device"]["device_id"])

    def service_timeout(self) -> float:
        return float(self.user_config().get("service", {}).get("timeout_s", 5))

    # ---- identity
    def identity(self) -> IdentityProvider:
        """The provider baked into _org.toml (SDD-07 §1.4): entra or github."""
        if self.identity_provider is None:
            dev = self.ensure_device()
            if self.org.provider == "github":
                from tsl.identity.github import GitHubIdentity, github_cache

                self.identity_provider = GitHubIdentity(
                    self.org, github_cache(self.home.github_token, self.keystore, dev)
                )
            else:
                from tsl.identity.entra import MsalIdentity, SealedCache

                self.identity_provider = MsalIdentity(
                    self.org, SealedCache(self.home.msal_cache, self.keystore, dev)
                )
        return self.identity_provider

    def token(self) -> str:
        return self.identity().silent_token()

    # ---- plugin root (SDD-05 §3.1)
    def plugin_root(self) -> Path:
        cand = self.env.get("CLAUDE_PLUGIN_ROOT")
        if cand and (Path(cand) / ".claude-plugin" / "plugin.json").is_file():
            return Path(cand)
        f = self.home.plugin_root_file
        if f.is_file():
            p = Path(f.read_text(encoding="utf-8").strip())
            if (p / ".claude-plugin" / "plugin.json").is_file():
                return p
        raise TslError("E-ENV-01", item="truminds plugin (start a Claude Code session once)")

    def plugin_version(self) -> str:
        import json

        data = json.loads((self.plugin_root() / ".claude-plugin" / "plugin.json").read_text())
        return str(data["version"])

    def session_id(self) -> str | None:
        return self.env.get("TSL_SESSION_ID") or None

    def warn(self, text: str) -> None:
        self.stderr_lines.append(text)

    def prompt(self, text: str) -> None:
        """Write to stderr now, not when the command ends: the user must act on it (for example
        the sign-in code) while the command is still waiting."""
        self.prompt_lines.append(text)
        sys.stderr.write(text + "\n")
        sys.stderr.flush()

    def outbox(self) -> Any:
        from tsl.telemetry.outbox import Outbox

        return Outbox(self.home.outbox, self.clock, self.ids, strict=self.strict_events)


def default_runtime() -> Runtime:
    from tsl.github.client import HttpGitHubClient
    from tsl.harness.verifier import DockerVerifier
    from tsl.identity.keystore import KeyringKeyStore
    from tsl.identity.org import load_org
    from tsl.insights.client import HttpInsightsClient

    org = load_org()
    home = Home(Path.home() / ".truminds")
    clock = system_clock
    rt = Runtime(
        home=home,
        clock=clock,
        ids=IdFactory(clock),
        org=org,
        keystore=KeyringKeyStore(),
        insights=HttpInsightsClient(org.service_url),
        github=HttpGitHubClient(org.github_api_url),
        verifier=DockerVerifier(),
        env=dict(os.environ),
    )
    with contextlib.suppress(Exception):
        rt.insights = HttpInsightsClient(org.service_url, rt.service_timeout())
    return rt


_current: Runtime | None = None


def get_runtime() -> Runtime:
    global _current
    if _current is None:
        _current = default_runtime()
    return _current


@contextlib.contextmanager
def use_runtime(rt: Runtime) -> Iterator[Runtime]:
    """Install a runtime for the duration of a block (tests and embedding)."""
    global _current
    prev = _current
    _current = rt
    try:
        yield rt
    finally:
        _current = prev
