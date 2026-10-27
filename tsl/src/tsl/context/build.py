"""tsl context build | sign | status | deny-term (SDD-06 §6, SDD-04 §6.15)."""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

from tsl.context import extractors as ex
from tsl.context.freshness import MANIFEST, SIGNATURE, manifest_sha
from tsl.context.freshness import status as fresh_status
from tsl.context.repoview import RepoView
from tsl.core.clock import iso
from tsl.core.config import ORG_DEFAULTS
from tsl.core.errors import TslError
from tsl.core.frontmatter import FrontMatterError, headings, split
from tsl.core.hashing import sha256_file, sha256_text
from tsl.core.jsonio import atomic_write, dump_yaml, dumps, read_json, write_json
from tsl.core.repo import Companion
from tsl.core.runtime import Runtime
from tsl.gitops.git import Git, GitError
from tsl.harness import citations, detectors
from tsl.identity import me as memod
from tsl.identity.keys import load_signer
from tsl.identity.signing import sign_object
from tsl.telemetry.emit import emit

JUDGEMENT = [
    "system-baseline",
    "architecture",
    "data-model",
    "glossary",
    "conventions",
    "test-strategy",
    "intent-baseline",
]
FACT_SECTIONS = ["module-map", "dependency-graph", "api-inventory", "db-schema", "test-layout"]
TITLES = {
    "system-baseline": "System baseline",
    "architecture": "Architecture",
    "data-model": "Data model",
    "glossary": "Glossary",
    "conventions": "Conventions",
    "test-strategy": "Test strategy",
    "intent-baseline": "Intent baseline",
}
# Org defaults; tsl.yaml context.limits may only lower them (TslConfig.pack_limits).
LIMITS = dict(ORG_DEFAULTS["context"]["limits"])
DRAFT = re.compile(r"<!--\s*tsl:draft\s+id=D-\d+\s*-->")
ANCHOR_SYNTAX = re.compile(r"\{#([^}]*)\}")


def tokens(n_bytes: int) -> int:
    return math.ceil(n_bytes / 4)


def _views(
    rt: Runtime, comp: Companion, commits: dict[str, str] | None, fetch: bool
) -> tuple[list[RepoView], list[dict[str, str]]]:
    views: list[RepoView] = []
    warnings: list[dict[str, str]] = []
    for repo in comp.config.product_repos:
        clone = comp.product_clone(repo.name)
        if clone is None:
            raise TslError("E-CTX-09", repo=repo.name)
        g = Git(clone)
        if fetch:
            try:
                g.fetch()
            except GitError:
                warnings.append(
                    {
                        "code": "E-NET-02",
                        "message": f"{repo.name}: offline; using the last fetched head",
                    }
                )
        want = (commits or {}).get(repo.name)
        sha = (
            g.resolve(want)
            if want
            else (g.resolve(f"origin/{repo.default_branch}") or g.resolve("HEAD"))
        )
        if sha is None:
            raise TslError("E-CTX-09", repo=repo.name)
        views.append(RepoView(repo.name, sha, repo.path, clone, comp.config.extra_exclude))
    return views, warnings


def _redact_value(v: Any, counts: dict[str, int], deny: frozenset[str] = frozenset()) -> Any:
    if isinstance(v, str):
        hits = detectors.scan(v, deny_term_hashes=deny)
        if hits:
            counts["masked"] += len(hits)
            return detectors.mask(v, hits)
        return v
    if isinstance(v, list):
        return [_redact_value(x, counts, deny) for x in v]
    if isinstance(v, dict):
        return {
            k: (x if k in ("id", "kind", "source") else _redact_value(x, counts, deny))
            for k, x in v.items()
        }
    return v


