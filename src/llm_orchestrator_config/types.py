"""Type definitions for the LLM Config Module."""

from typing import Any, Dict, Union
from enum import Enum
from pydantic import BaseModel, Field


class LLMProvider(str, Enum):
    """Enumeration of supported LLM providers."""

    AZURE_OPENAI = "azure_openai"
    AWS_BEDROCK = "aws_bedrock"


class ModelType(str, Enum):
    """Enumeration of model types."""

    CHAT = "chat"
    COMPLETION = "completion"
    EMBEDDING = "embedding"
    CONTEXT_GENERATION = "context_generation"


class EmbeddingProvider(str, Enum):
    """Enumeration of supported embedding providers."""

    AZURE_OPENAI = "azure_openai"
    AWS_BEDROCK = "aws_bedrock"
    OPENAI = "openai"


class LLMResponse(BaseModel):
    """Pydantic model for LLM response objects."""

    content: str = Field(..., description="Response content from the LLM")
    usage: Dict[str, Any] = Field(..., description="Token usage information")
    model: str = Field(..., description="Model name that generated the response")


# Type aliases for better readability
ProviderConfig = Dict[str, Any]
LLMConfig = Dict[str, Union[str, Dict[str, Any]]]
