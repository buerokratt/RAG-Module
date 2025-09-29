"""Factory class for creating LLM provider instances."""

from typing import Any, Dict, Type

from llm_orchestrator_config.providers.base import BaseLLMProvider
from llm_orchestrator_config.providers.azure_openai import AzureOpenAIProvider
from llm_orchestrator_config.providers.aws_bedrock import AWSBedrockProvider
from llm_orchestrator_config.types import LLMProvider
from llm_orchestrator_config.exceptions import UnsupportedProviderError


class LLMFactory:
    """Factory class for creating LLM provider instances using the Factory Method pattern."""

    # Registry of available providers
    _providers: Dict[LLMProvider, Type[BaseLLMProvider]] = {
        LLMProvider.AZURE_OPENAI: AzureOpenAIProvider,
        LLMProvider.AWS_BEDROCK: AWSBedrockProvider,
    }

    @classmethod
    def create_provider(
        cls, provider_type: LLMProvider, config: Dict[str, Any]
    ) -> BaseLLMProvider:
        """Create and return a provider instance.

        Args:
            provider_type: The type of provider to create.
            config: Configuration dictionary for the provider.

        Returns:
            Initialized provider instance.

        Raises:
            UnsupportedProviderError: If the provider type is not supported.
            InvalidConfigurationError: If the configuration is invalid.
            ProviderInitializationError: If provider initialization fails.
        """
        if provider_type not in cls._providers:
            available_providers = ", ".join([p.value for p in cls._providers.keys()])
            raise UnsupportedProviderError(
                f"Provider '{provider_type.value}' is not supported. "
                f"Available providers: {available_providers}"
            )

        provider_class = cls._providers[provider_type]
        provider = provider_class(config)

        # Validate configuration and initialize the provider
        provider.validate_config()
        provider.initialize()

        return provider

    @classmethod
    def register_provider(
        cls, provider_type: LLMProvider, provider_class: Type[BaseLLMProvider]
    ) -> None:
        """Register a new provider type.

        This allows for extending the factory with custom providers.

        Args:
            provider_type: The provider type enum value.
            provider_class: The provider class to register.
        """
        cls._providers[provider_type] = provider_class

    @classmethod
    def get_supported_providers(cls) -> Dict[LLMProvider, Type[BaseLLMProvider]]:
        """Get all supported providers.

        Returns:
            Dictionary mapping provider types to their classes.
        """
        return cls._providers.copy()

    @classmethod
    def is_provider_supported(cls, provider_type: LLMProvider) -> bool:
        """Check if a provider type is supported.

        Args:
            provider_type: The provider type to check.

        Returns:
            True if the provider is supported, False otherwise.
        """
        return provider_type in cls._providers
