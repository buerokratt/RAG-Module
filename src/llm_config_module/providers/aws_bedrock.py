"""AWS Bedrock provider implementation."""

from typing import Any, Dict, List

import dspy

from llm_config_module.providers.base import BaseLLMProvider
from llm_config_module.exceptions import ProviderInitializationError


class AWSBedrockProvider(BaseLLMProvider):
    """AWS Bedrock provider implementation using DSPY."""

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "AWS Bedrock"

    def get_required_config_fields(self) -> List[str]:
        """Return list of required configuration fields."""
        return ["enabled", "model", "region", "access_key_id", "secret_access_key"]

    def initialize(self) -> None:
        """Initialize the AWS Bedrock provider.

        Raises:
            ProviderInitializationError: If initialization fails.
        """
        try:
            self.validate_config()

            # Initialize DSPY LM client with Bedrock model
            # DSPy uses LM with bedrock/ prefix for Bedrock models
            model_name = f"bedrock/{self.config['model']}"
            self._client = dspy.LM(
                model=model_name,
                model_type="chat",  # Explicit model type for proper response parsing
                temperature=self.config.get(
                    "temperature", 0.0
                ),  # Use DSPY default of 0.0
                max_tokens=self.config.get(
                    "max_tokens", 4000
                ),  # Use DSPY default of 4000
                cache=True,  # Keep caching enabled (DSPY default) - this fixes serialization
                callbacks=None,
                num_retries=self.config.get(
                    "num_retries", 3
                ),  # Explicit retry configuration
                # AWS Bedrock specific parameters
                aws_access_key_id=self.config.get("access_key_id"),
                aws_secret_access_key=self.config.get("secret_access_key"),
                aws_session_token=self.config.get("session_token"),
                region_name=self.config.get("region"),
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
                "region": self.config.get("region", ""),
                "model_id": self.config.get("model", ""),
            }
        )
        return base_info
