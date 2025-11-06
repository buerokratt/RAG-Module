"""Pydantic models for API requests and responses."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class ConversationItem(BaseModel):
    """Model for conversation history item."""

    authorRole: Literal["user", "bot"] = Field(
        ..., description="Role of the message author"
    )
    message: str = Field(..., description="Content of the message")
    timestamp: str = Field(..., description="Timestamp in ISO format")


class PromptRefinerOutput(BaseModel):
    """Model for prompt refiner output."""

    original_question: str = Field(..., description="The original user question")
    refined_questions: List[str] = Field(
        ..., description="List of refined question variants"
    )


class OrchestrationRequest(BaseModel):
    """Model for LLM orchestration request."""

    chatId: str = Field(..., description="Unique identifier for the chat session")
    message: str = Field(..., description="User's message/query")
    authorId: str = Field(..., description="Unique identifier for the user")
    conversationHistory: List[ConversationItem] = Field(
        ..., description="Previous conversation history"
    )
    url: str = Field(..., description="Source URL context")
    environment: Literal["production", "test", "development"] = Field(
        ..., description="Environment context"
    )
    connection_id: Optional[str] = Field(
        None, description="Optional connection identifier"
    )


class OrchestrationResponse(BaseModel):
    """Model for LLM orchestration response."""

    chatId: str = Field(..., description="Chat session identifier from request")
    llmServiceActive: bool = Field(..., description="Whether LLM service is active")
    questionOutOfLLMScope: bool = Field(
        ..., description="Whether question is out of LLM scope"
    )
    inputGuardFailed: bool = Field(
        ..., description="Whether input guard validation failed"
    )
    content: str = Field(..., description="Response content with citations")
    # Testing-only fields (populated when EVAL_MODE=true)
    retrieval_context: Optional[List[Dict[str, Any]]] = Field(
        default=None, exclude=True
    )
    refined_questions: Optional[List[str]] = Field(default=None, exclude=True)


# New models for embedding and context generation


class EmbeddingRequest(BaseModel):
    """Request model for embedding generation.

    Model name is resolved from vault based on environment and connection_id.
    No explicit model_name parameter needed - uses vault-driven model selection.
    """

    texts: List[str] = Field(..., description="List of texts to embed", max_length=1000)
    environment: Literal["production", "development", "test"] = Field(
        ..., description="Environment for model resolution"
    )
    batch_size: Optional[int] = Field(
        50,  # Using small batch size as requested
        description="Batch size for processing",
        ge=1,
        le=100,
    )
    connection_id: Optional[str] = Field(
        None,
        description="Connection ID for dev/test environments (required for non-production)",
    )


class EmbeddingResponse(BaseModel):
    """Response model for embedding generation."""

    embeddings: List[List[float]] = Field(..., description="List of embedding vectors")
    model_used: str = Field(..., description="Actual model used for embeddings")
    processing_info: Dict[str, Any] = Field(..., description="Processing metadata")
    total_tokens: Optional[int] = Field(None, description="Total tokens processed")


class ContextGenerationRequest(BaseModel):
    """Request model for context generation using Anthropic methodology."""

    document_prompt: str = Field(
        ..., description="Document content for caching", max_length=100000
    )
    chunk_prompt: str = Field(..., description="Chunk-specific prompt", max_length=5000)
    environment: Literal["production", "development", "test"] = Field(
        ..., description="Environment for model resolution"
    )
    use_cache: bool = Field(default=True, description="Enable prompt caching")
    connection_id: Optional[str] = Field(
        None, description="Connection ID for dev/test environments"
    )
    max_tokens: int = Field(
        default=1000, description="Maximum tokens for response", ge=1, le=8192
    )
    temperature: float = Field(
        default=0.1, description="Temperature for response generation", ge=0.0, le=2.0
    )


class ContextGenerationResponse(BaseModel):
    """Response model for context generation."""

    context: str = Field(..., description="Generated contextual description")
    usage: Dict[str, int] = Field(..., description="Token usage breakdown")
    cache_performance: Dict[str, Any] = Field(
        ..., description="Caching performance metrics"
    )
    model_used: str = Field(..., description="Model used for generation")


class EmbeddingErrorResponse(BaseModel):
    """Error response for embedding failures."""

    error: str = Field(..., description="Error message")
    failed_texts: List[str] = Field(..., description="Texts that failed to embed")
    retry_after: Optional[int] = Field(None, description="Retry after seconds")


# Test endpoint models


class TestOrchestrationRequest(BaseModel):
    """Model for simplified test orchestration request."""

    message: str = Field(..., description="User's message/query")
    environment: Literal["production", "test", "development"] = Field(
        ..., description="Environment context"
    )
    connectionId: Optional[int] = Field(
        ..., description="Optional connection identifier"
    )


class TestOrchestrationResponse(BaseModel):
    """Model for test orchestration response (without chatId)."""

    llmServiceActive: bool = Field(..., description="Whether LLM service is active")
    questionOutOfLLMScope: bool = Field(
        ..., description="Whether question is out of LLM scope"
    )
    inputGuardFailed: bool = Field(
        ..., description="Whether input guard validation failed"
    )
    content: str = Field(..., description="Response content with citations")


class DeepEvalTestOrchestrationResponse(BaseModel):
    """Extended response model for testing with additional evaluation data."""

    chatId: str
    llmServiceActive: bool
    questionOutOfLLMScope: bool
    inputGuardFailed: bool
    content: str
    retrieval_context: Optional[List[Dict[str, Any]]] = None
    refined_questions: Optional[List[str]] = None
    expected_output: Optional[str] = None  # For DeepEval
