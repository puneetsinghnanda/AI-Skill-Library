"""Service configuration (SDD-08 §3.1, OPS-01 §5.3).

Every value comes from an environment variable. Secrets are read only from files named by a
``*_FILE`` variable (OPS-01 §7.2), never from the variable itself. Open policy decisions RD-1 to
RD-4 (registry §11) are configuration values here, not code.

Hosted test environment (deploy/render/README.md, ADR 0006 addendum): a platform such as Render
gives secrets only as environment variables and the database as one URL. There, ``DATABASE_URL``,
``DATA_KEY``, ``PSEUDONYM_PEPPER`` and ``DB_ROLE_PASSWORD_KEY`` are accepted as values. Production
refuses them (``check_hosting``), so production keeps the file-only rule.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

SERVICE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SCHEMAS_DIR = SERVICE_DIR.parent.parent / "schemas"

ENGINEER_FAMILY = ("engineer", "tech_lead", "eng_lead", "admin")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", frozen=True)

    # ENVIRONMENT (or the older ENV). "test" shows the TEST ENVIRONMENT banner (GET /v1/status).
    env: Literal["dev", "test", "staging", "prod"] = Field(
        default="dev", validation_alias=AliasChoices("ENVIRONMENT", "ENV", "env")
    )
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

    # --- Identity provider (SDD-07 §1.4, ADR 0006) ---
    # "entra" (default, production) or "github" (interim, test phase only; refused when ENV=prod).
    identity_provider: Literal["entra", "github"] = "entra"
    github_client_id: str = ""
    # The OAuth App client secret: GITHUB_CLIENT_SECRET_FILE (secret store) or GITHUB_CLIENT_SECRET
    # (env file on the host). Never in git.
    github_client_secret: SecretStr | None = None
    github_client_secret_file: Path | None = None
    github_oauth_url: str = "https://github.com"
    github_api_url: str = "https://api.github.com"
    github_token_cache_s: int = 300
    # Comma-separated GitHub logins that receive the org `admin` (and `viewer`) grant when they sign
    # in. Visible: logged at startup and audited per grant (action bootstrap_admin_grant).
    bootstrap_admin_github_logins: Annotated[tuple[str, ...], NoDecode] = ()
    session_max_age_s: int = 8 * 3600

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
    # Hosted test environment only (refused when ENV=prod). One owner URL, for example Neon's direct
    # connection string. The runtime roles log in with passwords derived from DB_ROLE_PASSWORD_KEY.
    database_url_value: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("DATABASE_URL", "database_url_value")
    )
    database_url_migrations: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("DATABASE_URL_MIGRATIONS", "database_url_migrations"),
    )
    db_role_password_key: SecretStr | None = None
    read_statement_timeout_ms: int = 5000

    # --- Secrets (SDD-08 §8.1, §9.2) ---
    pseudonym_pepper_file: Path | None = None
    data_key_file: Path | None = None
    # Hosted test environment only (refused when ENV=prod): the same secrets as values.
    pseudonym_pepper_value: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("PSEUDONYM_PEPPER", "pseudonym_pepper_value")
    )
    data_key_value: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("DATA_KEY", "data_key_value")
    )
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
    rd1_name_reveal_roles: Annotated[tuple[str, ...], NoDecode] = ("eng_lead", "admin")  # RD-1 (a)
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
    # Setting SERVE_PORTAL_DIR serves the built portal from that folder (same as SERVE_PORTAL=true
    # with PORTAL_DIST_DIR). Used by the hosted test environment.
    serve_portal_dir: Path | None = None
    # Hosted test environment: GitHub webhooks registered at start, "HOOK_ID:org[/repo],..."
    # (the secret is GITHUB_WEBHOOK_SECRET). Replaces `admin hook create` where there is no shell.
    github_webhook_hooks: Annotated[tuple[str, ...], NoDecode] = ()
    github_webhook_secret: SecretStr | None = None
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

    @field_validator(
        "rd1_name_reveal_roles",
        "bootstrap_admin_github_logins",
        "github_webhook_hooks",
        mode="before",
    )
    @classmethod
    def _split(cls, v: object) -> object:
        if isinstance(v, str):
            return tuple(x.strip() for x in v.split(",") if x.strip())
        return v

    @field_validator("bootstrap_admin_github_logins")
    @classmethod
    def _lower(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(x.lower() for x in v)

    # ----- derived values -----
    @property
    def issuer(self) -> str:
        return f"{self.entra_authority_host}/{self.entra_tenant_id}/v2.0"

    @property
    def jwks_url(self) -> str:
        return self.entra_jwks_url or (
            f"{self.entra_authority_host}/{self.entra_tenant_id}/discovery/v2.0/keys"
        )

    @property
    def portal_dir(self) -> Path | None:
        """The built portal to serve, or None when this service does not serve it."""
        if self.serve_portal_dir is not None:
            return self.serve_portal_dir
        return self.portal_dist_dir if self.serve_portal else None

    def database_url(self, role: Literal["owner", "app", "read", "reveal"]) -> str:
        user = {
            "owner": self.database_owner_user,
            "app": self.database_app_user,
            "read": self.database_read_user,
            "reveal": self.database_reveal_user,
        }[role]
        if self.database_url_value is not None:
            return hosted_database_url(
                self.database_url_value.get_secret_value(),
                None if role == "owner" else (user, self.role_password(role)),
            )
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

    def migrations_url(self) -> str:
        """Owner URL for Alembic: DATABASE_URL_MIGRATIONS when set, else the owner URL."""
        if self.database_url_migrations is not None:
            return hosted_database_url(self.database_url_migrations.get_secret_value(), None)
        return self.database_url("owner")

    def role_password(self, role: Literal["app", "read", "reveal"]) -> str:
        """Login password of a runtime role in the hosted test environment (HMAC of the key)."""
        if self.db_role_password_key is None:
            raise RuntimeError("DATABASE_URL needs DB_ROLE_PASSWORD_KEY for the runtime roles")
        key = self.db_role_password_key.get_secret_value().encode()
        if len(key) < 32:
            raise RuntimeError("DB_ROLE_PASSWORD_KEY must hold at least 32 characters")
        return hmac.new(key, f"insights-db-role:{role}".encode(), hashlib.sha256).hexdigest()

    def check_hosting(self) -> None:
        """Value secrets and a database URL are for the hosted test environment only."""
        values = {
            "DATABASE_URL": self.database_url_value,
            "DATABASE_URL_MIGRATIONS": self.database_url_migrations,
            "DB_ROLE_PASSWORD_KEY": self.db_role_password_key,
            "PSEUDONYM_PEPPER": self.pseudonym_pepper_value,
            "DATA_KEY": self.data_key_value,
        }
        given = sorted(k for k, v in values.items() if v is not None)
        if given and self.env == "prod":
            raise RuntimeError(
                f"{', '.join(given)}: secrets as variables are for the test phase only; "
                "production reads secrets from *_FILE (OPS-01 §7.2)"
            )
        if self.database_url_value is not None:
            hosted_database_url(self.database_url_value.get_secret_value(), None)
            self.role_password("app")

    def github_secret(self) -> str:
        if self.github_client_secret_file:
            return read_secret(self.github_client_secret_file)
        if self.github_client_secret is not None:
            return self.github_client_secret.get_secret_value()
        raise RuntimeError("GITHUB_CLIENT_SECRET_FILE or GITHUB_CLIENT_SECRET is not set")

    def check_identity(self) -> None:
        """Refuse a configuration that ADR 0006 does not allow. Called at app start."""
        if self.identity_provider == "github":
            if self.env == "prod":
                raise RuntimeError("IDENTITY_PROVIDER=github is for the test phase only (ADR 0006)")
            if not self.github_client_id:
                raise RuntimeError("IDENTITY_PROVIDER=github needs GITHUB_CLIENT_ID")

    def pepper(self) -> bytes:
        if self.pseudonym_pepper_file:
            raw = read_secret(self.pseudonym_pepper_file).encode()
        elif self.pseudonym_pepper_value is not None:
            raw = self.pseudonym_pepper_value.get_secret_value().strip().encode()
        else:
            raise RuntimeError("PSEUDONYM_PEPPER_FILE is not set")
        if len(raw) < 32:
            raise RuntimeError("pseudonym pepper must hold at least 32 bytes")
        return raw

    def data_key(self) -> bytes:
        if self.data_key_file:
            key = base64.b64decode(read_secret(self.data_key_file))
        elif self.data_key_value is not None:
            key = base64.b64decode(self.data_key_value.get_secret_value().strip())
        else:
            raise RuntimeError("DATA_KEY_FILE is not set")
        if len(key) != 32:
            raise RuntimeError("DATA_KEY_FILE must hold 32 bytes, base64")
        return key


INSECURE_SSLMODES = frozenset({"disable", "allow", "prefer"})


def hosted_database_url(raw: str, login: tuple[str, str] | None) -> str:
    """A hosted ``postgresql://`` URL (for example Neon's) as a SQLAlchemy psycopg URL.

    ``login`` replaces the user and password (the runtime roles); query options such as
    ``sslmode=require`` and ``channel_binding=require`` are kept. Refused: a non-PostgreSQL URL, a
    remote host without TLS, and Neon's pooled endpoint, because the service relies on session
    state (advisory lock, statement timeout) that a transaction pooler does not keep.
    """
    from sqlalchemy.engine import make_url
    from sqlalchemy.exc import ArgumentError

    raw = raw.strip()
    if raw.startswith("postgres://"):  # the short scheme some providers print
        raw = "postgresql://" + raw[len("postgres://") :]
    try:
        url = make_url(raw)
    except ArgumentError:
        raise RuntimeError("DATABASE_URL is not a valid database URL") from None
    if url.get_backend_name() != "postgresql":
        raise RuntimeError("DATABASE_URL must be a postgresql:// URL")
    host = url.host or ""
    if not host or not url.database:
        raise RuntimeError("DATABASE_URL needs a host and a database name")
    if "-pooler." in host:
        raise RuntimeError(
            "DATABASE_URL is Neon's pooled endpoint (-pooler); use the direct connection string"
        )
    local = host in ("localhost", "127.0.0.1", "::1")
    if not local and str(url.query.get("sslmode", "prefer")) in INSECURE_SSLMODES:
        raise RuntimeError("DATABASE_URL must use TLS: add ?sslmode=require (or verify-full)")
    url = url.set(drivername="postgresql+psycopg")
    if login is not None:
        url = url.set(username=login[0], password=login[1])
    return url.render_as_string(hide_password=False)


def read_secret(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
