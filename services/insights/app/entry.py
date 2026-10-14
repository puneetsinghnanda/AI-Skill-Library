"""Container entrypoint dispatcher (OPS-01 §5.2): ``api | worker | migrate | admin | probe``, plus
``allinone`` for the hosted test environment (``app.hosted``, deploy/render).

It accepts no other mode, so the image has no hidden mode.
"""

from __future__ import annotations

import os
import sys
import tempfile
import urllib.request

from app.config import SERVICE_DIR, get_settings

USAGE = "usage: python -m app.entry api|worker|migrate|allinone|admin ...|probe ready|live"


def _api() -> int:
    import uvicorn

    s = get_settings()
    os.environ.setdefault("PROMETHEUS_MULTIPROC_DIR", tempfile.mkdtemp(prefix="prom-"))
    import threading

    from app.obs.metrics import metrics_app

    cfg = uvicorn.Config(
        metrics_app(),
        host="0.0.0.0",  # noqa: S104 - internal metrics port, never routed by the edge
        port=s.metrics_port,
        log_level="warning",
    )
    threading.Thread(target=uvicorn.Server(cfg).run, daemon=True).start()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",  # noqa: S104 - container port behind the edge proxy
        port=8000,
        workers=2,
        proxy_headers=True,
        forwarded_allow_ips="*",
        log_config=None,
    )
    return 0


def _migrate() -> int:
    from alembic.config import Config

    from alembic import command

    cfg = Config(str(SERVICE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(SERVICE_DIR / "alembic"))
    command.upgrade(cfg, "head")
    from app.jobs import partitions

    partitions.run(
        get_settings(), role="owner"
    )  # the api cannot store events before the first partition exists
    return 0


def _probe(kind: str) -> int:
    path = "/v1/health/ready" if kind == "ready" else "/v1/health"
    try:
        port = os.environ.get("PORT") or "8000"  # PORT: the hosted test environment (allinone)
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=3) as r:
            return 0 if r.status == 200 else 1
    except OSError:
        return 1


def main(argv: list[str]) -> int:
    if not argv:
        print(USAGE, file=sys.stderr)
        return 2
    mode, rest = argv[0], argv[1:]
    if mode == "api" and not rest:
        return _api()
    if mode == "worker" and not rest:
        from app.worker import main as worker_main

        worker_main()
        return 0
    if mode == "migrate" and not rest:
        return _migrate()
    if mode == "allinone" and not rest:
        from app.hosted import main as hosted_main

        return hosted_main()
    if mode == "admin":
        from app.admin import main as admin_main

        return admin_main(rest)
    if mode == "probe" and rest in (["ready"], ["live"]):
        return _probe(rest[0])
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
