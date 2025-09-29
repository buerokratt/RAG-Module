"""Exceptions for embedding vault operations."""


class EmbeddingVaultError(Exception):
    """Base exception for embedding vault operations."""

    pass


class EmbeddingVaultConnectionError(EmbeddingVaultError):
    """Raised when vault connection fails."""

    pass


class EmbeddingVaultSecretError(EmbeddingVaultError):
    """Raised when secret operations fail."""

    pass


class EmbeddingVaultTokenError(EmbeddingVaultError):
    """Raised when token operations fail."""

    pass