def run_extractors(
    views: list[RepoView],
    migration_globs: list[str] | None = None,
    test_globs: list[str] | None = None,
    deny: frozenset[str] = frozenset(),
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, str]], int, int]:
    """section -> context-facts.v1 document; extractor list; errors; masked; excluded.

    Globs and deny-term hashes come from tsl.yaml `context.extractors` and
    `context.redaction` (SDD-06 §5.2, §9.4).
    """
    regs = ex.registry(migration_globs, test_globs)
    per: dict[str, list[tuple[str, ex.ExtractResult, str]]] = {s: [] for s in FACT_SECTIONS}
    errors: list[dict[str, str]] = []
    used: dict[str, str] = {}
    for e in regs:
        for v in views:
            try:
                if e.applies(v):
                    per[e.section].append((v.repo, e.extract(v), e.name))
                    used[e.name] = e.version
            except Exception as exc:  # one bad parser does not block the pack (E-CTX-08)
                errors.append(
                    {
                        "code": "E-CTX-08",
                        "message": f"Extractor {e.name} failed on {v.repo} "
                        f"({type(exc).__name__}); section {e.section} not rebuilt.",
                    }
                )
    counts = {"masked": 0}
    out: dict[str, dict[str, Any]] = {}
    sources = {v.repo: v.commit for v in views}
    names = {e.section: e.name for e in regs}
    for sec in FACT_SECTIONS:
        facts: dict[str, dict[str, Any]] = {}
        unresolved: list[dict[str, Any]] = []
        reasons: list[str] = []
        for _repo, res, _name in per[sec]:
            for f in res.facts:
                f = _redact_value(f, counts, deny)
                if f["id"] in facts and json.dumps(facts[f["id"]], sort_keys=True) != json.dumps(
                    f, sort_keys=True
                ):
                    errors.append(
                        {
                            "code": "E-CTX-08",
                            "message": f"duplicate fact id {f['id']} with different content",
                        }
                    )
                    continue
                facts[f["id"]] = f
            unresolved += res.unresolved
            if res.empty_reason:
                reasons.append(res.empty_reason)
        doc: dict[str, Any] = {
            "schema": "context-facts.v1",
            "section": sec,
            "extractor": {"name": names[sec], "version": used.get(names[sec], "1.0.0")},
            "sources": sources,
            "empty_reason": None,
            "facts": [facts[k] for k in sorted(facts)],
            "unresolved": sorted(unresolved, key=lambda u: json.dumps(u, sort_keys=True)),
        }
        if not doc["facts"]:
            doc["empty_reason"] = (reasons[0] if reasons else "extractor did not apply")[:200]
        out[sec] = doc
    extractors = [{"name": n, "version": used[n]} for n in sorted(used)]
    excluded = sum(v.excluded_count for v in views)
    return out, extractors, errors, counts["masked"], excluded


def _template(section: str, owner: str) -> str:
    front = {
        "schema": "context-section.v1",
        "section": section,
        "owner": owner,
        "origin": "human",
        "status": "drafted",
        "verified_at": None,
    }
    return f"---\n{dump_yaml(front)}---\n\n# {TITLES[section]} {{#{section}}}\n"


