"""Service error codes (registry §2) and the problem+json error (RFC 9457, SDD-09 §5.1.4)."""

from __future__ import annotations

from typing import Any

TITLES: dict[str, tuple[int, str]] = {
    # Read API (SDD-09 §5.1.4)
    "E-API-01": (400, "Invalid parameter"),
    "E-API-02": (401, "Not authenticated"),
    "E-API-03": (403, "Not allowed"),
    "E-API-04": (404, "Not found"),
    "E-API-05": (429, "Rate limited"),
    "E-API-06": (503, "Service unavailable"),
    # Ingest (SDD-08 §4.3); E-ING-01..05 are per event inside a 202
    "E-ING-01": (422, "Schema invalid"),
    "E-ING-02": (422, "Unknown schema version"),
    "E-ING-03": (422, "Forbidden field"),
    "E-ING-04": (422, "Deny-list"),
    "E-ING-05": (403, "Token kind not allowed"),
    "E-ING-06": (400, "Malformed batch"),
    "E-ING-07": (401, "Token invalid"),
    # Identity (SDD-07 §12)
    "E-AUTH-08": (403, "No Truminds app role, or account deactivated"),
    "E-KEY-02": (400, "Key proof does not verify, or iat too old"),
    "E-KEY-03": (409, "Key id already registered with another public key"),
    "E-KEY-04": (404, "Key not found, or not yours"),
    "E-KEY-06": (422, "compromised_since out of range"),
    # Admin (SDD-13 §10)
    "E-ADM-01": (403, "An admin cannot grant a role to themselves"),
}

INGEST_CODES = ("E-ING-01", "E-ING-02", "E-ING-03", "E-ING-04", "E-ING-05")


class ServiceError(Exception):
    def __init__(
        self,
        code: str,
        detail: str | None = None,
        status: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        st, title = TITLES[code]
        self.code = code
        self.status = status or st
        self.title = title
        self.detail = detail or title
        self.headers = headers or {}
        super().__init__(f"{code}: {self.detail}")

    def problem(self, request_id: str, base_url: str) -> dict[str, Any]:
        return {
            "type": f"{base_url.rstrip('/')}/errors/{self.code}",
            "title": self.title,
            "status": self.status,
            "code": self.code,
            "detail": self.detail,
            "request_id": request_id,
        }
