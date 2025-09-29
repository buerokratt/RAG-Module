"""Vault-specific exceptions for LLM Config Module."""


class VaultError(Exception):
    """Base exception for Vault-related errors."""

    pass


class VaultConnectionError(VaultError):
    """Raised when unable to connect to Vault or authentication fails."""

    pass


class VaultSecretError(VaultError):
    """Raised when secret operations fail (not found, invalid format, etc.)."""

    pass


class VaultTokenError(VaultError):
    """Raised when Vault Agent token is missing or invalid."""

    pass


class SecretValidationError(VaultError):
    """Raised when secret data doesn't match expected schema."""

    pass