def lint_judgement(
    comp: Companion, repos: set[str], sources: dict[str, str], fresh: dict[str, str] | None = None
) -> tuple[list[dict[str, Any]], list[str], int]:
    deny = comp.config.deny_term_hashes
    """(sections, lint errors, blocking redaction hits) for context/*.md."""
    sections: list[dict[str, Any]] = []
    errs: list[str] = []
    blocking = 0
    clones = comp.local_paths()
    # `fresh`: the facts this build just extracted. Citations are checked against them,
    # not against the previous build's files still on disk.
    resolver = citations.Resolver(comp.root, clones, sources, fresh)
    for sec in JUDGEMENT:
        p = comp.path(f"context/{sec}.md")
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8")
        try:
            doc = split(text)
        except FrontMatterError as exc:
            errs.append(f"context/{sec}.md: {exc}")
            continue
        from tsl.schemas.registry import errors as schema_errors

        for e in schema_errors("context-section.v1", doc.front)[:1]:
            errs.append(f"context/{sec}.md front matter {e.pointer}: {e.message}")
        anchors: list[str] = []
        for line in doc.body.split("\n"):
            for m in ANCHOR_SYNTAX.finditer(line):
                if not re.fullmatch(r"[a-z0-9-]{1,64}", m.group(1)):
                    errs.append(f"context/{sec}.md: bad anchor {{#{m.group(1)}}}")
        for h in headings(doc.body):
            if h.anchor:
                if h.anchor in anchors:
                    errs.append(f"context/{sec}.md: duplicate anchor {h.anchor}")
                anchors.append(h.anchor)
        for i, line in enumerate(doc.body.split("\n")):
            if line.strip().startswith("Sources:"):
                for ref in [x.strip() for x in line.split(":", 1)[1].split(",") if x.strip()]:
                    c = citations.parse(ref, repos)
                    if c is None:
                        errs.append(
                            f"context/{sec}.md line {i + doc.body_start_line}: bad citation {ref}"
                        )
                        continue
                    t, _why = resolver.read(c)
                    if t is None or citations.span_for(c, t)[0] is None:
                        errs.append(
                            f"context/{sec}.md line {i + doc.body_start_line}: citation {ref} "
                            f"does not resolve"
                        )
        hits = [
            h
            for h in detectors.scan(text, deny_term_hashes=deny)
            if h.kind in ("secret", "pii", "term")
        ]
        blocking += len(hits)
        size = len(text.encode("utf-8"))
        sections.append(
            {
                "id": sec,
                "path": f"context/{sec}.md",
                "kind": "judgement",
                "required": sec != "intent-baseline",
                "origin": doc.front.get("origin", "human"),
                "status": doc.front.get("status", "drafted"),
                "owner": doc.front.get("owner", "tl-0000"),
                "verified_at": doc.front.get("verified_at") or {},
                "sha256": sha256_file(p),
                "tokens_est": tokens(size),
                "anchors": anchors,
                "_drafts": len(DRAFT.findall(text)),
                "_hits": [(h.rule_id, h.line, h.kind) for h in hits],
            }
        )
    return sections, errs, blocking


def compute(
    rt: Runtime, comp: Companion, commits: dict[str, str] | None, fetch: bool
) -> dict[str, Any]:
    views, warnings = _views(rt, comp, commits, fetch)
    cfg = comp.config
    limits = cfg.pack_limits()
    generated, extractors, ex_errors, masked, excluded = run_extractors(
        views,
        cfg.extractor_globs("migrations"),
        cfg.extractor_globs("tests"),
        cfg.deny_term_hashes,
    )
    repos = {r.name for r in comp.config.product_repos} | {
        str(r["name"]) for r in comp.config.read_only_repos
    }
    sources = {v.repo: v.commit for v in views}
    gen_text = {s: dumps(d) for s, d in generated.items()}
    fresh = {f"context/generated/{s}.json": t for s, t in gen_text.items()}
    jsections, lint, blocking = lint_judgement(comp, repos, sources, fresh)
    sections: list[dict[str, Any]] = []
    size_errs: list[str] = []
    for sec, text in gen_text.items():
        b = len(text.encode("utf-8"))
        if b > limits["generated_file_bytes"]:
            size_errs.append(f"generated/{sec}.json is {b} bytes (sharding not supported yet)")
        sections.append(
            {
                "id": sec,
                "path": f"context/generated/{sec}.json",
                "kind": "fact",
                "required": True,
                "sha256": sha256_text(text),
                "tokens_est": tokens(b),
                "fact_count": len(generated[sec]["facts"]),
                "empty_reason": generated[sec]["empty_reason"],
            }
        )
    total_j = 0
    for s in jsections:
        total_j += s["tokens_est"]
        if s["tokens_est"] > limits["section_tokens"]:
            size_errs.append(
                f"{s['path']} is {s['tokens_est']} tokens over {limits['section_tokens']}"
            )
        sections.append({k: v for k, v in s.items() if not k.startswith("_")})
    if total_j > limits["judgement_tokens"]:
        size_errs.append(f"judgement sections {total_j} tokens over {limits['judgement_tokens']}")
    sections.sort(key=lambda s: s["id"])
    manifest = {
        "schema": "context-pack.v1",
        "system": comp.config.system.code,
        "built_by": f"tsl@{rt.tsl_version}",
        "sources": [
            {
                "repo": v.repo,
                "commit": v.commit,
                "default_branch": (
                    comp.config.repo(v.repo) or comp.config.product_repos[0]
                ).default_branch,
                "scope": v.scope,
                "files_scanned": len(v.list_files()),
                "files_excluded": v.excluded_count,
            }
            for v in views
        ],
        "extractors": extractors,
        "sections": sections,
        "redaction": {
            "rules_version": "1",
            "values_masked": masked,
            "paths_excluded": excluded,
            "blocking_hits": blocking,
        },
        "limits": dict(limits),
        "tokens_total_est": sum(s["tokens_est"] for s in sections),
    }
    from tsl.schemas.registry import errors as schema_errors

    errs = schema_errors("context-pack.v1", manifest)
    if errs:
        raise TslError(
            "E-INT-01", f"manifest invalid: {errs[0].pointer} {errs[0].message}", log_id="context"
        )
    return {
        "manifest": manifest,
        "generated": gen_text,
        "lint": lint,
        "size": size_errs,
        "extract_errors": ex_errors,
        "jsections": jsections,
        "sources": sources,
        "warnings": warnings,
    }


