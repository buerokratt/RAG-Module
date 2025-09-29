"""Custom exceptions for the LLM Config Module."""


class LLMConfigError(Exception):
    """Base exception for LLM configuration errors."""

    pass


class ConfigurationError(LLMConfigError):
    """Raised when there's an error in configuration loading or validation."""

    pass


class UnsupportedProviderError(LLMConfigError):
    """Raised when an unsupported provider is requested."""

    pass


class ProviderInitializationError(LLMConfigError):
    """Raised when a provider fails to initialize."""

    pass


class InvalidConfigurationError(LLMConfigError):
    """Raised when configuration validation fails."""

    pass
