"""Secret resolver with TTL cache and background refresh for LLM Config Module."""

import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass
from loguru import logger

from llm_orchestrator_config.vault.vault_client import VaultAgentClient
from llm_orchestrator_config.vault.models import (
    AzureOpenAISecret,
    AWSBedrockSecret,
    get_secret_model,
)
from llm_orchestrator_config.vault.exceptions import VaultConnectionError


@dataclass
class CachedSecret:
    """Cached secret with TTL information."""

    data: Union[AzureOpenAISecret, AWSBedrockSecret]
    expires_at: datetime
    path: str


class SecretResolver:
    """Vault secret resolver with TTL cache and fallback support."""

    def __init__(
        self,
        vault_client: Optional[VaultAgentClient] = None,
        cache_ttl_minutes: int = 5,
        background_refresh: bool = True,
    ):
        """Initialize Secret Resolver.

        Args:
            vault_client: Vault client instance (creates default if None)
            cache_ttl_minutes: Cache TTL in minutes
            background_refresh: Enable background refresh of expired secrets
        """
        self.vault_client = vault_client or VaultAgentClient()
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        self.background_refresh = background_refresh

        # In-memory cache: path -> CachedSecret
        self._cache: Dict[str, CachedSecret] = {}
        self._cache_lock = threading.RLock()

        # Last-known-good fallback cache
        self._fallback_cache: Dict[str, Union[AzureOpenAISecret, AWSBedrockSecret]] = {}

        logger.info(f"SecretResolver initialized with {cache_ttl_minutes}min TTL")

    def get_secret_for_model(
        self,
        provider: str,
        environment: str,
        model_name: str,
        connection_id: Optional[str] = None,
    ) -> Optional[Union[AzureOpenAISecret, AWSBedrockSecret]]:
        """Get secret for a specific model.

        Args:
            provider: Provider name (azure_openai, aws_bedrock)
            environment: Environment (production, development, test)
            model_name: Model name from llm_config.yaml
            connection_id: Optional connection ID for dev/test environments

        Returns:
            Validated secret object or None if not found
        """
        # Determine the vault path
        vault_path = self._build_vault_path(
            provider, environment, model_name, connection_id
        )

        # Try cache first
        cached_secret = self._get_from_cache(vault_path)
        if cached_secret:
            return cached_secret

        # Fetch from Vault
        try:
            secret_data = self.vault_client.get_secret(vault_path)
            if not secret_data:
                logger.debug(f"Secret not found in Vault: {vault_path}")
                return self._get_fallback(vault_path)

            # Validate and parse secret
            secret_model = get_secret_model(provider)
            validated_secret = secret_model(**secret_data)

            # Verify model name matches (more flexible for production)
            if environment == "production":
                # For production, trust the model name from vault secret
                logger.debug(
                    f"Production secret model: {validated_secret.model}, requested: {model_name}"
                )
            elif validated_secret.model != model_name:
                logger.warning(
                    f"Model name mismatch: vault={validated_secret.model}, "
                    f"requested={model_name}"
                )
                # Continue anyway - vault might have updated model name

            # Cache the secret
            self._cache_secret(vault_path, validated_secret)

            # Update fallback cache
            self._fallback_cache[vault_path] = validated_secret

            logger.debug(f"Successfully resolved secret for {provider}/{model_name}")
            return validated_secret

        except VaultConnectionError:
            logger.warning(f"Vault unavailable, trying fallback for {vault_path}")
            return self._get_fallback(vault_path)
        except Exception as e:
            logger.error(f"Error resolving secret for {vault_path}: {e}")
            return self._get_fallback(vault_path)

    def list_available_models(self, provider: str, environment: str) -> list[str]:
        """List available models for a provider and environment.

        Args:
            provider: Provider name (azure_openai, aws_bedrock)
            environment: Environment (production, development, test)

        Returns:
            List of available model names
        """
        if environment == "production":
            # For production: Check provider/production path for available models
            production_path = f"llm/connections/{provider}/{environment}"
            try:
                models = self.vault_client.list_secrets(production_path)
                if models:
                    logger.debug(
                        f"Found {len(models)} production models for {provider}: {models}"
                    )
                    return models
                else:
                    logger.debug(f"No production models found for {provider}")
                    return []

            except Exception as e:
                logger.debug(f"Provider {provider} not available in production: {e}")
                return []
        else:
            # For dev/test: Use existing logic with connection_id paths
            base_path = f"llm/connections/{provider}/{environment}"
            try:
                models = self.vault_client.list_secrets(base_path)
                if models:
                    logger.debug(
                        f"Found {len(models)} models for {provider}/{environment}"
                    )
                    return models
                else:
                    logger.debug(f"No models found for {provider}/{environment}")
                    return []

            except Exception as e:
                logger.error(f"Error listing models for {provider}/{environment}: {e}")
                return []

    def refresh_secret(self, vault_path: str) -> bool:
        """Manually refresh a specific secret.

        Args:
            vault_path: Vault path to refresh

        Returns:
            True if refresh successful
        """
        try:
            secret_data = self.vault_client.get_secret(vault_path)
            if not secret_data:
                logger.debug(f"Secret not found during refresh: {vault_path}")
                return False

            # Determine provider from path
            path_parts = vault_path.split("/")
            if len(path_parts) >= 4:
                provider = path_parts[2]  # llm/connections/PROVIDER/...
                secret_model = get_secret_model(provider)
                validated_secret = secret_model(**secret_data)

                # Update cache
                self._cache_secret(vault_path, validated_secret)
                self._fallback_cache[vault_path] = validated_secret

                logger.debug(f"Successfully refreshed secret: {vault_path}")
                return True

        except Exception as e:
            logger.error(f"Error refreshing secret {vault_path}: {e}")

        return False

    def get_cache_status(self) -> Dict[str, Any]:
        """Get cache status information.

        Returns:
            Dictionary with cache statistics
        """
        with self._cache_lock:
            now = datetime.now()
            total_secrets = len(self._cache)
            expired_secrets = sum(
                1 for cached in self._cache.values() if cached.expires_at <= now
            )

            return {
                "total_cached_secrets": total_secrets,
                "expired_secrets": expired_secrets,
                "active_secrets": total_secrets - expired_secrets,
                "fallback_secrets": len(self._fallback_cache),
                "cache_ttl_minutes": int(self.cache_ttl.total_seconds() / 60),
            }

    def clear_cache(self) -> None:
        """Clear all cached secrets."""
        with self._cache_lock:
            self._cache.clear()
            logger.info("Secret cache cleared")

    def _build_vault_path(
        self,
        provider: str,
        environment: str,
        model_name: str,
        connection_id: Optional[str] = None,
    ) -> str:
        """Build Vault path for a secret.

        For production: llm/connections/{provider}/production/{model_name}
        For dev/test: use connection_id if provided, otherwise model name
        """
        if environment == "production":
            # Production uses provider/production/model_name path
            return f"llm/connections/{provider}/{environment}/{model_name}"
        else:
            # Development/test can use connection_id or fall back to model name
            model_identifier = connection_id if connection_id else model_name
            return f"llm/connections/{provider}/{environment}/{model_identifier}"

    def _get_from_cache(
        self, vault_path: str
    ) -> Optional[Union[AzureOpenAISecret, AWSBedrockSecret]]:
        """Get secret from cache if valid."""
        with self._cache_lock:
            cached = self._cache.get(vault_path)
            if cached and cached.expires_at > datetime.now():
                logger.debug(f"Cache hit for {vault_path}")
                return cached.data
            elif cached:
                logger.debug(f"Cache expired for {vault_path}")
                # Optionally trigger background refresh
                if self.background_refresh:
                    self._schedule_background_refresh(vault_path)
            return None

    def _cache_secret(
        self, vault_path: str, secret: Union[AzureOpenAISecret, AWSBedrockSecret]
    ) -> None:
        """Cache a secret with TTL."""
        with self._cache_lock:
            expires_at = datetime.now() + self.cache_ttl
            self._cache[vault_path] = CachedSecret(
                data=secret, expires_at=expires_at, path=vault_path
            )
            logger.debug(f"Cached secret {vault_path} until {expires_at}")

    def _get_fallback(
        self, vault_path: str
    ) -> Optional[Union[AzureOpenAISecret, AWSBedrockSecret]]:
        """Get secret from fallback cache."""
        fallback = self._fallback_cache.get(vault_path)
        if fallback:
            logger.info(f"Using fallback secret for {vault_path}")
            return fallback
        return None

    def _schedule_background_refresh(self, vault_path: str) -> None:
        """Schedule background refresh of an expired secret."""

        def refresh_task():
            logger.debug(f"Background refresh for {vault_path}")
            self.refresh_secret(vault_path)

        # Use threading for background refresh
        thread = threading.Thread(target=refresh_task, daemon=True)
        thread.start()
