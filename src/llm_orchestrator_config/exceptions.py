"""Custom exceptions for the LLM Config Module."""

from typing import Optional


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


class ContextualRetrievalError(LLMConfigError):
    """Base exception for contextual retrieval errors."""

    pass


class ContextualRetrieverInitializationError(ContextualRetrievalError):
    """Raised when contextual retriever fails to initialize."""

    pass


class ContextualRetrievalFailureError(ContextualRetrievalError):
    """Raised when contextual chunk retrieval fails."""

    pass


class StreamTimeoutError(LLMConfigError):
    """Raised when stream duration exceeds maximum allowed time."""

    def __init__(
        self, message: str = "Stream timeout", error_id: Optional[str] = None
    ) -> None:
        """
        Initialize StreamTimeoutError with error tracking.

        Args:
            message: Human-readable error message
            error_id: Optional error ID (auto-generated if not provided)
        """
        from src.utils.error_utils import generate_error_id

        self.error_id = error_id or generate_error_id()
        super().__init__(f"[{self.error_id}] {message}")


class StreamSizeLimitError(LLMConfigError):
    """Raised when stream size limits are exceeded."""

    pass


# Comprehensive error hierarchy for error boundaries
class StreamError(LLMConfigError):
    """Base exception for streaming operations with error tracking."""

    def __init__(self, message: str, error_id: Optional[str] = None) -> None:
        """
        Initialize StreamError with error tracking.

        Args:
            message: Human-readable error message
            error_id: Optional error ID (auto-generated if not provided)
        """
        from src.utils.error_utils import generate_error_id

        self.error_id = error_id or generate_error_id()
        self.user_message = message
        super().__init__(f"[{self.error_id}] {message}")


class ValidationError(StreamError):
    """Raised when input or request validation fails."""

    pass


class ServiceError(StreamError):
    """Raised when external service calls fail (LLM, Qdrant, Vault, etc.)."""

    pass


class GuardrailError(StreamError):
    """Raised when guardrails processing encounters errors."""

    pass
