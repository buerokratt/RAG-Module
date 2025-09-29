"""Type definitions for the LLM Config Module."""

from typing import Any, Dict, Protocol, Union
from enum import Enum


class LLMProvider(str, Enum):
    """Enumeration of supported LLM providers."""

    AZURE_OPENAI = "azure_openai"
    AWS_BEDROCK = "aws_bedrock"


class LLMResponse(Protocol):
    """Protocol for LLM response objects."""

    content: str
    usage: Dict[str, Any]
    model: str


# Type aliases for better readability
ProviderConfig = Dict[str, Any]
LLMConfig = Dict[str, Union[str, Dict[str, Any]]]
