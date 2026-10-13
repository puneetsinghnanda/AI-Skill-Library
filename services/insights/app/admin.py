"""``python -m app.admin``: platform-operator commands inside the deployed container (SDD-08 §9.3).

There is no HTTP endpoint for any of these. Each prints JSON. Token values are printed once.

  token create --kind otel|ci --label TEXT
  token revoke ID
  hook create --hook-id N --target ORG[/REPO]     (secret read from stdin; stored encrypted)
  hook revoke --hook-id N
  catalogue sync --path DIR --tag vX.Y.Z --commit SHA
  report run                                     (improvement report now)
  views refresh | partitions ensure | retention run
  user erase PSEUDONYM                           (DPDP / GDPR erasure, SDD-08 §8.1)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.auth import ingest_tokens
from app.auth.users import SVC_ENTRA_SYNC_ID, audit
from app.config import Settings, get_settings
from app.crypto import encrypt
from app.db import tx


def _out(obj: Any) -> None:
    print(json.dumps(obj, default=str))


def main(argv: list[str] | None = None, settings: Settings | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.admin")
    sub = ap.add_subparsers(dest="area", required=True)
    tok = sub.add_parser("token").add_subparsers(dest="op", required=True)
    tc = tok.add_parser("create")
    tc.add_argument("--kind", choices=["otel", "ci"], required=True)
    tc.add_argument("--label", required=True)
    tr = tok.add_parser("revoke")
    tr.add_argument("id")
    hook = sub.add_parser("hook").add_subparsers(dest="op", required=True)
    hc = hook.add_parser("create")
    hc.add_argument("--hook-id", type=int, required=True)
    hc.add_argument("--target", required=True)
    hr = hook.add_parser("revoke")
    hr.add_argument("--hook-id", type=int, required=True)
    cat = sub.add_parser("catalogue").add_subparsers(dest="op", required=True)
    cs = cat.add_parser("sync")
    cs.add_argument("--path", type=Path, required=True)
    cs.add_argument("--tag", required=True)
    cs.add_argument("--commit", required=True)
    sub.add_parser("report").add_subparsers(dest="op", required=True).add_parser("run")
    sub.add_parser("views").add_subparsers(dest="op", required=True).add_parser("refresh")
    sub.add_parser("partitions").add_subparsers(dest="op", required=True).add_parser("ensure")
    sub.add_parser("retention").add_subparsers(dest="op", required=True).add_parser("run")
    ue = sub.add_parser("user").add_subparsers(dest="op", required=True).add_parser("erase")
    ue.add_argument("pseudonym")
    a = ap.parse_args(argv)
    s = settings or get_settings()

    if a.area == "token" and a.op == "create":
        with tx("app", s) as conn:
            tid, value = ingest_tokens.create(conn, a.kind, a.label)
            audit(
                conn,
                SVC_ENTRA_SYNC_ID,
                "token_create",
                "ingest_token",
                tid,
                after={"kind": a.kind, "label": a.label},
            )
        _out(
            {
                "id": tid,
                "kind": a.kind,
                "token": value,
                "note": "shown once; store it in the secret store now",
            }
        )
    elif a.area == "token":
        with tx("app", s) as conn:
            ok = ingest_tokens.revoke(conn, a.id)
            if ok:
                audit(conn, SVC_ENTRA_SYNC_ID, "token_revoke", "ingest_token", a.id)
        _out({"id": a.id, "revoked": ok})
    elif a.area == "hook" and a.op == "create":
        secret = sys.stdin.readline().strip()
        if len(secret) < 20:
            print("hook secret on stdin must be at least 20 characters", file=sys.stderr)
            return 2
        enc, key_id = encrypt(s, secret)
        with tx("app", s) as conn:
            conn.execute(
                text(
                    "INSERT INTO github_hooks (hook_id, target, secret_enc, enc_key_id) VALUES "
                    "(:h, "
                    ""
                    ":t, :s, :k)"
                ),
                {"h": a.hook_id, "t": a.target, "s": enc, "k": key_id},
            )
        _out({"hook_id": a.hook_id, "target": a.target})
    elif a.area == "hook":
        with tx("app", s) as conn:
            n = conn.execute(
                text(
                    "UPDATE github_hooks SET revoked_at = now() WHERE hook_id = :h AND "
                    "revoked_at "
                    "IS NULL"
                ),
                {"h": a.hook_id},
            ).rowcount
        _out({"hook_id": a.hook_id, "revoked": bool(n)})
    elif a.area == "catalogue":
        from app.catalogue.sync import sync

        r = sync(s, a.path, a.tag, a.commit)
        _out(r.__dict__)
    elif a.area == "report":
        from app.jobs import improvement_report

        _out(improvement_report.run(s))
    elif a.area == "views":
        from app.jobs import refresh_views

        _out(refresh_views.run(s))
    elif a.area == "partitions":
        from app.jobs import partitions

        _out({"created": partitions.run(s)})
    elif a.area == "retention":
        from app.jobs import retention

        _out(retention.run(s))
    elif a.area == "user":
        with tx("app", s) as conn:
            uid = conn.execute(
                text(
                    "UPDATE users SET display_name_enc = NULL, email_enc = NULL, email_hmac = "
                    "NULL, "
                    ""
                    "erased_at = now() "
                    "WHERE pseudonym = :p RETURNING id::text"
                ),
                {"p": a.pseudonym},
            ).scalar()
            if uid:
                audit(conn, SVC_ENTRA_SYNC_ID, "erase_user", "user", a.pseudonym)
        _out({"pseudonym": a.pseudonym, "erased": bool(uid)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
