"""Base abstract class for LLM providers."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import dspy

from llm_orchestrator_config.exceptions import InvalidConfigurationError


class BaseLLMProvider(ABC):
    """Abstract base class for all LLM providers.

    This class defines the interface that all LLM providers must implement
    to ensure consistent behavior across different provider implementations.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize the provider with configuration.

        Args:
            config: Provider-specific configuration dictionary.
        """
        self.config = config
        self._client: Optional[dspy.LM] = None
        self._initialized = False

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the provider with configuration.

        This method should set up the provider's client and perform
        any necessary initialization steps.

        Raises:
            ProviderInitializationError: If initialization fails.
        """
        pass

    @abstractmethod
    def get_dspy_client(self) -> dspy.LM:
        """Return DSPY-compatible client.

        Returns:
            DSPY LM client instance.

        Raises:
            RuntimeError: If the provider is not initialized.
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name.

        Returns:
            Human-readable provider name.
        """
        pass

    def validate_config(self) -> None:
        """Validate provider configuration.

        Raises:
            InvalidConfigurationError: If configuration is invalid.
        """
        required_fields = self.get_required_config_fields()
        missing_fields: List[str] = []

        for field in required_fields:
            if (
                field not in self.config or not self.config[field]
            ):  # Check for missing or empty strings/None
                missing_fields.append(field)

        if missing_fields:
            raise InvalidConfigurationError(
                f"Missing or empty required config fields for {self.provider_name}: "
                f"{', '.join(missing_fields)}"
            )

    @abstractmethod
    def get_required_config_fields(self) -> List[str]:
        """Return list of required configuration fields.

        Returns:
            List of required configuration field names.
        """
        pass

    def _ensure_initialized(self) -> None:
        """Ensure the provider is initialized.

        Raises:
            RuntimeError: If the provider is not initialized.
        """
        if not self._initialized:
            raise RuntimeError(f"{self.provider_name} provider is not initialized")

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the configured model.

        Returns:
            Dictionary containing model information.
        """
        return {
            "provider": self.provider_name,
            "model": self.config.get("model", "unknown"),
            "max_tokens": self.config.get("max_tokens", 4096),
            "temperature": self.config.get("temperature", 0.7),
        }
