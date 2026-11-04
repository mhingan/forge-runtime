"""Operating-system credential vault.

Secret values are never written to Forge manifests, project files, or logs.
The keyring backend must be an available OS-backed credential store.
"""
from __future__ import annotations

import re

SERVICE_NAME = "forge-runtime"
REFERENCE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_./:-]{0,190}$")


class CredentialVault:
    def __init__(self, service_name: str = SERVICE_NAME) -> None:
        self.service_name = service_name

    @staticmethod
    def _keyring():
        try:
            import keyring
        except ImportError as exc:
            raise RuntimeError('Install the credential support: pip install "forge-agent-runtime"') from exc
        backend = keyring.get_keyring()
        if getattr(backend, "priority", 0) <= 0:
            raise RuntimeError(
                "No secure operating-system keyring is available. Configure macOS Keychain, "
                "Windows Credential Manager, or a Linux Secret Service backend before storing secrets."
            )
        return keyring

    def set(self, reference: str, secret: str) -> None:
        if not REFERENCE_RE.fullmatch(reference):
            raise ValueError("Credential reference contains unsupported characters.")
        if not secret or "\n" in secret or "\r" in secret:
            raise ValueError("Secret must be non-empty and must not contain newlines.")
        self._keyring().set_password(self.service_name, reference, secret)

    def get(self, reference: str) -> str:
        if not REFERENCE_RE.fullmatch(reference):
            raise ValueError("Invalid credential reference.")
        value = self._keyring().get_password(self.service_name, reference)
        if value is None:
            raise KeyError(f"Credential is not stored: {reference}")
        return value

    def delete(self, reference: str) -> None:
        if not REFERENCE_RE.fullmatch(reference):
            raise ValueError("Invalid credential reference.")
        try:
            self._keyring().delete_password(self.service_name, reference)
        except Exception as exc:
            if type(exc).__name__ not in {"PasswordDeleteError", "KeyringError"}:
                raise