def _require_engineer(rt: Runtime, comp: Companion) -> dict[str, Any]:
    memod.require_consent(rt, comp.config.system.code, ("code_processing",))
    return memod.require_grant(rt, {"engineer", "tech_lead"}, comp.config.system.code, "E-AUTH-03")


def build(
    rt: Runtime,
    comp: Companion,
    check: bool,
    commits: dict[str, str] | None,
    sections: list[str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, str]], str | None]:
    """Returns (data, warnings, failing code or None).

    `sections` (SDD-06 §6.1 --sections) limits lint findings to those judgement sections;
    the manifest always covers the whole pack.
    """
    for s in sections or []:
        if s not in JUDGEMENT:
            raise TslError("E-USE-01", detail=f"unknown section {s}", cmd="context build")
    me = _require_engineer(rt, comp)
    if not check:
        for sec in JUDGEMENT:
            p = comp.path(f"context/{sec}.md")
            if not p.exists():
                atomic_write(p, _template(sec, str(me.get("pseudonym", "tl-0000"))))
    r = compute(rt, comp, commits, fetch=True)
    if sections:
        wanted = tuple(f"context/{s}.md" for s in sections)
        r["lint"] = [x for x in r["lint"] if x.startswith(wanted)]
    warnings: list[dict[str, str]] = list(r["warnings"]) + list(r["extract_errors"])
    fs = fresh_status(rt, comp, fetch=False) if comp.path(SIGNATURE).is_file() else None
    sb = (fs or {}).get("state_block", {})
    drift = {
        "files": sum(sb.get("drift_files", {}).values()) if sb else 0,
        "commits_behind": sb.get("commits_behind", {}) if sb else {},
        "critical_changed": [x for x in (fs or {}).get("reasons", []) if x == "critical_change"],
        "over_limit": bool(fs and fs["state"] == "stale"),
    }
    generated = [
        {"path": f"context/generated/{s}.json", "sha256": sha256_text(t)}
        for s, t in sorted(r["generated"].items())
    ]
    data: dict[str, Any] = {
        "generated": generated,
        "source_shas": r["sources"],
        "drift": drift,
        "lint": r["lint"],
        "size": r["size"],
        "manifest_sha256": manifest_sha(r["manifest"]),
    }
    if check:
        cur = read_json(comp.path(MANIFEST)) if comp.path(MANIFEST).is_file() else None
        data["changed"] = cur != r["manifest"]
        emit(
            rt,
            "context.drift",
            {
                "system": comp.config.system.code,
                "age_days": 0,
                "drift_files": drift["files"],
                "status": "stale" if drift["over_limit"] else "fresh",
            },
            enabled=comp.config.telemetry_enabled,
        )
    else:
        for s, t in r["generated"].items():
            atomic_write(comp.path(f"context/generated/{s}.json"), t)
        write_json(comp.path(MANIFEST), r["manifest"])
    code = None
    if r["manifest"]["redaction"]["blocking_hits"]:
        code = "E-CTX-06"
    elif r["size"]:
        code = "E-CTX-05"
    elif r["lint"]:
        code = "E-CTX-07"
    elif r["extract_errors"]:
        code = "E-CTX-08"
    elif check and drift["over_limit"]:
        code = "E-CTX-02"
    return data, warnings, code


