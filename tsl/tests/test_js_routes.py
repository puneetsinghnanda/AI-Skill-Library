"""SDD-06 api-inventory: js-routes resolves mount prefixes for default and named imports."""

from __future__ import annotations

from dataclasses import dataclass, field

from tsl.context.extractors import JsRoutes


@dataclass
class FakeView:
    files: dict[str, str]
    repo: str = "product"
    commit: str = "0" * 40
    scope: str = ""
    extra_exclude: list[str] = field(default_factory=list)

    def list_files(self, pattern: str = "**") -> list[str]:
        return list(self.files)

    def read_text(self, path: str, max_bytes: int = 0) -> str | None:
        return self.files.get(path)


ROUTER = (
    "import { Router } from 'express';\nexport const ordersRouter = Router();\n"
    "ordersRouter.get('/', list);\nordersRouter.post(\n  '/',\n  create,\n);\n"
)


def _ids(files: dict[str, str]) -> set[str]:
    return {f["id"] for f in JsRoutes().extract(FakeView(files)).facts}  # type: ignore[arg-type]


def test_named_import_mount_prefix() -> None:
    app = (
        "import express from 'express';\n"
        "import { ordersRouter } from './routes/orders';\n"
        "import { hRouter as healthRouter, other } from './routes/health';\n"
        "const app = express();\napp.use('/api/orders', ordersRouter);\n"
        "app.use('/api', healthRouter);\n"
    )
    health = "export const hRouter = Router();\nhRouter.get('/health', h);\n"
    ids = _ids({"src/app.ts": app, "src/routes/orders.ts": ROUTER, "src/routes/health.ts": health})
    assert {"http:GET:/api/orders", "http:POST:/api/orders", "http:GET:/api/health"} <= ids


def test_default_import_and_require_still_resolve() -> None:
    app = (
        "import ordersRouter from './routes/orders';\n"
        "const x = require('./routes/x');\napp.use('/api/orders', ordersRouter);\n"
        "app.use('/x', x);\n"
    )
    ids = _ids(
        {
            "src/app.js": app,
            "src/routes/orders.js": ROUTER,
            "src/routes/x.js": "router.get('/y', h);\n",
        }
    )
    assert {"http:POST:/api/orders", "http:GET:/x/y"} <= ids
