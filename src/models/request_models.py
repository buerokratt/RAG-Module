"""Pydantic models for API requests and responses."""

from typing import List, Literal, Optional
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
