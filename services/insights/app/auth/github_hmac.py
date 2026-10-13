"""``X-Hub-Signature-256`` check for GitHub webhooks (SDD-08 §6.1 step 1)."""

from __future__ import annotations

import hashlib
import hmac


def signature(secret: bytes, body: bytes) -> str:
    return "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()


def verify(secret: bytes, body: bytes, header: str | None) -> bool:
    if not header or not header.startswith("sha256="):
        return False
    return hmac.compare_digest(signature(secret, body), header)
