"""Embedding secret resolver with TTL caching."""

import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger

from vector_indexer.vault.vault_client import EmbeddingVaultClient
from vector_indexer.vault.models import get_embedding_secret_model
from vector_indexer.vault.exceptions import EmbeddingVaultConnectionError
from vector_indexer.vault.models import BaseEmbeddingSecret


@dataclass
class CachedEmbeddingSecret:
    """Cached embedding secret with TTL."""

    secret: BaseEmbeddingSecret
    expires_at: float
    last_accessed: float = field(default_factory=time.time)


class EmbeddingSecretResolver:
    """Resolves embedding secrets from Vault with TTL caching."""

    def __init__(
        self,
        vault_client: Optional[EmbeddingVaultClient] = None,
        ttl_minutes: int = 5,
    ):
        """Initialize the embedding secret resolver.

        Args:
            vault_client: Vault client instance. If None, creates default client.
            ttl_minutes: Time-to-live for cached secrets in minutes
        """
        self.vault_client = vault_client or EmbeddingVaultClient()
        self.ttl_seconds = ttl_minutes * 60
        self._cache: Dict[str, CachedEmbeddingSecret] = {}
        self._fallback_cache: Dict[str, Any] = {}

        logger.info(f"EmbeddingSecretResolver initialized with {ttl_minutes}min TTL")

    def get_secret_for_model(
        self,
        provider: str,
        environment: str,
        model_name: str,
        connection_id: Optional[str] = None,
    ) -> Optional[Any]:
        """Get embedding secret for a specific model.

        Args:
            provider: Provider name (e.g., "azure_openai")
            environment: Environment name (production/development/test)
            model_name: Model name (e.g., "text-embedding-3-large")
            connection_id: Connection ID for dev/test environments

        Returns:
            Validated secret object or None if not found
        """
        vault_path = self._build_vault_path(provider, environment, model_name)

        # Check cache first
        cached = self._get_cached_secret(vault_path)
        if cached:
            # For dev/test environments, validate connection_id
            if environment != "production" and connection_id:
                if (
                    hasattr(cached, "connection_id")
                    and cached.connection_id != connection_id
                ):
                    logger.debug(
                        f"Connection ID mismatch: cached={cached.connection_id}, requested={connection_id}"
                    )
                    return None

            logger.debug(f"Using cached embedding secret for {provider}/{model_name}")
            return cached

        try:
            # Fetch from Vault
            secret_data = self.vault_client.get_secret(vault_path)
            if not secret_data:
                logger.debug(f"Embedding secret not found in Vault: {vault_path}")
                return self._get_fallback(vault_path)

            # Validate and parse secret
            secret_model = get_embedding_secret_model(provider)
            validated_secret = secret_model(**secret_data)

            # For dev/test environments, validate connection_id
            if environment != "production" and connection_id:
                if validated_secret.connection_id != connection_id:
                    logger.debug(
                        f"Connection ID mismatch: vault={validated_secret.connection_id}, "
                        f"requested={connection_id}"
                    )
                    return None

            # Cache the secret
            self._cache_secret(vault_path, validated_secret)

            # Update fallback cache
            self._fallback_cache[vault_path] = validated_secret

            logger.debug(
                f"Successfully resolved embedding secret for {provider}/{model_name}"
            )
            return validated_secret

        except EmbeddingVaultConnectionError:
            logger.warning(
                f"Embedding vault unavailable, trying fallback for {vault_path}"
            )
            return self._get_fallback(vault_path)
        except Exception as e:
            logger.error(f"Error resolving embedding secret for {vault_path}: {e}")
            return self._get_fallback(vault_path)

    def list_available_models(self, provider: str, environment: str) -> List[str]:
        """List available embedding models for a provider and environment.

        Args:
            provider: Provider name (e.g., "azure_openai")
            environment: Environment name

        Returns:
            List of available model names
        """
        if environment == "production":
            # For production: Check provider/production path for available models
            production_path = f"embeddings/connections/{provider}/{environment}"
            try:
                models = self.vault_client.list_secrets(production_path)
                if models:
                    logger.debug(
                        f"Found {len(models)} production embedding models for {provider}: {models}"
                    )
                    return models
                else:
                    logger.debug(f"No production embedding models found for {provider}")
                    return []

            except Exception as e:
                logger.debug(
                    f"Embedding provider {provider} not available in production: {e}"
                )
                return []
        else:
            # For dev/test: Use existing logic with connection_id paths
            # This would need to be implemented based on specific requirements
            logger.debug(
                f"Dev/test embedding model listing not implemented for {provider}"
            )
            return []

    def get_first_available_model(
        self,
        provider: str,
        environment: str,
        connection_id: Optional[str] = None,
    ) -> Optional[Any]:
        """Get the first available embedding model for a provider.

        Args:
            provider: Provider name
            environment: Environment name
            connection_id: Connection ID for dev/test environments

        Returns:
            First available secret or None
        """
        available_models = self.list_available_models(provider, environment)

        if not available_models:
            return None

        # Try each model until we find one that works
        for model_name in available_models:
            secret = self.get_secret_for_model(
                provider, environment, model_name, connection_id
            )
            if secret:
                logger.info(
                    f"Using embedding model {model_name} for provider {provider}"
                )
                return secret

        return None

    def _build_vault_path(
        self, provider: str, environment: str, model_name: str
    ) -> str:
        """Build vault path for embedding secret.

        Args:
            provider: Provider name
            environment: Environment name
            model_name: Model name

        Returns:
            Vault path string
        """
        return f"embeddings/connections/{provider}/{environment}/{model_name}"

    def _get_cached_secret(self, vault_path: str) -> Optional[Any]:
        """Get secret from cache if not expired.

        Args:
            vault_path: Vault path for the secret

        Returns:
            Cached secret or None if not found/expired
        """
        if vault_path not in self._cache:
            return None

        cached = self._cache[vault_path]
        current_time = time.time()

        # Check if expired
        if current_time > cached.expires_at:
            logger.debug(f"Embedding cache expired for {vault_path}")
            del self._cache[vault_path]
            return None

        # Update last accessed time
        cached.last_accessed = current_time
        return cached.secret

    def _cache_secret(self, vault_path: str, secret: Any) -> None:
        """Cache a secret with TTL.

        Args:
            vault_path: Vault path for the secret
            secret: Secret to cache
        """
        expires_at = time.time() + self.ttl_seconds
        self._cache[vault_path] = CachedEmbeddingSecret(
            secret=secret, expires_at=expires_at
        )

        expiry_time = datetime.fromtimestamp(expires_at)
        logger.debug(f"Cached embedding secret {vault_path} until {expiry_time}")

    def _get_fallback(self, vault_path: str) -> Optional[Any]:
        """Get secret from fallback cache.

        Args:
            vault_path: Vault path for the secret

        Returns:
            Fallback secret or None
        """
        if vault_path in self._fallback_cache:
            logger.info(f"Using fallback embedding secret for {vault_path}")
            return self._fallback_cache[vault_path]
        return None

    def clear_cache(self) -> None:
        """Clear all cached secrets."""
        self._cache.clear()
        logger.info("Embedding secret cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        current_time = time.time()
        active_count = sum(
            1 for cached in self._cache.values() if current_time <= cached.expires_at
        )

        return {
            "total_cached": len(self._cache),
            "active_cached": active_count,
            "fallback_cached": len(self._fallback_cache),
            "ttl_seconds": self.ttl_seconds,
        }
