"""Print the OpenAPI document: ``python -m app.openapi_dump > openapi/openapi.json`` (SDD-08 §11.1 "
"CI diff)."""

from __future__ import annotations

import json
import sys

from app.config import Settings
from app.main import create_app


def main() -> None:
    spec = create_app(Settings(entra_tenant_id="00000000-0000-0000-0000-000000000000")).openapi()
    sys.stdout.write(json.dumps(spec, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
