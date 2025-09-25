"""HashiCorp Vault client for RAG Config Manager."""

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, List, cast
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from loguru import logger

from rag_config_manager.exceptions import VaultConnectionError, VaultSecretError


# Constants
VAULT_NOT_AVAILABLE_MSG = "Vault is not available"


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle datetime objects."""

    def default(self, o: Any) -> Any:
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


class VaultClient:
    """HashiCorp Vault client for secret management."""

    def __init__(
        self,
        vault_url: str = "http://localhost:8200",
        token: Optional[str] = None,
        mount_point: str = "secret",
    ):
        """Initialize Vault client.

        Args:
            vault_url: Vault server URL
            token: Vault authentication token
            mount_point: KV mount point (default: secret)
        """
        self.vault_url = vault_url.rstrip("/")
        self.token = token or os.getenv("VAULT_TOKEN")
        self.mount_point = mount_point
        self.session = self._create_session()
        self.headers = {"X-Vault-Token": self.token, "Content-Type": "application/json"}

        logger.info(f"Initialized Vault client: {self.vault_url}")

    def _create_session(self) -> requests.Session:
        """Create requests session with retry strategy."""
        session = requests.Session()

        # Retry strategy
        retry_strategy = Retry(
            total=3, status_forcelist=[429, 500, 502, 503, 504], backoff_factor=1
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def is_vault_available(self) -> bool:
        """Check if Vault is available and accessible."""
        try:
            response = self.session.get(f"{self.vault_url}/v1/sys/health", timeout=5)
            is_available = response.status_code in [200, 429, 472, 473, 501]
            logger.debug(f"Vault availability check: {is_available}")
            return is_available
        except Exception as e:
            logger.warning(f"Vault not available: {e}")
            return False

    def get_secret(self, path: str) -> Optional[Dict[str, Any]]:
        """Retrieve secret from Vault KV store.

        Args:
            path: Secret path (e.g., "users/user1/azure-openai/conn_123")

        Returns:
            Secret data or None if not found
        """
        if not self.is_vault_available():
            raise VaultConnectionError(VAULT_NOT_AVAILABLE_MSG)

        try:
            # For KV v2 in dev mode, use the data endpoint
            url = f"{self.vault_url}/v1/{self.mount_point}/data/{path}"

            response = self.session.get(url, headers=self.headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                # KV v2 stores actual data under 'data' key
                secret_data = data.get("data", {}).get("data", {})
                # Convert ISO datetime strings back to datetime objects if needed
                return self._deserialize_datetimes(secret_data)
            elif response.status_code == 404:
                logger.debug(f"Secret not found at path: {path}")
                return None
            else:
                logger.error(
                    f"Failed to retrieve secret: {response.status_code} - {response.text}"
                )
                raise VaultSecretError(
                    f"Failed to retrieve secret: {response.status_code}"
                )

        except requests.RequestException as e:
            logger.error(f"Error retrieving secret from path {path}: {e}")
            raise VaultSecretError(f"Error retrieving secret: {e}")

    def put_secret(self, path: str, data: Dict[str, Any]) -> bool:
        """Store secret in Vault KV store.

        Args:
            path: Secret path
            data: Secret data to store

        Returns:
            True if successful, False otherwise
        """
        if not self.is_vault_available():
            raise VaultConnectionError(VAULT_NOT_AVAILABLE_MSG)

        try:
            # For KV v2 in dev mode, use the data endpoint with nested data structure
            url = f"{self.vault_url}/v1/{self.mount_point}/data/{path}"
            payload = {"data": data}

            # Use custom JSON encoder to handle datetime objects
            json_payload = json.dumps(payload, cls=DateTimeEncoder)

            response = self.session.post(
                url, data=json_payload, headers=self.headers, timeout=10
            )

            if response.status_code in [200, 204]:
                logger.info(f"Successfully stored secret at path: {path}")
                return True
            else:
                logger.error(
                    f"Failed to store secret: {response.status_code} - {response.text}"
                )
                raise VaultSecretError(
                    f"Failed to store secret: {response.status_code}"
                )

        except requests.RequestException as e:
            logger.error(f"Error storing secret at path {path}: {e}")
            raise VaultSecretError(f"Error storing secret: {e}")

    def delete_secret(self, path: str) -> bool:
        """Delete secret from Vault KV store.

        Args:
            path: Secret path to delete

        Returns:
            True if successful, False otherwise
        """
        if not self.is_vault_available():
            raise VaultConnectionError(VAULT_NOT_AVAILABLE_MSG)

        try:
            url = f"{self.vault_url}/v1/{self.mount_point}/data/{path}"

            response = self.session.delete(url, headers=self.headers, timeout=10)

            if response.status_code in [200, 204, 404]:  # 404 means already deleted
                logger.info(f"Successfully deleted secret at path: {path}")
                return True
            else:
                logger.error(
                    f"Failed to delete secret: {response.status_code} - {response.text}"
                )
                raise VaultSecretError(
                    f"Failed to delete secret: {response.status_code}"
                )

        except requests.RequestException as e:
            logger.error(f"Error deleting secret at path {path}: {e}")
            raise VaultSecretError(f"Error deleting secret: {e}")

    def list_secrets(self, path: str) -> Optional[List[str]]:
        """List secrets at given path.

        Args:
            path: Path to list secrets from

        Returns:
            List of secret names or None if not found
        """
        if not self.is_vault_available():
            raise VaultConnectionError(VAULT_NOT_AVAILABLE_MSG)

        try:
            url = f"{self.vault_url}/v1/{self.mount_point}/metadata/{path}"
            params = {"list": "true"}

            response = self.session.get(
                url, headers=self.headers, params=params, timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                keys = data.get("data", {}).get("keys", [])
                logger.debug(f"Listed {len(keys)} secrets at path: {path}")
                return keys
            elif response.status_code == 404:
                logger.debug(f"No secrets found at path: {path}")
                return []
            else:
                logger.error(
                    f"Failed to list secrets: {response.status_code} - {response.text}"
                )
                return None

        except requests.RequestException as e:
            logger.error(f"Error listing secrets at path {path}: {e}")
            return None

    def _deserialize_datetimes(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert ISO format strings back to datetime objects.

        Args:
            data: Dictionary that may contain ISO datetime strings

        Returns:
            Dictionary with ISO strings converted back to datetime objects where appropriate
        """
        # Constants
        TIMEZONE_SUFFIX = "+00:00"

        deserialized: Dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, str) and self._is_iso_datetime(value):
                try:
                    deserialized[key] = datetime.fromisoformat(
                        value.replace("Z", TIMEZONE_SUFFIX)
                    )
                except ValueError:
                    deserialized[key] = value
            elif isinstance(value, dict):
                # Cast to proper type for recursion
                dict_value = cast(Dict[str, Any], value)
                deserialized[key] = self._deserialize_datetimes(dict_value)
            elif isinstance(value, list):
                # Cast to proper type for list processing
                list_value = cast(List[Any], value)
                deserialized[key] = self._deserialize_list_items(
                    list_value, TIMEZONE_SUFFIX
                )
            else:
                deserialized[key] = value
        return deserialized

    def _deserialize_list_items(
        self, items: List[Any], timezone_suffix: str
    ) -> List[Any]:
        """Helper method to deserialize list items."""
        result: List[Any] = []
        for item in items:
            if isinstance(item, str) and self._is_iso_datetime(item):
                try:
                    result.append(
                        datetime.fromisoformat(item.replace("Z", timezone_suffix))
                    )
                except ValueError:
                    result.append(item)
            elif isinstance(item, dict):
                # Cast to proper type for recursion
                dict_item = cast(Dict[str, Any], item)
                result.append(self._deserialize_datetimes(dict_item))
            else:
                result.append(item)
        return result

    def _is_iso_datetime(self, value: str) -> bool:
        """Check if string looks like an ISO datetime format.

        Args:
            value: String to check

        Returns:
            True if string matches ISO datetime pattern
        """
        try:
            # Simple heuristic: contains 'T' and has reasonable length for datetime
            if "T" in value and 19 <= len(value) <= 32:
                # Try parsing to validate
                datetime.fromisoformat(value.replace("Z", "+00:00"))
                return True
        except (ValueError, TypeError):
            pass
        return False
