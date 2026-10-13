"""Display labels (SDD-01 §11 roles and phases; SDD-09 §5.6.12 status labels)."""

from __future__ import annotations

AGENT_ROLES: list[tuple[str, str, str]] = [
    ("business-analyst", "BA", "Business Analyst"),
    ("solution-architect", "SA", "Solution Architect"),
    ("developer", "DV", "Developer"),
    ("qa-engineer", "QA", "QA Engineer"),
    ("security", "SE", "Security"),
    ("devops", "DO", "DevOps"),
    ("ux-designer", "UX", "UX Designer"),
    ("delivery-manager", "DM", "Delivery Manager"),
]
AGENT_LABEL = {r: label for r, _c, label in AGENT_ROLES}
AGENT_CODE = {r: c for r, c, _l in AGENT_ROLES}
PHASES: list[tuple[str, str]] = [
    ("requirements", "Requirements"),
    ("design", "Design"),
    ("build", "Build"),
    ("test", "Test"),
    ("operate", "Operate"),
]
ROLE_LABELS = {
    "viewer": "Viewer",
    "engineer": "Engineer",
    "tech_lead": "Tech lead",
    "skill_owner": "Skill owner",
    "stage_approver": "Stage approver",
    "eng_lead": "Engineering lead",
    "admin": "Admin",
}
STATUS_RANK = {"production": 0, "pilot": 1, "draft": 2, "deprecated": 3}


def status_label(status: str | None, end_reason: str | None) -> str:
    if status == "RUNNING":
        return "Running"
    if status == "PAUSED_INPUT":
        return "Needs input"
    if status == "PAUSED_APPROVAL":
        return "Needs approval"
    if status == "COMPLETED":
        return "Aborted" if end_reason == "aborted" else "Completed"
    return "Unknown"
