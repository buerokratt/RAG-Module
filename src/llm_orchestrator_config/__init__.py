"""LLM Config Module - A configurable LLM provider management system.

This module provides a flexible, factory-pattern-based system for managing
different LLM providers with DSPY integration. It supports configuration
via YAML files with environment variable substitution.

Example usage:
    from llm_config_module import LLMManager, LLMProvider

    # Get the default configured LLM
    manager = LLMManager()
    llm = manager.get_llm()

    # Generate text
    response = llm.generate("Hello, world!")

    # Use with DSPY
    import dspy
    manager.configure_dspy()

    # Or get a specific provider
    azure_llm = manager.get_llm(LLMProvider.AZURE_OPENAI)
"""

from llm_orchestrator_config.llm_manager import LLMManager
from llm_orchestrator_config.llm_factory import LLMFactory
from llm_orchestrator_config.types import LLMProvider
from llm_orchestrator_config.exceptions import (
    LLMConfigError,
    ConfigurationError,
    UnsupportedProviderError,
    ProviderInitializationError,
    InvalidConfigurationError,
)

# Re-export key classes for convenience
from llm_orchestrator_config.providers import (
    BaseLLMProvider,
    AzureOpenAIProvider,
    AWSBedrockProvider,
)
from llm_orchestrator_config.config import ConfigurationLoader, LLMConfiguration

__version__ = "0.1.0"

__all__ = [
    # Main API
    "LLMManager",
    "LLMFactory",
    "LLMProvider",
    # Exceptions
    "LLMConfigError",
    "ConfigurationError",
    "UnsupportedProviderError",
    "ProviderInitializationError",
    "InvalidConfigurationError",
    # Provider classes (for advanced usage)
    "BaseLLMProvider",
    "AzureOpenAIProvider",
    "AWSBedrockProvider",
    # Configuration classes (for advanced usage)
    "ConfigurationLoader",
    "LLMConfiguration",
]
