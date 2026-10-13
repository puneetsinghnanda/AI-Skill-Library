"""Canonical JSON (RFC 8785 JCS) and Ed25519 signatures (SDD-07 §6.2, SDD-03 §12.2)."""

from __future__ import annotations

import base64
import math
import unicodedata
from typing import Any

import rfc8785
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

MAX_INT = 2**53 - 1


class NotSignable(ValueError):
    pass


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def check_signable(obj: Any, path: str = "") -> None:
    """Extra rules on top of JCS (SDD-07 §6.2)."""
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, int):
        if abs(obj) > MAX_INT:
            raise NotSignable(f"{path}: integer out of range")
        return
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            raise NotSignable(f"{path}: non-finite number")
        if round(obj, 4) != obj:
            raise NotSignable(f"{path}: float not rounded to 4 decimals")
        return
    if isinstance(obj, str):
        if unicodedata.normalize("NFC", obj) != obj:
            raise NotSignable(f"{path}: string is not NFC")
        return
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            check_signable(v, f"{path}/{i}")
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str):
                raise NotSignable(f"{path}: non-string key")
            check_signable(k, path)
            check_signable(v, f"{path}/{k}")
        return
    raise NotSignable(f"{path}: unsupported type {type(obj).__name__}")


def canonical(obj: Any) -> bytes:
    check_signable(obj)
    out: bytes = rfc8785.dumps(obj)
    return out


def round4(x: float) -> float:
    return round(float(x), 4)


def public_key_b64(priv: Ed25519PrivateKey) -> str:
    return b64url(priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))


def sign_object(obj: dict[str, Any], key_id: str, priv: Ed25519PrivateKey) -> dict[str, Any]:
    if "signature" in obj:
        raise NotSignable("already signed")
    body = {**obj, "key_id": key_id}
    sig = priv.sign(canonical(body))
    return {**body, "signature": b64url(sig)}


def signature_ok(obj: dict[str, Any], public_key: bytes) -> bool:
    """Verify over the stored content (never re-serialised after an upgrade)."""
    try:
        body = {k: v for k, v in obj.items() if k != "signature"}
        sig = b64url_decode(str(obj["signature"]))
        Ed25519PublicKey.from_public_bytes(public_key).verify(sig, canonical(body))
        return True
    except (InvalidSignature, NotSignable, ValueError, KeyError, TypeError):
        return False
