"""Azure OpenAI provider implementation."""

from typing import Any, Dict, List

import dspy

from llm_orchestrator_config.providers.base import BaseLLMProvider
from llm_orchestrator_config.exceptions import ProviderInitializationError


class AzureOpenAIProvider(BaseLLMProvider):
    """Azure OpenAI provider implementation using DSPY."""

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "Azure OpenAI"

    def get_required_config_fields(self) -> List[str]:
        """Return list of required configuration fields."""
        return [
            "enabled",
            "model",
            "endpoint",
            "api_key",
            "deployment_name",
            "api_version",
        ]

    def initialize(self) -> None:
        """Initialize the Azure OpenAI provider.

        Raises:
            ProviderInitializationError: If initialization fails.
        """
        try:
            self.validate_config()

            # Initialize DSPY LM client with proper Azure OpenAI configuration
            self._client = dspy.LM(
                model=f"azure/{self.config['deployment_name']}",  # Proper Azure model format
                model_type=self.config.get("model_type", "chat"),
                temperature=self.config.get(
                    "temperature", 0.0
                ),  # Use DSPY default of 0.0
                max_tokens=self.config.get(
                    "max_tokens", 4000
                ),  # Use DSPY default of 4000
                cache=False,  # If this enable true repeated questions are performing incorrect behaviour
                callbacks=None,
                num_retries=self.config.get(
                    "num_retries", 3
                ),  # Explicit retry configuration
                api_key=self.config["api_key"],
                api_base=self.config["endpoint"],
                api_version=self.config["api_version"],
            )

            self._initialized = True

        except Exception as e:
            raise ProviderInitializationError(
                f"Failed to initialize {self.provider_name} provider: {e}"
            ) from e

    def get_dspy_client(self) -> dspy.LM:
        """Return DSPY-compatible client.

        Returns:
            DSPY LM client instance.

        Raises:
            RuntimeError: If the provider is not initialized.
        """
        self._ensure_initialized()

        if self._client is None:
            raise RuntimeError("Client is not initialized")

        return self._client

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the configured model.

        Returns:
            Dictionary containing model information.
        """
        base_info = super().get_model_info()
        base_info.update(
            {
                "endpoint": self.config.get("endpoint", ""),
                "deployment_name": self.config.get("deployment_name", ""),
                "api_version": self.config.get("api_version", ""),
            }
        )
        return base_info
