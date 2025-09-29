"""Vault Agent client using hvac library."""

import os
from pathlib import Path
from typing import Optional, Dict, Any, cast
from loguru import logger
import hvac

from llm_orchestrator_config.vault.exceptions import (
    VaultConnectionError,
    VaultSecretError,
    VaultTokenError,
)


class VaultAgentClient:
    """HashiCorp Vault client using Vault Agent token."""

    def __init__(
        self,
        vault_url: Optional[str] = None,
        token_path: str = "/agent/out/token",
        mount_point: str = "secret",
        timeout: int = 10,
    ):
        """Initialize Vault Agent client.

        Args:
            vault_url: Vault server URL (defaults to VAULT_ADDR env var)
            token_path: Path to Vault Agent token file
            mount_point: KV v2 mount point
            timeout: Request timeout in seconds
        """
        self.vault_url = vault_url or os.getenv("VAULT_ADDR", "http://vault:8200")
        self.token_path = Path(token_path)
        self.mount_point = mount_point
        self.timeout = timeout

        # Initialize hvac client
        self.client = hvac.Client(
            url=self.vault_url,
            timeout=timeout,
        )

        # Load token from Vault Agent
        self._load_token()

        logger.info(f"Vault Agent client initialized: {self.vault_url}")

    def _load_token(self) -> None:
        """Load token from Vault Agent token file.

        Raises:
            VaultTokenError: If token file is missing or unreadable
        """
        try:
            if not self.token_path.exists():
                raise VaultTokenError(
                    f"Vault Agent token file not found: {self.token_path}"
                )

            with open(self.token_path, "r") as f:
                token = f.read().strip()

            if not token:
                raise VaultTokenError("Vault Agent token file is empty")

            # Log token info for debugging (first and last 4 chars only for security)
            token_preview = f"{token[:4]}...{token[-4:]}" if len(token) > 8 else "****"
            logger.debug(f"Loaded token: {token_preview} (length: {len(token)})")

            self.client.token = token
            logger.debug("Vault Agent token loaded successfully")

        except (OSError, IOError) as e:
            raise VaultTokenError(f"Failed to read Vault Agent token: {e}")

    def is_authenticated(self) -> bool:
        """Check if client is authenticated with Vault.

        Returns:
            True if authenticated, False otherwise
        """
        try:
            # Check if we have a token
            if not hasattr(self.client, "token") or not self.client.token:
                logger.debug("No token set on client")
                return False

            # Test authentication with a simple lookup_self call
            result = self.client.is_authenticated()
            logger.debug(f"Vault authentication result: {result}")

            # Additional debug - try to get token info
            try:
                token_info = cast(Dict[str, Any], self.client.lookup_token())
                logger.debug(
                    f"Token info: policies={token_info.get('data', {}).get('policies', [])}"
                )
            except Exception as token_e:
                logger.debug(
                    f"Could not get token info (this might be normal): {token_e}"
                )

            return result

        except Exception as e:
            logger.warning(f"Vault authentication check failed: {e}")
            return False

    def is_vault_available(self) -> bool:
        """Check if Vault is available and accessible.

        Returns:
            True if Vault is available, False otherwise
        """
        try:
            response = self.client.sys.read_health_status()
            logger.debug(f"Vault health response type: {type(response)}")
            logger.debug(f"Vault health response: {response}")

            # For Vault health endpoint, we primarily check the HTTP status code
            if hasattr(response, "status_code"):
                is_available = response.status_code == 200
                logger.debug(
                    f"Vault health check: status_code={response.status_code}, available={is_available}"
                )

                # Try to get additional details from response body if available
                try:
                    if hasattr(response, "json") and callable(
                        getattr(response, "json")
                    ):
                        health_data = response.json()
                        logger.debug(f"Vault health details: {health_data}")
                except Exception as e:
                    logger.debug(
                        f"Could not parse health response body (this is normal): {e}"
                    )

                return is_available
            else:
                # Fallback for non-Response objects (direct dict)
                if isinstance(response, dict):
                    is_available = response.get(
                        "initialized", False
                    ) and not response.get("sealed", True)
                    logger.debug(f"Vault availability check from dict: {is_available}")
                    return is_available
                else:
                    logger.warning(f"Unexpected response type: {type(response)}")
                    return False

        except Exception as e:
            logger.warning(f"Vault not available: {e}")
            return False

    def get_secret(self, path: str) -> Optional[Dict[str, Any]]:
        """Retrieve secret from Vault KV v2 store.

        Args:
            path: Secret path (e.g., "llm/connections/azure_openai/production/gpt-4o")

        Returns:
            Secret data or None if not found

        Raises:
            VaultConnectionError: If Vault is not available
            VaultSecretError: If secret retrieval fails
        """
        if not self.is_vault_available():
            raise VaultConnectionError("Vault is not available")

        if not self.is_authenticated():
            # Try to reload token
            self._load_token()
            if not self.is_authenticated():
                raise VaultConnectionError("Vault authentication failed")

        try:
            # Use KV v2 API
            response = self.client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point=self.mount_point,
            )

            if response and "data" in response:
                secret_data = response["data"]["data"]
                logger.debug(f"Successfully retrieved secret from path: {path}")
                return secret_data
            else:
                logger.debug(f"Secret not found at path: {path}")
                return None

        except hvac.exceptions.InvalidPath:
            logger.debug(f"Secret not found at path: {path}")
            return None
        except hvac.exceptions.Forbidden as e:
            raise VaultSecretError(f"Access denied to secret path {path}: {e}")
        except Exception as e:
            logger.error(f"Error retrieving secret from path {path}: {e}")
            raise VaultSecretError(f"Failed to retrieve secret: {e}")

    def list_secrets(self, path: str) -> Optional[list[str]]:
        """List secrets at the given path.

        Args:
            path: Directory path to list

        Returns:
            List of secret names or None if path doesn't exist

        Raises:
            VaultConnectionError: If Vault is not available
            VaultSecretError: If listing fails
        """
        if not self.is_vault_available():
            raise VaultConnectionError("Vault is not available")

        if not self.is_authenticated():
            self._load_token()
            if not self.is_authenticated():
                raise VaultConnectionError("Vault authentication failed")

        try:
            response = self.client.secrets.kv.v2.list_secrets(
                path=path,
                mount_point=self.mount_point,
            )
            logger.debug(f"List secrets response: {response}")

            if response and "data" in response:
                keys = response["data"].get("keys", [])
                logger.debug(f"Listed {len(keys)} secrets at path: {path}")
                return keys
            else:
                logger.debug(f"No secrets found at path: {path}")
                return None

        except hvac.exceptions.InvalidPath:
            logger.debug(f"Path not found: {path}")
            return None
        except Exception as e:
            logger.error(f"Error listing secrets at path {path}: {e}")
            raise VaultSecretError(f"Failed to list secrets: {e}")

    def refresh_token(self) -> bool:
        """Refresh token from Vault Agent.

        Returns:
            True if token was refreshed successfully
        """
        try:
            self._load_token()
            return self.is_authenticated()
        except Exception as e:
            logger.error(f"Failed to refresh Vault token: {e}")
            return False
