"""User rows, pseudonyms and app-role sync (SDD-08 §8.1, SDD-07 §3.3-§3.4)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import Connection, text

from app.auth.entra import EntraClaims
from app.auth.github import GITHUB_TENANT, GitHubUser
from app.config import Settings
from app.crypto import email_hmac, encrypt, pseudonym_candidates
from app.errors import ServiceError
from app.timeutil import utcnow

SVC_ENTRA_SYNC_ID = "00000000-0000-0000-0000-000000000001"
APP_ROLES = frozenset({"Business", "Engineer", "TechLead", "Admin"})
ANY = "any"
CEILING: dict[str, frozenset[str] | str] = {
    "viewer": ANY,
    "engineer": frozenset({"Engineer", "TechLead"}),
    "tech_lead": frozenset({"TechLead"}),
    "skill_owner": frozenset({"Engineer", "TechLead"}),
    "stage_approver": frozenset({"TechLead"}),
    "eng_lead": frozenset({"TechLead", "Admin"}),
    "admin": frozenset({"Admin"}),
}
SYNC_EVERY = timedelta(minutes=10)


@dataclass(frozen=True)
class Grant:
    id: str
    role: str
    scope_type: str
    scope_id: str | None


@dataclass(frozen=True)
class User:
    id: str
    pseudonym: str
    active: bool
    agent_role: str | None
    app_roles: frozenset[str]


def allowed_by_ceiling(role: str, token_roles: frozenset[str]) -> bool:
    c = CEILING[role]
    return c == ANY or bool(isinstance(c, frozenset) and c & token_roles)


def _audit(
    conn: Connection,
    actor: str,
    action: str,
    target_type: str,
    target: str,
    before: object = None,
    after: object = None,
    reason: str | None = None,
    detail: dict[str, object] | None = None,
) -> None:
    conn.execute(
        text(
            "INSERT INTO audit_log (actor_user_id, action, target_type, target, before, after, "
            "reason, detail) "
            "VALUES (CAST(:a AS uuid), :ac, :tt, :t, CAST(:b AS jsonb), CAST(:af AS jsonb), :r, "
            "CAST(:d AS jsonb))"
        ),
        {
            "a": actor,
            "ac": action,
            "tt": target_type,
            "t": target,
            "b": json.dumps(before) if before is not None else None,
            "af": json.dumps(after) if after is not None else None,
            "r": reason,
            "d": json.dumps(detail or {}),
        },
    )


audit = _audit


def resolve_user(conn: Connection, s: Settings, c: EntraClaims) -> User:
    """Find or create the user by (tid, oid); sync app roles at most every 10 minutes."""
    row = conn.execute(
        text(
            "SELECT id::text, pseudonym, active, agent_role, app_roles, roles_synced_at FROM "
            "users "
            "WHERE tenant_id = CAST(:t AS uuid) AND sso_subject = CAST(:o AS uuid) FOR UPDATE"
        ),
        {"t": c.tid, "o": c.oid},
    ).first()
    if row is None:
        row = _create(conn, s, c)
    user = User(row.id, row.pseudonym, row.active, row.agent_role, frozenset(row.app_roles or []))
    if not user.active:
        raise ServiceError("E-AUTH-08", "Account deactivated")
    if not c.roles & APP_ROLES:
        raise ServiceError("E-AUTH-08", "No Truminds app role")
    synced: datetime | None = row.roles_synced_at
    if synced is None or utcnow() - synced > SYNC_EVERY or user.app_roles != c.roles:
        sync_roles(conn, user.id, c.roles)
        user = User(user.id, user.pseudonym, user.active, user.agent_role, c.roles)
    return user


def _create(conn: Connection, s: Settings, c: EntraClaims):  # type: ignore[no-untyped-def]  # Row
    name_enc = email_enc = mac = None
    key_id = None
    if c.name:
        name_enc, key_id = encrypt(s, c.name)
    if c.email:
        email_enc, key_id = encrypt(s, c.email)
        mac = email_hmac(s, c.email)
    for cand in pseudonym_candidates(s, c.tid, c.oid):
        row = conn.execute(
            text(
                "INSERT INTO users (tenant_id, sso_subject, pseudonym, display_name_enc, "
                "email_enc, "
                ""
                ""
                "email_hmac, enc_key_id) VALUES (CAST(:t AS uuid), CAST(:o AS uuid), :p, :n, :e, "
                ""
                ":m, :k) "
                "ON CONFLICT DO NOTHING "
                "RETURNING id::text, pseudonym, active, agent_role, app_roles, roles_synced_at"
            ),
            {
                "t": c.tid,
                "o": c.oid,
                "p": cand,
                "n": name_enc,
                "e": email_enc,
                "m": mac,
                "k": key_id,
            },
        ).first()
        if row is not None:
            return row
        again = conn.execute(
            text(
                "SELECT id::text, pseudonym, active, agent_role, app_roles, roles_synced_at FROM "
                ""
                "users "
                "WHERE tenant_id = CAST(:t AS uuid) AND sso_subject = CAST(:o AS uuid)"
            ),
            {"t": c.tid, "o": c.oid},
        ).first()
        if again is not None:  # created concurrently by another request
            return again
    raise RuntimeError("pseudonym space exhausted for this user")


def sync_roles(conn: Connection, user_id: str, token_roles: frozenset[str]) -> None:
    """SDD-07 §3.4 steps 1-4."""
    conn.execute(
        text(
            "UPDATE users SET app_roles = :r, roles_synced_at = now() WHERE id = CAST(:u AS uuid)"
        ),
        {"r": sorted(token_roles), "u": user_id},
    )
    grants = active_grants(conn, user_id)
    have = {(g.role, g.scope_type) for g in grants if g.scope_type == "org"}
    wanted: list[str] = []
    if ("viewer", "org") not in have:
        wanted.append("viewer")
    if "Admin" in token_roles and ("admin", "org") not in have:
        wanted.append("admin")
    for role in wanted:
        gid = conn.execute(
            text(
                "INSERT INTO role_grants (user_id, role, scope_type, scope_id, granted_at, "
                "granted_by) "
                "VALUES (CAST(:u AS uuid), :r, 'org', NULL, now(), CAST(:by AS uuid)) "
                "ON CONFLICT DO NOTHING RETURNING id::text"
            ),
            {"u": user_id, "r": role, "by": SVC_ENTRA_SYNC_ID},
        ).scalar()
        if gid:
            _audit(
                conn,
                SVC_ENTRA_SYNC_ID,
                "role_sync_grant",
                "role_grant",
                gid,
                after={"user": user_id, "role": role, "scope": "org"},
            )
    for g in grants:
        if not allowed_by_ceiling(g.role, token_roles):
            conn.execute(
                text("UPDATE role_grants SET revoked_at = now() WHERE id = CAST(:g AS uuid)"),
                {"g": g.id},
            )
            _audit(
                conn,
                SVC_ENTRA_SYNC_ID,
                "role_sync_revoke",
                "role_grant",
                g.id,
                before={"role": g.role, "scope_type": g.scope_type, "scope_id": g.scope_id},
            )


def active_grants(conn: Connection, user_id: str, at: datetime | None = None) -> list[Grant]:
    if at is None:
        rows = conn.execute(
            text(
                "SELECT id::text, role, scope_type, scope_id FROM role_grants "
                "WHERE user_id = CAST(:u AS uuid) AND revoked_at IS NULL"
            ),
            {"u": user_id},
        ).all()
    else:
        rows = conn.execute(
            text(
                "SELECT id::text, role, scope_type, scope_id FROM role_grants "
                "WHERE user_id = CAST(:u AS uuid) AND granted_at <= :at "
                "AND (revoked_at IS NULL OR revoked_at > :at)"
            ),
            {"u": user_id, "at": at},
        ).all()
    return [Grant(r.id, r.role, r.scope_type, r.scope_id) for r in rows]


def effective_grants(conn: Connection, user: User, token_roles: frozenset[str]) -> list[Grant]:
    return [g for g in active_grants(conn, user.id) if allowed_by_ceiling(g.role, token_roles)]


# ----------------------------------------------------------------------- GitHub (ADR 0006)
# With GitHub there are no app roles in the token. Roles come from the database: the role grants the
# admin screens manage. The app roles each grant implies (the same ceilings as CEILING above) are
# stored in users.app_roles so every app-role check works unchanged.
APP_ROLE_OF_GRANT: dict[str, str] = {
    "viewer": "Business",
    "engineer": "Engineer",
    "skill_owner": "Engineer",
    "tech_lead": "TechLead",
    "stage_approver": "TechLead",
    "eng_lead": "TechLead",
    "admin": "Admin",
}
SVC_BOOTSTRAP_ID = SVC_ENTRA_SYNC_ID  # the seeded service actor (inactive user row, migration 0003)


def app_roles_from_grants(grants: list[Grant]) -> frozenset[str]:
    return frozenset(APP_ROLE_OF_GRANT[g.role] for g in grants if g.role in APP_ROLE_OF_GRANT)


def resolve_github_user(
    conn: Connection, s: Settings, gh: GitHubUser
) -> tuple[User, frozenset[str], list[Grant]]:
    """Find or create the GitHub user; apply the bootstrap admin rule; derive app roles.

    Never raises for a missing role: the row must survive so an admin can grant roles to it. The
    caller refuses access (E-AUTH-08) after the transaction commits.
    """
    sub = gh.sso_subject
    row = conn.execute(
        text(
            "SELECT id::text, pseudonym, active, agent_role, app_roles, github_login FROM users "
            "WHERE tenant_id = CAST(:t AS uuid) AND sso_subject = CAST(:o AS uuid) FOR UPDATE"
        ),
        {"t": GITHUB_TENANT, "o": sub},
    ).first()
    if row is None:
        name_enc, key_id = encrypt(s, f"{gh.name} (@{gh.login})" if gh.name else f"@{gh.login}")
        for cand in pseudonym_candidates(s, GITHUB_TENANT, gh.subject):
            row = conn.execute(
                text(
                    "INSERT INTO users (tenant_id, sso_subject, pseudonym, display_name_enc, "
                    "enc_key_id, github_login) VALUES (CAST(:t AS uuid), CAST(:o AS uuid), :p, :n, "
                    ":k, :g) ON CONFLICT DO NOTHING "
                    "RETURNING id::text, pseudonym, active, agent_role, app_roles, github_login"
                ),
                {
                    "t": GITHUB_TENANT,
                    "o": sub,
                    "p": cand,
                    "n": name_enc,
                    "k": key_id,
                    "g": gh.login,
                },
            ).first()
            if row is not None:
                _audit(
                    conn,
                    SVC_BOOTSTRAP_ID,
                    "user_create",
                    "user",
                    cand,
                    after={"provider": "github", "github_login": gh.login},
                )
                break
        if row is None:
            raise RuntimeError("pseudonym space exhausted for this user")
    elif row.github_login != gh.login:  # GitHub logins can be renamed; the numeric id is the key
        conn.execute(
            text("UPDATE users SET github_login = :g WHERE id = CAST(:u AS uuid)"),
            {"g": gh.login, "u": row.id},
        )
    if row.active and gh.login.lower() in s.bootstrap_admin_github_logins:
        _bootstrap_admin(conn, row.id, row.pseudonym, gh.login)
    grants = active_grants(conn, row.id)
    roles = app_roles_from_grants(grants)
    if frozenset(row.app_roles or []) != roles:
        conn.execute(
            text(
                "UPDATE users SET app_roles = :r, roles_synced_at = now() "
                "WHERE id = CAST(:u AS uuid)"
            ),
            {"r": sorted(roles), "u": row.id},
        )
    user = User(row.id, row.pseudonym, row.active, row.agent_role, roles)
    return user, roles, grants


def _bootstrap_admin(conn: Connection, user_id: str, pseudonym: str, login: str) -> None:
    have = {(g.role, g.scope_type) for g in active_grants(conn, user_id)}
    for role in ("viewer", "admin"):
        if (role, "org") in have:
            continue
        gid = conn.execute(
            text(
                "INSERT INTO role_grants (user_id, role, scope_type, scope_id, granted_at, "
                "granted_by) VALUES (CAST(:u AS uuid), :r, 'org', NULL, now(), CAST(:by AS uuid)) "
                "ON CONFLICT DO NOTHING RETURNING id::text"
            ),
            {"u": user_id, "r": role, "by": SVC_BOOTSTRAP_ID},
        ).scalar()
        if gid:
            _audit(
                conn,
                SVC_BOOTSTRAP_ID,
                "bootstrap_admin_grant",
                "role_grant",
                gid,
                after={"user": pseudonym, "role": role, "scope": "org", "github_login": login},
                reason="BOOTSTRAP_ADMIN_GITHUB_LOGINS",
            )
