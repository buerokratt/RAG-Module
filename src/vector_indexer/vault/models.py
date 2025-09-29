"""Pydantic models for embedding vault connection secrets."""

from typing import List, Dict, Union
from pydantic import BaseModel, Field, field_validator


class BaseEmbeddingSecret(BaseModel):
    """Base model for embedding connection secrets stored in Vault."""

    connection_id: str = Field(..., description="Unique connection identifier")
    model: str = Field(..., description="Model name (e.g., text-embedding-3-large)")
    environment: str = Field(
        ..., description="Environment: production/development/test"
    )
    tags: List[str] = Field(default_factory=list, description="Connection tags")

    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags(cls, value: Union[str, List[str], None]) -> List[str]:
        """Convert string tags to list if needed.

        Handles both:
        - List format: ["tag1", "tag2", "tag3"]
        - String format: "tag1,tag2,tag3"
        """
        if isinstance(value, str):
            # Split comma-separated string and strip whitespace
            return [tag.strip() for tag in value.split(",") if tag.strip()]
        elif isinstance(value, list):
            # Already a list, ensure all items are strings
            return [str(tag).strip() for tag in value]
        else:
            # Default to empty list for other types
            return []


class AzureEmbeddingSecret(BaseEmbeddingSecret):
    """Azure OpenAI embedding connection secrets from Vault."""

    endpoint: str = Field(..., description="Azure OpenAI endpoint URL")
    api_key: str = Field(..., description="Azure OpenAI API key")
    deployment_name: str = Field(..., description="Azure deployment name")
    api_version: str = Field(
        default="2024-12-01-preview", description="Azure OpenAI API version"
    )
    embedding_dimension: int = Field(
        default=3072, description="Embedding vector dimension"
    )


# Type mapping for embedding provider secrets
EMBEDDING_SECRET_MODELS: Dict[str, type] = {
    "azure_openai": AzureEmbeddingSecret,
}


def get_embedding_secret_model(provider: str) -> type:
    """Get the appropriate secret model for an embedding provider.

    Args:
        provider: Provider name (azure_openai)

    Returns:
        Pydantic model class for the provider

    Raises:
        ValueError: If provider is not supported
    """
    if provider not in EMBEDDING_SECRET_MODELS:
        raise ValueError(f"Unsupported embedding provider: {provider}")
    return EMBEDDING_SECRET_MODELS[provider]
