"""Pack freshness F1-F7, measured in product repo commits (SDD-06 §7)."""

from __future__ import annotations

import fnmatch
from typing import Any

from tsl.core.clock import parse_iso
from tsl.core.config import ORG_DEFAULTS
from tsl.core.hashing import sha256_file, sha256_raw
from tsl.core.jsonio import read_json
from tsl.core.repo import Companion
from tsl.core.runtime import Runtime
from tsl.gitops.git import Git, GitError
from tsl.identity.signing import canonical

MANIFEST = "context/manifest.json"
SIGNATURE = "context/pack.signature.json"
# SDD-06 reason codes -> run-state.v1 pack.reasons vocabulary
STATE_REASON = {
    "no_pack": "missing",
    "bad_signature": "signature_invalid",
    "edited_after_sign": "manifest_changed",
    "history_rewritten": "drift",
    "commits_behind": "age",
    "drift": "drift",
    "critical_change": "critical_change",
}


def pack_present(comp: Companion) -> bool:
    return comp.path(MANIFEST).is_file() and comp.path(SIGNATURE).is_file()


def manifest_sha(manifest: dict[str, Any]) -> str:
    return sha256_raw(canonical(manifest))


def status(rt: Runtime, comp: Companion, fetch: bool = True) -> dict[str, Any]:
    from tsl.identity.keys import public_key
    from tsl.identity.verify import accept, facts_from

    block: dict[str, Any] = {
        "fresh": False,
        "signed_at": None,
        "source_sha": {},
        "manifest_sha256": None,
        "reasons": [],
        "commits_behind": {},
        "drift_files": {},
        "checked_offline": False,
    }
    if not pack_present(comp):
        block["reasons"] = ["missing"]
        return {"state": "missing", "reasons": ["no_pack"], "state_block": block}
    manifest = read_json(comp.path(MANIFEST))
    sig = read_json(comp.path(SIGNATURE))
    block["signed_at"] = sig.get("signed_at")
    block["source_sha"] = dict(sig.get("sources") or {})
    block["manifest_sha256"] = sig.get("manifest_sha256")
    facts = public_key(rt, str(sig.get("key_id")), online=fetch)
    verdict, _ = accept(
        sig, parse_iso(str(sig.get("signed_at"))), [], facts_from(facts), check_roles=False
    )
    if verdict == "bad":
        block["reasons"] = ["signature_invalid"]
        return {"state": "invalid", "reasons": ["bad_signature"], "state_block": block}
    reasons: list[str] = []
    if manifest_sha(manifest) != sig.get("manifest_sha256"):
        reasons.append("edited_after_sign")
    else:
        for s in manifest.get("sections", []):
            p = comp.path(s["path"])
            if not p.is_file() or sha256_file(p) != s["sha256"]:
                reasons.append("edited_after_sign")
                break
    cfg = comp.config
    max_behind = int(ORG_DEFAULTS["context"]["max_commits_behind"])
    max_drift = int(cfg.ctx("drift_files"))
    critical = list(cfg.ctx("critical_paths"))
    for repo in cfg.product_repos:
        src = block["source_sha"].get(repo.name)
        clone = comp.product_clone(repo.name)
        if not src or clone is None:
            block["checked_offline"] = True
            continue
        g = Git(clone)
        if fetch:
            try:
                g.fetch()
            except GitError:
                block["checked_offline"] = True
        head = g.resolve(f"origin/{repo.default_branch}") or g.resolve("HEAD")
        if head is None or g.resolve(src) is None:
            block["checked_offline"] = True
            continue
        if not g.is_ancestor(src, head):
            reasons.append("history_rewritten")
            continue
        behind = g.rev_list_count(src, head, repo.path)
        changed = g.diff_names(src, head, repo.path)
        block["commits_behind"][repo.name] = behind
        block["drift_files"][repo.name] = len(changed)
        if behind > max_behind:
            reasons.append("commits_behind")
        if len(changed) > max_drift:
            reasons.append("drift")
        for cp in critical:
            r, _, glob = cp.partition(":")
            if r == repo.name and any(fnmatch.fnmatch(f, glob) for f in changed):
                reasons.append("critical_change")
    reasons = list(dict.fromkeys(reasons))
    block["reasons"] = list(dict.fromkeys(STATE_REASON[r] for r in reasons))
    block["fresh"] = not reasons
    return {"state": "fresh" if not reasons else "stale", "reasons": reasons, "state_block": block}
