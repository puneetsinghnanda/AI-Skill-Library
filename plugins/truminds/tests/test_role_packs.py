"""Role packs (SDD-01 §11.3, proposed; PRD FR-AGT-02, PLN-01 ST-05.5; traceability GAP-04).

Mirrors rules RP-V01 to RP-V06 and RP-V08 until `tsl validate` gains them. RP-V07 (version bump against `main`)
needs git history and stays with `tsl validate`; here only the CHANGELOG entry for the current version is checked.
"""

from __future__ import annotations

from typing import Any

import pytest
import yaml

from conftest import PLUGIN, STATUS_RANK, errors, pods, satisfies, skill_meta, split_ref, workflows

ROLE_PACKS = PLUGIN / "role-packs"
ROLES = {  # SDD-01 §11.1: role id -> (display name, persona)
    "business-analyst": ("Business Analyst", "P-01"),
    "solution-architect": ("Solution Architect", "P-02"),
    "developer": ("Developer", "P-03"),
    "qa-engineer": ("QA Engineer", "P-04"),
    "security": ("Security", "P-06"),
    "devops": ("DevOps", "P-05"),
    "ux-designer": ("UX Designer", "P-07"),
    "delivery-manager": ("Delivery Manager", "P-08"),
}


def packs() -> dict[str, dict[str, Any]]:
    return {
        p.parent.name: yaml.safe_load(p.read_text(encoding="utf-8"))
        for p in sorted(ROLE_PACKS.glob("*/role-pack.yaml"))
    }


def test_one_role_pack_per_role() -> None:  # RP-V01
    folders = sorted(p.name for p in ROLE_PACKS.iterdir() if p.is_dir())
    assert folders == sorted(ROLES)
    assert sorted(packs()) == sorted(ROLES), "every folder holds role-pack.yaml"


@pytest.mark.parametrize("role", sorted(ROLES))
def test_role_pack_schema_identity_and_text(role: str) -> None:  # RP-V01, RP-V08
    pack = packs()[role]
    assert not errors("role-pack.v1", pack)
    assert pack["id"] == role
    assert (pack["title"], pack["persona"]) == ROLES[role]
    assert len(pack["title"]) <= 40 and len(pack["summary"]) <= 200
    changelog = (ROLE_PACKS / role / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## {pack['version']}" in changelog  # RP-V07 (local part)


@pytest.mark.parametrize("role", sorted(ROLES))
def test_role_pack_skills_are_exactly_the_roles_skills(role: str) -> None:  # RP-V02
    pack = packs()[role]
    owned = {sid for sid, m in skill_meta().items() if m["agent"] == role and m["status"] != "deprecated"}
    listed = [split_ref(r) for r in pack["skills"]]
    assert {s for s, _ in listed} == owned
    for skill, rng in listed:
        assert satisfies(skill_meta()[skill]["version"], rng), f"{skill}@{rng}"


def test_every_skill_is_in_exactly_one_role_pack() -> None:  # RP-V02
    seen: dict[str, str] = {}
    for role, pack in packs().items():
        for ref in pack["skills"]:
            skill = split_ref(ref)[0]
            assert skill not in seen, f"{skill} in {seen.get(skill)} and {role}"
            seen[skill] = role
    assert sorted(seen) == sorted(skill_meta())


@pytest.mark.parametrize("role", sorted(ROLES))
def test_role_pack_rubrics_are_the_skills_rubrics(role: str) -> None:  # RP-V03
    pack = packs()[role]
    skills = [split_ref(r)[0] for r in pack["skills"]]
    assert sorted(r["skill"] for r in pack["rubrics"]) == sorted(skills)
    for r in pack["rubrics"]:
        assert r["path"] == f"skills/{r['skill']}/{skill_meta()[r['skill']]['rubric']}"
        assert (PLUGIN / r["path"]).is_file(), r["path"]


@pytest.mark.parametrize("role", sorted(ROLES))
def test_role_pack_default_workflows_resolve_and_use_the_role(role: str) -> None:  # RP-V04
    pack = packs()[role]
    skills = {split_ref(r)[0] for r in pack["skills"]}
    for ref in pack["default_workflows"]:
        wid, rng = split_ref(ref)
        assert wid in workflows(), ref
        wf = workflows()[wid]
        assert satisfies(wf["version"], rng), ref
        used = {split_ref(s["skill"])[0] for s in wf["steps"] if "skill" in s}
        assert used & skills, f"{ref} uses none of the {role} skills"


@pytest.mark.parametrize("role", sorted(ROLES))
def test_role_pack_status_not_above_its_parts(role: str) -> None:  # RP-V05
    pack = packs()[role]
    ranks = [STATUS_RANK[skill_meta()[split_ref(r)[0]]["status"]] for r in pack["skills"]]
    ranks += [STATUS_RANK[workflows()[split_ref(r)[0]]["status"]] for r in pack["default_workflows"]]
    if pack["status"] == "deprecated":
        assert pack.get("deprecated_by")
    else:
        assert STATUS_RANK[pack["status"]] <= min(ranks)


@pytest.mark.parametrize("pod_id", sorted(pods()))
def test_pod_agents_match_their_role_packs(pod_id: str) -> None:  # RP-V06: pods reference role packs by role id
    for agent in pods()[pod_id]["agents"]:
        pack = packs().get(agent["role"])
        assert pack is not None, f"{pod_id}.{agent['key']}: no role pack for {agent['role']}"
        in_pack = {split_ref(r)[0] for r in pack["skills"]}
        cross = {c["skill"] for c in agent.get("cross_role_skills", [])}
        for ref in agent["skills"]:
            skill = split_ref(ref)[0]
            where = f"{pod_id}.{agent['key']}"
            assert skill in in_pack or skill in cross, f"{where}: {skill} not in role pack {agent['role']}"
        assert not (cross & in_pack), f"{pod_id}.{agent['key']}: {cross & in_pack} is not cross-role"


def test_role_packs_are_not_loaded_as_skills() -> None:
    """Claude Code loads skills only from skills/; role packs hold no SKILL.md (SDD-05 §3.1)."""
    assert not list(ROLE_PACKS.rglob("SKILL.md"))
    assert all(p.suffix in (".yaml", ".md") for p in ROLE_PACKS.rglob("*") if p.is_file())
