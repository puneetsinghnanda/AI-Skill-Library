"""Hatch build hook: bundle the repository JSON Schemas into the wheel.

The schemas live once, in ../schemas (registry §6). This hook reads
../schemas/index.json and force-includes every listed schema plus index.json
into the wheel at tsl/schemas/bundled/. Nothing is duplicated in the source tree.

It also bakes the organisation identity file (tsl/_org.toml, SDD-04 §7.1) from
build-time environment variables when they are set (release builds). At run
time nothing reads these variables; the values are fixed inside the wheel.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

ORG_KEYS = (
    "tenant_id",
    "tsl_client_id",
    "api_scope",
    "service_url",
    "companion_remote_template",
    "github_api_url",
)


class CustomBuildHook(BuildHookInterface):  # type: ignore[type-arg]
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        root = Path(self.root)
        plugin = root.parent / "plugins" / "truminds" / ".claude-plugin" / "plugin.json"
        if plugin.is_file():  # SDD-04 §2.1: tsl version equals the plugin version
            want = json.loads(plugin.read_text(encoding="utf-8"))["version"]
            if version != "editable" and self.metadata.version != want:
                raise RuntimeError(
                    f"tsl version {self.metadata.version} != plugin version {want} ({plugin})"
                )
        # In the repository the schemas sit next to tsl/; inside an sdist they were
        # copied to <sdist>/schemas by this same hook.
        schemas = (root.parent / "schemas").resolve()
        if not (schemas / "index.json").is_file():
            schemas = (root / "schemas").resolve()
        index = schemas / "index.json"
        if not index.is_file():
            raise RuntimeError(f"schema index not found at {index}; build from the repository")
        force = build_data.setdefault("force_include", {})
        dest = "schemas" if self.target_name == "sdist" else "tsl/schemas/bundled"
        force[str(index)] = f"{dest}/index.json"
        for entry in json.loads(index.read_text(encoding="utf-8"))["schemas"]:
            force[str(schemas / entry["file"])] = f"{dest}/{entry['file']}"
        if self.target_name == "sdist":
            return
        values = {k: os.environ.get(f"TSL_ORG_{k.upper()}") for k in ORG_KEYS}
        if all(values.values()):
            lines = [
                "# Generated at release build time (SDD-04 §7.1). Not secret.",
                "configured = true",
            ]
            lines += [f'{k} = "{v}"' for k, v in values.items()]
            tmp = Path(tempfile.mkdtemp()) / "_org.toml"
            tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
            force[str(tmp)] = "tsl/_org.toml"
