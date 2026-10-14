"""Portal sign-in with GitHub, backend-for-frontend (ADR 0006, SDD-09 §3.4.1).

``GET /auth/github/login`` -> GitHub authorize (``state`` + PKCE S256) ->
``GET /auth/github/callback`` (state checked, code exchanged server-side with the client secret,
token stored encrypted in the signed session cookie) -> redirect to the portal.
``POST /auth/logout`` clears the cookie.

These routes exist only while ``IDENTITY_PROVIDER=github``; with ``entra`` they answer 404. They are
in the OpenAPI file and in registry §4 like every other route.
"""

from __future__ import annotations

import hmac
import secrets

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import RedirectResponse

from app.auth.entra import TokenInvalid
from app.auth.github import GitHubUnavailable, GitHubValidator, GitHubWebFlow, pkce_pair
from app.auth.session import require_csrf, session_of, session_token, store_token
from app.config import Settings
from app.errors import ServiceError
from app.obs import metrics

router = APIRouter(tags=["identity"])


def _github_only(request: Request) -> Settings:
    s: Settings = request.app.state.settings
    if s.identity_provider != "github" or session_of(request) is None:
        raise ServiceError("E-API-04", "Not found")
    return s


def safe_return(path: str | None) -> str:
    """Only a same-origin portal path (no open redirect)."""
    if not path or not path.startswith("/") or path.startswith("//") or "\\" in path:
        return "/"
    if path.startswith(("/auth/", "/v1/", "/otel/")):
        return "/"
    return path


@router.get(
    "/auth/github/login",
    summary="Portal sign-in with GitHub: redirect to GitHub (IDENTITY_PROVIDER=github only)",
    status_code=302,
    response_class=RedirectResponse,
)
def github_login(
    request: Request, return_to: str | None = Query(default=None, max_length=500)
) -> RedirectResponse:
    _github_only(request)
    flow: GitHubWebFlow = request.app.state.github_flow
    state = secrets.token_urlsafe(32)
    verifier, challenge = pkce_pair()
    sess = request.session
    sess.pop("gh", None)
    sess["st"] = state
    sess["pv"] = verifier
    sess["rt"] = safe_return(return_to)
    return RedirectResponse(flow.authorize_url(state, challenge), status_code=302)


@router.get(
    "/auth/github/callback",
    summary="GitHub OAuth callback: check state, exchange the code, set the session cookie",
    status_code=302,
    response_class=RedirectResponse,
)
def github_callback(
    request: Request,
    code: str | None = Query(default=None, max_length=200),
    state: str | None = Query(default=None, max_length=200),
    error: str | None = Query(default=None, max_length=100),
) -> RedirectResponse:
    s = _github_only(request)
    sess = request.session
    expected = str(sess.pop("st", "") or "")
    verifier = str(sess.pop("pv", "") or "")
    back = safe_return(str(sess.pop("rt", "/") or "/"))
    if not expected or not state or not hmac.compare_digest(expected, state):
        metrics.AUTH_FAILURES.labels(kind="github", reason="state").inc()
        raise ServiceError("E-AUTH-09", "Sign-in state does not match; start again from the portal")
    if error or not code:
        metrics.AUTH_FAILURES.labels(kind="github", reason=error or "no_code").inc()
        raise ServiceError("E-AUTH-09", f"GitHub did not return a code ({error or 'none'})")
    flow: GitHubWebFlow = request.app.state.github_flow
    try:
        token = flow.exchange(code, verifier)
    except TokenInvalid as exc:
        metrics.AUTH_FAILURES.labels(kind="github", reason="exchange").inc()
        raise ServiceError("E-AUTH-09", f"Code exchange failed ({exc})") from None
    except GitHubUnavailable:
        raise ServiceError("E-AUTH-10", "GitHub could not be reached; try again") from None
    store_token(request, s, token)
    return RedirectResponse(back, status_code=302)


@router.post(
    "/auth/logout",
    summary="Portal sign-out: clear the session cookie (IDENTITY_PROVIDER=github only)",
    status_code=204,
    response_class=Response,
)
def logout(request: Request) -> Response:
    s = _github_only(request)
    token = session_token(request, s)
    if token is not None:
        require_csrf(request, s)
        validator: GitHubValidator = request.app.state.github
        validator.forget(token)
    request.session.clear()
    return Response(status_code=204)
