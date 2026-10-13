"""SHA-256 over LF-normalised bytes (Doc 5 §1.1)."""

from __future__ import annotations

import hashlib
from pathlib import Path


def normalise(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(normalise(data)).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha256_raw(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
