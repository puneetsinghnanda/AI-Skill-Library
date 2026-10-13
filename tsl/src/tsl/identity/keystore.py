"""OS keychain access through keyring, allowed backends only (SDD-07 §4.3)."""

from __future__ import annotations

import contextlib
import sys
from typing import Protocol

from tsl.core.errors import TslError

SERVICE = "truminds-tsl"

ALLOWED_BACKENDS = {
    "darwin": "keyring.backends.macOS.Keyring",
    "win32": "keyring.backends.Windows.WinVaultKeyring",
    "linux": "keyring.backends.SecretService.Keyring",
}


class KeyStore(Protocol):
    def get(self, name: str) -> str | None: ...
    def set(self, name: str, value: str) -> None: ...
    def delete(self, name: str) -> None: ...


class KeyringKeyStore:
    """Production key store. tsl picks the backend itself; PYTHON_KEYRING_BACKEND and
    keyringrc.cfg have no effect. Any other backend gives E-KEY-01 (no file fallback)."""

    def __init__(self) -> None:
        self._backend: object | None = None

    def _kr(self) -> object:
        if self._backend is not None:
            return self._backend
        import importlib

        import keyring

        path = ALLOWED_BACKENDS.get(sys.platform)
        if path is None:
            raise TslError("E-KEY-01")
        mod_name, cls_name = path.rsplit(".", 1)
        try:
            cls = getattr(importlib.import_module(mod_name), cls_name)
            backend = cls()
            if getattr(backend, "priority", 0) <= 0:
                raise RuntimeError("backend not usable")
            keyring.set_keyring(backend)
        except Exception as exc:  # backend missing or no running Secret Service
            raise TslError("E-KEY-01") from exc
        self._backend = backend
        return backend

    def get(self, name: str) -> str | None:
        b = self._kr()
        try:
            value = b.get_password(SERVICE, name)  # type: ignore[attr-defined]
        except Exception as exc:
            raise TslError("E-KEY-01") from exc
        return None if value is None else str(value)

    def set(self, name: str, value: str) -> None:
        b = self._kr()
        try:
            b.set_password(SERVICE, name, value)  # type: ignore[attr-defined]
        except Exception as exc:
            raise TslError("E-KEY-01") from exc

    def delete(self, name: str) -> None:
        b = self._kr()
        with contextlib.suppress(Exception):  # deleting an absent item is fine
            b.delete_password(SERVICE, name)  # type: ignore[attr-defined]


class MemoryKeyStore:
    """In-memory store for tests (SDD-04 §12, SDD-07 §11). Never used by the CLI."""

    def __init__(self) -> None:
        self.items: dict[str, str] = {}

    def get(self, name: str) -> str | None:
        return self.items.get(name)

    def set(self, name: str, value: str) -> None:
        self.items[name] = value

    def delete(self, name: str) -> None:
        self.items.pop(name, None)
