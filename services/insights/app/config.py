"""Service configuration (SDD-08 §3.1, OPS-01 §5.3).

Every value comes from an environment variable. Secrets are read only from files named by a
``*_FILE`` variable (OPS-01 §7.2), never from the variable itself. Open policy decisions RD-1 to
RD-4 (registry §11) are configuration values here, not code.
"""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SCHEMAS_DIR = SERVICE_DIR.parent.parent / "schemas"

ENGINEER_FAMILY = ("engineer", "tech_lead", "eng_lead", "admin")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", frozen=True)

    env: Literal["dev", "test", "staging", "prod"] = "dev"
    service_version: str = "0.1.0"
    public_base_url: str = "http://localhost:8000"

    # --- Microsoft Entra ID (ADR 0002, SDD-07 §9) ---
    entra_tenant_id: str = ""
    entra_api_audience: str = ""  # truminds-insights-api application (client) ID (registry §10 #23)
    entra_tsl_client_id: str = ""
    entra_portal_client_id: str = ""
    entra_authority_host: str = "https://login.microsoftonline.com"
    entra_jwks_url: str | None = None  # default: <authority>/<tenant>/discovery/v2.0/keys
    entra_jwks_file: Path | None = None  # JWKS document on disk (air-gapped hosts and tests)
    entra_leeway_s: int = 60

    # --- Database (OPS-01 §5.3, SDD-08 §9.4) ---
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "insights"
    database_sslmode: str = "verify-full"
    database_ca_file: Path | None = None
    database_owner_user: str = "insights_owner"
    database_app_user: str = "insights_app"
    database_read_user: str = "insights_read"
    database_reveal_user: str = "insights_reveal"
    database_owner_password_file: Path | None = None
    database_app_password_file: Path | None = None
    database_read_password_file: Path | None = None
    database_reveal_password_file: Path | None = None
    database_pool_size: int = 5
    read_statement_timeout_ms: int = 5000

    # --- Secrets (SDD-08 §8.1, §9.2) ---
    pseudonym_pepper_file: Path | None = None
    data_key_file: Path | None = None
    data_key_id: str = "dk-1"

    # --- Schemas and catalogue ---
    schemas_dir: Path = DEFAULT_SCHEMAS_DIR
    catalogue_source_dir: Path | None = None  # checked-out release tree for catalogue sync
    marketplace_repo: str = ""  # org/repo of the skill library; release webhooks come from it

    # --- Retention (SDD-08 §8.2; OQ-08, RD-4) ---
    retention_events_months: int = 13
    retention_otel_days: int = 90
    retention_webhook_days: int = 30
    retention_runs_months: int = 13
    audit_retention_months: int = 36  # RD-4 default: 3 years (registry §11)

    # --- Policy decisions (registry §11) ---
    rd1_name_reveal_roles: tuple[str, ...] = ("eng_lead", "admin")  # RD-1 (a)
    rd2_engineer_run_scope: Literal["system", "project"] = "system"  # RD-2 (a)
    rd3_question_text_in_cloud: bool = False  # RD-3 (a)
    rd5_first_pass_metric: Literal["first_try"] = "first_try"  # noqa: S105 - RD-5 (b), not a secret
    rd6_workflow_names: Literal["doc3", "doc1"] = "doc3"  # RD-6 (a): canonical workflow-name set

    # --- Limits ---
    ingest_rate_per_s: float = 20.0
    ingest_burst: int = 40
    read_rate_per_s: float = 10.0
    read_burst: int = 30
    max_batch_events: int = 500
    max_body_bytes: int = 1024 * 1024
    max_otel_body_bytes: int = 4 * 1024 * 1024
    clock_skew_s: int = 300
    key_max_age_days: int = 180
    key_proof_window_s: int = 300
    first_try_target: float = 0.80

    # --- OTel, improvement ---
    otel_allowlist_file: Path = SERVICE_DIR / "app" / "otel" / "allowlist.yaml"
    improvement_thresholds_file: Path = SERVICE_DIR / "app" / "improvement_thresholds.yaml"

    # --- Observability and serving ---
    metrics_port: int = 9100
    worker_metrics_port: int = 9101
    serve_portal: bool = (
        False  # SDD-09 §10 (api serves portal/dist) vs OPS-01 §2 (portal container)
    )
    portal_dist_dir: Path = Path("/app/portal")
    companion_url_base: str = "https://github.com"
    view_refresh_interval_s: int = 300

    @field_validator("rd3_question_text_in_cloud")
    @classmethod
    def _rd3(cls, v: bool) -> bool:
        if v:
            raise ValueError(
                "RD-3 option (b) (question titles in the cloud) needs a new event field and "
                "consent wording first; no event carries question text (X-06)"
            )
        return v

    @field_validator("rd1_name_reveal_roles", mode="before")
    @classmethod
    def _split(cls, v: object) -> object:
        if isinstance(v, str):
            return tuple(x.strip() for x in v.split(",") if x.strip())
        return v

    # ----- derived values -----
    @property
    def issuer(self) -> str:
        return f"{self.entra_authority_host}/{self.entra_tenant_id}/v2.0"

    @property
    def jwks_url(self) -> str:
        return self.entra_jwks_url or (
            f"{self.entra_authority_host}/{self.entra_tenant_id}/discovery/v2.0/keys"
        )

    def database_url(self, role: Literal["owner", "app", "read", "reveal"]) -> str:
        user = {
            "owner": self.database_owner_user,
            "app": self.database_app_user,
            "read": self.database_read_user,
            "reveal": self.database_reveal_user,
        }[role]
        pw_file = {
            "owner": self.database_owner_password_file,
            "app": self.database_app_password_file,
            "read": self.database_read_password_file,
            "reveal": self.database_reveal_password_file,
        }[role]
        from sqlalchemy.engine import URL

        query: dict[str, str] = {"sslmode": self.database_sslmode}
        if self.database_ca_file:
            query["sslrootcert"] = str(self.database_ca_file)
        url = URL.create(
            "postgresql+psycopg",
            username=user,
            password=read_secret(pw_file) if pw_file else None,
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
            query=query,
        )
        return url.render_as_string(hide_password=False)

    def pepper(self) -> bytes:
        if not self.pseudonym_pepper_file:
            raise RuntimeError("PSEUDONYM_PEPPER_FILE is not set")
        raw = read_secret(self.pseudonym_pepper_file).encode()
        if len(raw) < 32:
            raise RuntimeError("pseudonym pepper must hold at least 32 bytes")
        return raw

    def data_key(self) -> bytes:
        if not self.data_key_file:
            raise RuntimeError("DATA_KEY_FILE is not set")
        key = base64.b64decode(read_secret(self.data_key_file))
        if len(key) != 32:
            raise RuntimeError("DATA_KEY_FILE must hold 32 bytes, base64")
        return key


def read_secret(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