def sign(rt: Runtime, comp: Companion) -> dict[str, Any]:
    cfg = comp.config
    me = memod.require_grant(
        rt, {"tech_lead"}, cfg.system.code, "E-AUTH-04", action="sign the pack"
    )
    if not comp.path(MANIFEST).is_file():
        raise TslError("E-CTX-01", detail=": run tsl context build first")
    on_disk = read_json(comp.path(MANIFEST))
    commits = {s["repo"]: s["commit"] for s in on_disk.get("sources", [])}
    r = compute(rt, comp, commits, fetch=False)
    if r["manifest"] != on_disk:
        raise TslError("E-CTX-09", repo="(manifest differs from the files; run tsl context build)")
    for s in r["jsections"]:
        if s["status"] != "reviewed" or s["_drafts"]:
            raise TslError(
                "E-CTX-04", section=s["id"], detail="status drafted or draft markers left"
            )
        if not s["verified_at"]:
            raise TslError("E-CTX-04", section=s["id"], detail="verified_at missing")
    present = {s["id"] for s in r["manifest"]["sections"]}
    for sec in [*JUDGEMENT[:-1], *FACT_SECTIONS]:
        if sec not in present:
            raise TslError("E-CTX-01", detail=f" (required section {sec} missing)")
    if r["manifest"]["redaction"]["blocking_hits"]:
        hit = next(h for s in r["jsections"] for h in s["_hits"])
        raise TslError("E-CTX-06", path="context", line=hit[1], kind=hit[2])
    if r["size"]:
        raise TslError("E-CTX-05", detail=r["size"][0])
    if r["lint"]:
        raise TslError("E-CTX-07", n=len(r["lint"]), data={"lint": r["lint"]})
    signer = load_signer(rt)
    record = {
        "schema": "pack-signature.v1",
        "system": cfg.system.code,
        "manifest_sha256": manifest_sha(on_disk),
        "sources": commits,
        "signed_by": me["pseudonym"],
        "role": "tech_lead",
        "signed_at": iso(rt.clock()),
        "tsl": rt.tsl_version,
    }
    signed = sign_object(record, signer.key_id, signer.private)
    from tsl.schemas.registry import require_valid

    require_valid("pack-signature.v1", signed, SIGNATURE)
    write_json(comp.path(SIGNATURE), signed)
    try:
        comp.git.commit(f"tsl: sign context pack {signed['manifest_sha256'][:12]}", ["context"])
    except GitError as exc:
        raise exc.tsl() from None
    emit(
        rt,
        "context.signed",
        {
            "system": cfg.system.code,
            "age_days": 0,
            "drift_files": 0,
            "status": "fresh",
            "signature_sha256": sha256_file(comp.path(SIGNATURE)),
            "key_id": signer.key_id,
        },
        enabled=cfg.telemetry_enabled,
    )
    return {
        "signature_path": SIGNATURE,
        "signed_at": signed["signed_at"],
        "source_shas": commits,
        "files": len(on_disk["sections"]),
        "key_id": signer.key_id,
    }


