"""Column encryption, pseudonyms and ids (SDD-08 §8.1, §9.2).

AES-256-GCM with the data key from the secret store; the key id is stored next to every value so
keys can rotate. No custom cryptography: ``cryptography`` primitives only.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import Settings

NONCE = 12
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def encrypt(settings: Settings, plaintext: str) -> tuple[bytes, str]:
    nonce = os.urandom(NONCE)
    ct = AESGCM(settings.data_key()).encrypt(nonce, plaintext.encode("utf-8"), None)
    return nonce + ct, settings.data_key_id


def decrypt(settings: Settings, blob: bytes, key_id: str | None) -> str:
    if key_id and key_id != settings.data_key_id:
        raise ValueError(f"unknown data key id {key_id}")
    data = bytes(blob)
    return AESGCM(settings.data_key()).decrypt(data[:NONCE], data[NONCE:], None).decode("utf-8")


def email_hmac(settings: Settings, email: str) -> bytes:
    return hmac.new(settings.pepper(), email.strip().lower().encode(), hashlib.sha256).digest()


def pseudonym_candidates(settings: Settings, tenant_id: str, oid: str) -> list[str]:
    """``eng-`` + first 4, then 6, then 8 hex of HMAC-SHA256(pepper, tid:oid) (SDD-08 §8.1)."""
    digest = hmac.new(settings.pepper(), f"{tenant_id}:{oid}".encode(), hashlib.sha256).hexdigest()
    return [f"eng-{digest[:n]}" for n in (4, 6, 8)]


def ulid(prefix: str) -> str:
    """``<prefix>_<ULID>`` (Doc 5 §1.1)."""
    ms = int(time.time() * 1000)
    rand = int.from_bytes(secrets.token_bytes(10), "big")
    value = (ms << 80) | rand
    chars = []
    for _ in range(26):
        chars.append(_CROCKFORD[value & 31])
        value >>= 5
    return f"{prefix}_{''.join(reversed(chars))}"


def sha256_bytes(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()
