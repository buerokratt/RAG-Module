"""Embedding vault module for chunk indexing."""

from vector_indexer.vault.vault_client import EmbeddingVaultClient
from vector_indexer.vault.secret_resolver import EmbeddingSecretResolver
from vector_indexer.vault.models import (
    AzureEmbeddingSecret,
    get_embedding_secret_model,
)
from vector_indexer.vault.exceptions import (
    EmbeddingVaultError,
    EmbeddingVaultConnectionError,
    EmbeddingVaultSecretError,
    EmbeddingVaultTokenError,
)

__all__ = [
    "EmbeddingVaultClient",
    "EmbeddingSecretResolver",
    "AzureEmbeddingSecret",
    "get_embedding_secret_model",
    "EmbeddingVaultError",
    "EmbeddingVaultConnectionError",
    "EmbeddingVaultSecretError",
    "EmbeddingVaultTokenError",
]
