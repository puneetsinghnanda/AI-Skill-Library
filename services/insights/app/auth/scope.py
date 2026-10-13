"""Role grants -> visible systems (SDD-09 §5.2), with RD-1 and RD-2 from configuration.

- RD-2 ``system`` (default): an ``engineer`` or ``tech_lead`` grant on a system shows that system
  only. ``project``: it shows every system in the same project (SDD-09 §5.2 text).
- RD-1: names are revealed only to the roles in ``rd1_name_reveal_roles`` (default ``eng_lead`` and
  ``admin``); add ``tech_lead`` for option (b).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import Connection, text

from app.auth.users import Grant
from app.config import ENGINEER_FAMILY, Settings


@dataclass(frozen=True)
class SystemInfo:
    id: str
    code: str
    project_id: str
    project_code: str
    client_id: str
    client_code: str
    domain: str
    companion_repo: str


@dataclass
class Scope:
    all_systems: bool = False
    systems: set[str] = field(default_factory=set)  # system ids
    name_systems: set[str] = field(default_factory=set)
    owned_skills: set[str] = field(default_factory=set)
    tech_lead_systems: set[str] = field(default_factory=set)
    engineer_systems: set[str] = field(default_factory=set)
    roles: set[str] = field(default_factory=set)
    engineer_family: bool = False
    any_grant: bool = False
    tech_lead: bool = False
    telemetry: bool = False
    catalogue: dict[str, SystemInfo] = field(default_factory=dict)

    @property
    def viewer_only(self) -> bool:
        return not (self.engineer_family or self.owned_skills)

    def system_ids(self) -> list[str]:
        if self.all_systems:
            return list(self.catalogue)
        return sorted(self.systems)

    def can_see_system(self, system_id: str | None) -> bool:
        return system_id is not None and (self.all_systems or system_id in self.systems)

    def can_see_names(self, system_id: str | None) -> bool:
        return system_id is not None and system_id in self.name_systems

    @property
    def can_reveal_names(self) -> bool:
        return bool(self.name_systems)


def load_systems(conn: Connection) -> dict[str, SystemInfo]:
    rows = conn.execute(
        text(
            "SELECT s.id::text AS id, s.code, p.id::text AS project_id, p.code AS project_code, "
            "c.id::text AS client_id, c.code AS client_code, s.domain, s.companion_repo "
            "FROM systems s JOIN projects p ON p.id = s.project_id JOIN clients c ON c.id = "
            "p.client_id"
        )
    ).all()
    return {
        r.id: SystemInfo(
            r.id,
            r.code,
            r.project_id,
            r.project_code,
            r.client_id,
            r.client_code,
            r.domain,
            r.companion_repo,
        )
        for r in rows
    }


def resolve_scope(conn: Connection, s: Settings, grants: list[Grant]) -> Scope:
    sc = Scope(catalogue=load_systems(conn))
    reveal = set(s.rd1_name_reveal_roles)
    allsys = set(sc.catalogue)
    by_code_skill_phase: dict[str, set[str]] = {}
    for g in grants:
        sc.roles.add(g.role)
        if g.role == "admin" or (g.role == "eng_lead" and g.scope_type == "org"):
            sc.all_systems = True
            sc.systems |= allsys
            if g.role in reveal:
                sc.name_systems |= allsys
            sc.telemetry = True
        if g.role in ("engineer", "tech_lead") and g.scope_type == "system" and g.scope_id:
            sid = g.scope_id
            if sid in sc.catalogue:
                if s.rd2_engineer_run_scope == "project":
                    pid = sc.catalogue[sid].project_id
                    sc.systems |= {x for x, i in sc.catalogue.items() if i.project_id == pid}
                else:
                    sc.systems.add(sid)
                sc.engineer_systems.add(sid)
        if g.role == "tech_lead" and g.scope_type == "system" and g.scope_id:
            sc.tech_lead = True
            sc.telemetry = True
            sc.tech_lead_systems.add(g.scope_id)
            if "tech_lead" in reveal:
                sc.name_systems.add(g.scope_id)
        if g.role == "eng_lead" and g.scope_type in ("client", "project") and g.scope_id:
            key = "client_id" if g.scope_type == "client" else "project_id"
            under = {x for x, i in sc.catalogue.items() if getattr(i, key) == g.scope_id}
            sc.systems |= under
            sc.telemetry = True
            if "eng_lead" in reveal:
                sc.name_systems |= under
        if g.role == "skill_owner" and g.scope_type == "skill" and g.scope_id:
            sc.owned_skills.add(g.scope_id)
        if g.role == "stage_approver" and g.scope_type == "stage" and g.scope_id:
            by_code_skill_phase.setdefault(g.scope_id, set())
    if by_code_skill_phase:
        rows = conn.execute(
            text("SELECT id, phase FROM skills WHERE phase = ANY(:p)"),
            {"p": list(by_code_skill_phase)},
        ).all()
        sc.owned_skills |= {r.id for r in rows}
    sc.engineer_family = any(g.role in ENGINEER_FAMILY for g in grants)
    sc.any_grant = bool(grants)
    return sc
