"""Insights service client interface (SDD-08 endpoints, registry §4).

Production uses HttpInsightsClient (httpx). Tests inject a fake; no test
touches the network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class InsightsUnavailable(Exception):
    """Network error, timeout or 5xx after the client's own retry."""


@dataclass
class HttpResult:
    status: int
    body: Any
    headers: dict[str, str] = field(default_factory=dict)


class InsightsClient(Protocol):
    def health(self) -> bool: ...
    def get_me(self, token: str) -> HttpResult: ...
    def register_key(self, token: str, body: dict[str, Any]) -> HttpResult: ...
    def revoke_key(self, token: str, key_id: str, body: dict[str, Any]) -> HttpResult: ...
    def my_keys(self, token: str) -> HttpResult: ...
    def get_key(self, token: str, key_id: str) -> HttpResult: ...
    def verify_signatures(self, token: str, body: dict[str, Any]) -> HttpResult: ...
    def get_system(self, token: str, code: str) -> HttpResult: ...
    def improvement_report(self, token: str, skill: str) -> HttpResult: ...
    def post_events(self, token: str, events: list[dict[str, Any]]) -> HttpResult: ...


class HttpInsightsClient:
    def __init__(self, base_url: str, timeout_s: float = 5.0) -> None:
        self.base = base_url.rstrip("/")
        self.timeout = timeout_s

    def _req(
        self, method: str, path: str, token: str | None = None, json_body: Any = None
    ) -> HttpResult:
        import httpx

        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            r = httpx.request(
                method, self.base + path, headers=headers, json=json_body, timeout=self.timeout
            )
        except httpx.HTTPError as exc:
            raise InsightsUnavailable(type(exc).__name__) from exc
        try:
            body: Any = r.json()
        except ValueError:
            body = None
        return HttpResult(r.status_code, body, dict(r.headers))

    def health(self) -> bool:
        try:
            return self._req("GET", "/v1/health").status == 200
        except InsightsUnavailable:
            return False

    def get_me(self, token: str) -> HttpResult:
        return self._req("GET", "/v1/me", token)

    def register_key(self, token: str, body: dict[str, Any]) -> HttpResult:
        return self._req("POST", "/v1/keys", token, body)

    def revoke_key(self, token: str, key_id: str, body: dict[str, Any]) -> HttpResult:
        return self._req("POST", f"/v1/keys/{key_id}/revoke", token, body)

    def my_keys(self, token: str) -> HttpResult:
        return self._req("GET", "/v1/me/keys", token)

    def get_key(self, token: str, key_id: str) -> HttpResult:
        return self._req("GET", f"/v1/keys/{key_id}", token)

    def verify_signatures(self, token: str, body: dict[str, Any]) -> HttpResult:
        return self._req("POST", "/v1/signatures/verify", token, body)

    def get_system(self, token: str, code: str) -> HttpResult:
        return self._req("GET", f"/v1/systems/{code}", token)

    def improvement_report(self, token: str, skill: str) -> HttpResult:
        return self._req("GET", f"/v1/improvement/skills/{skill}", token)

    def post_events(self, token: str, events: list[dict[str, Any]]) -> HttpResult:
        return self._req("POST", "/v1/events", token, {"events": events})
