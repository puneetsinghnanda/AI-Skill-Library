"""Portal session cookie for GitHub sign-in (ADR 0006, SDD-09 §3.4.1).

Starlette's ``SessionMiddleware`` signs the cookie (itsdangerous); the GitHub token inside it is
also encrypted with AES-256-GCM under the service data key (``app.crypto``), so the browser holds
only ciphertext. Cookie flags: HttpOnly (always, Starlette), SameSite=Lax, Secure when
PUBLIC_BASE_URL is https. The signing key is derived from the data key with HKDF, so there is no
extra secret to manage.

A state-changing request authenticated by the cookie must carry ``X-Requested-With:
truminds-portal`` and an ``Origin`` equal to the origin of PUBLIC_BASE_URL (E-API-07).
"""

from __future__ import annotations

import base64
from typing import Any
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from fastapi import Request

from app.config import Settings
from app.crypto import decrypt, encrypt
from app.errors import ServiceError

COOKIE = "tm_session"
CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "truminds-portal"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def signing_key(s: Settings) -> str:
    raw = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None, info=b"truminds-session-cookie-v1"
    ).derive(s.data_key())
    return base64.urlsafe_b64encode(raw).decode("ascii")


def origin_of(url: str) -> str:
    u = urlsplit(url)
    return f"{u.scheme}://{u.netloc}".lower()


def cookie_secure(s: Settings) -> bool:
    return urlsplit(s.public_base_url).scheme == "https"


def is_local(s: Settings) -> bool:
    return (urlsplit(s.public_base_url).hostname or "") in ("localhost", "127.0.0.1", "::1")


def session_of(request: Request) -> dict[str, Any] | None:
    """The session dict, or None when the middleware is not installed (provider entra)."""
    if "session" not in request.scope:
        return None
    sess: dict[str, Any] = request.session
    return sess


def store_token(request: Request, s: Settings, token: str) -> None:
    sess = session_of(request)
    if sess is None:
        raise RuntimeError("session middleware is not installed")
    blob, key_id = encrypt(s, token)
    sess.clear()
    sess["gh"] = base64.urlsafe_b64encode(blob).decode("ascii")
    sess["kid"] = key_id


def session_token(request: Request, s: Settings) -> str | None:
    sess = session_of(request)
    if not sess or "gh" not in sess:
        return None
    try:
        return decrypt(s, base64.urlsafe_b64decode(str(sess["gh"])), str(sess.get("kid") or ""))
    except Exception:  # tampered, or data key rotated: treat as signed out
        sess.clear()
        return None


def require_csrf(request: Request, s: Settings, code: str = "E-API-07") -> None:
    """Cookie-authenticated writes: custom header plus same-origin ``Origin`` (SDD-07 §1.4)."""
    if request.method in SAFE_METHODS:
        return
    if request.headers.get(CSRF_HEADER, "") != CSRF_VALUE:
        raise ServiceError(code, "Cookie writes need the header X-Requested-With: truminds-portal")
    origin = (request.headers.get("origin") or "").lower()
    if origin != origin_of(s.public_base_url):
        raise ServiceError(code, "Cookie writes need an Origin header equal to the portal origin")
