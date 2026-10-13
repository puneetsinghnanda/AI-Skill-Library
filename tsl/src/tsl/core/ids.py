"""ULID ids: run_, evt_, key_, dev_, imp_ (Doc 5 §1.1). Crockford base32, 26 chars."""

from __future__ import annotations

import random
import secrets
from datetime import datetime

from tsl.core.clock import Clock

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def encode_ulid(ms: int, rand80: int) -> str:
    value = (ms << 80) | rand80
    out = []
    for _ in range(26):
        out.append(ALPHABET[value & 31])
        value >>= 5
    return "".join(reversed(out))


class IdFactory:
    """Makes ULIDs. A seeded factory gives a fixed sequence (golden tests, SDD-04 §12)."""

    def __init__(self, clock: Clock, seed: int | None = None) -> None:
        self._clock = clock
        self._rng: random.Random | None = (
            random.Random(seed) if seed is not None else None  # noqa: S311 - test ids only
        )

    def _rand(self) -> int:
        if self._rng is not None:
            return self._rng.getrandbits(80)
        return secrets.randbits(80)

    def ulid(self, at: datetime | None = None) -> str:
        t = at or self._clock()
        return encode_ulid(int(t.timestamp() * 1000), self._rand())

    def new(self, prefix: str) -> str:
        return f"{prefix}_{self.ulid()}"