def status_cmd(rt: Runtime, comp: Companion) -> tuple[dict[str, Any], list[dict[str, str]]]:
    fs = fresh_status(rt, comp)
    if fs["state"] == "missing":
        raise TslError("E-CTX-01", detail="")
    if fs["state"] == "invalid":
        raise TslError("E-CTX-03")
    warnings = []
    if fs["state"] == "stale":
        warnings.append(
            {
                "code": "E-CTX-02",
                "message": f"Context pack is stale ({', '.join(fs['reasons'])}). "
                "Band capped at Medium.",
            }
        )
    from tsl.context.freshness import behind_warnings

    warnings += behind_warnings(fs)
    sb = fs["state_block"]
    return {
        "state": fs["state"],
        "reasons": fs["reasons"],
        "signed_at": sb["signed_at"],
        "commits_behind": sb["commits_behind"],
        "drift_files": sb["drift_files"],
        "checked_offline": sb["checked_offline"],
    }, warnings


def deny_term(term: str) -> dict[str, Any]:
    """Hash line for deny_term_hashes; the name is never written (SDD-06 §9.4)."""
    return {"sha256": hashlib.sha256(term.strip().lower().encode("utf-8")).hexdigest()}


DRAFT_FACTS = {
    "system-baseline": ["module-map", "api-inventory"],
    "architecture": ["module-map", "dependency-graph", "api-inventory"],
    "data-model": ["db-schema"],
    "glossary": ["db-schema", "api-inventory"],
    "conventions": ["module-map", "test-layout"],
    "test-strategy": ["test-layout"],
    "intent-baseline": [],
}
MAX_DRAFT_FACT_IDS = 300


def draft_prepare(rt: Runtime, comp: Companion, section: str) -> dict[str, Any]:
    """Package for /truminds:context-draft (SDD-06 §6.4). Writes nothing."""
    if section not in JUDGEMENT:
        raise TslError("E-USE-01", detail=f"unknown section {section}", cmd="context draft-prepare")
    if not comp.path(MANIFEST).is_file():
        raise TslError("E-CTX-01", detail=": run tsl context build first")
    rel = f"context/{section}.md"
    p = comp.path(rel)
    me = memod.cached_me(rt) or {}
    current = (
        p.read_text(encoding="utf-8")
        if p.is_file()
        else _template(section, str(me.get("pseudonym", "tl-0000")))
    )
    facts: list[dict[str, Any]] = []
    for fs in DRAFT_FACTS[section]:
        gp = comp.path(f"context/generated/{fs}.json")
        if not gp.is_file():
            continue
        doc = read_json(gp)
        ids = [str(f["id"]) for f in doc.get("facts", [])]
        facts.append(
            {
                "file": f"context/generated/{fs}.json",
                "ids": ids[:MAX_DRAFT_FACT_IDS],
                "truncated": len(ids) > MAX_DRAFT_FACT_IDS,
                "empty_reason": doc.get("empty_reason"),
            }
        )
    repos = sorted(r.name for r in comp.config.product_repos)
    return {
        "section": section,
        "path": rel,
        "title": TITLES[section],
        "current": current,
        "facts": facts,
        "product_repos": repos,
        "budget_tokens": comp.config.pack_limits()["section_tokens"],
        "rules": {
            "front_matter": "keep schema, section and owner; set status: drafted, origin: ai-draft",
            "draft_marker": "<!-- tsl:draft id=D-<n> --> before every block you write",
            "anchors": "every heading ends with {#kebab-id}: lower-case a-z, 0-9 and '-', unique",
            "sources": "every fact block ends with 'Sources: <cite>, <cite>' using "
            "context/generated/<file>.json#<fact id> or <repo>:<path>#L<n>[-L<m>]",
            "unknown": "anything you cannot cite goes under '## Open points {#open-points}'",
            "never": "secrets, personal data, data values, client names",
        },
        "check_command": f"tsl context build --check --sections {section} --json",
    }
