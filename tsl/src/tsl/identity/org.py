"""Organisation identity and endpoints, fixed inside the wheel (SDD-04 §7.1, SDD-07 TM-26).

``provider`` picks the identity provider (SDD-07 §1.4, ADR 0006): ``entra``
(default, production) or ``github`` (interim, test phase only). Like every other value here it is
baked in at build time; nothing at run time can change it.
"""

from __future__ import annotations

import tomllib
from importlib import resources
from typing import Literal

from pydantic import BaseModel, ConfigDict


class OrgConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    configured: bool
    tenant_id: str
    tsl_client_id: str
    api_scope: str
    service_url: str
    companion_remote_template: str
    github_api_url: str
    provider: Literal["entra", "github"] = "entra"
    # GitHub OAuth App (provider "github" only). The client id is public; there is no secret in tsl.
    github_client_id: str = ""
    github_oauth_url: str = "https://github.com"
    # Hosts allowed in artifact links (GEN-LINK-02) and org default limits.
    link_hosts: tuple[str, ...] = ()

    @property
    def authority(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}"


def load_org() -> OrgConfig:
    """Read tsl/_org.toml from the installed package. No other source is consulted."""
    text = resources.files("tsl").joinpath("_org.toml").read_text(encoding="utf-8")
    return OrgConfig.model_validate(tomllib.loads(text))
