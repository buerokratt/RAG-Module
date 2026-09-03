"""Data models for tool classifier system."""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from tool_classifier.enums import AgenticLoopStatus, WorkflowType


class ClassificationResult(BaseModel):
    """
    Result of query classification by the tool classifier.

    This model encapsulates the decision of which workflow should handle
    a user query, along with confidence score and metadata.

    Attributes:
        workflow: The workflow type that should handle this query
        confidence: Confidence score (0.0-1.0) for this classification
        metadata: Workflow-specific data (e.g., service_id, intent, entities)
        reasoning: Human-readable explanation of why this workflow was chosen
    """

    workflow: WorkflowType = Field(
        ..., description="Which workflow should handle this query"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for this classification",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Workflow-specific data passed to executor"
    )
    reasoning: Optional[str] = Field(
        default=None, description="Explanation of classification decision"
    )


class ServiceWorkflowMetadata(BaseModel):
    """
    Metadata specific to Service Workflow execution.

    TODO: Will be populated by service discovery logic with:
    - service_id: Identified service to call
    - intent: Detected user intent
    - entities: Extracted parameters for service call
    - confidence: Intent detection confidence
    """

    service_id: Optional[str] = Field(
        default=None, description="ID of the service to execute"
    )
    intent: Optional[str] = Field(
        default=None, description="Detected user intent/service name"
    )
    entities: Optional[Dict[str, Any]] = Field(
        default=None, description="Extracted entities/parameters"
    )


class ContextWorkflowMetadata(BaseModel):
    """
    Metadata specific to Context Workflow execution.

    TODO: Will be populated by context analysis logic with:
    - is_greeting: Whether query is a greeting
    - greeting_type: Type of greeting (hello, goodbye, thanks, etc.)
    - can_answer_from_history: Whether conversation history has answer
    - relevant_history_indices: Indices of relevant history items
    """

    is_greeting: bool = Field(
        default=False, description="Whether this is a greeting/conversational query"
    )
    greeting_type: Optional[str] = Field(
        default=None, description="Type of greeting: hello, goodbye, thanks, casual"
    )
    can_answer_from_history: bool = Field(
        default=False, description="Whether conversation history can answer this"
    )


@dataclass
class AgenticLoopResult:
    """
    Result returned by AgenticLoop.run_turn() after processing one conversation turn.

    Attributes:
        status: Outcome of this turn — completed, needs_input, max_turns_reached,
            or awaiting_continuation_decision.
        collected_params: All parameters collected so far (prior turns + this turn merged).
        clarifying_question: Natural-language question to show the user when status is
            NEEDS_INPUT or AWAITING_CONTINUATION_DECISION. Empty string for other statuses.
        turn_count: Updated turn counter (input turn_count + 1).
    """

    status: AgenticLoopStatus
    collected_params: Dict[str, Any]
    clarifying_question: str
    turn_count: int


@dataclass
class APICallResult:
    """
    Result returned by APICaller.call() after executing an external HTTP request.

    Attributes:
        success: True if the request succeeded (2xx status code).
        status_code: HTTP status code returned by the server. 0 when no HTTP response
            was received (network error, timeout, or circuit breaker rejection).
        response_data: Parsed JSON value on success (dict, list, or scalar); extracted
            error body on 4xx; empty string on 5xx, timeout, or network error.
        error: Human-readable error message for the user or agentic loop. None when
            success is True. Contains the raw API error body for 4xx to support
            agentic loop re-prompting; contains a localized friendly message for all
            other failure types.
    """

    success: bool
    status_code: int
    response_data: Any
    error: Optional[str]

    @property
    def is_client_error(self) -> bool:
        """True if the response was a 4xx client error."""
        return 400 <= self.status_code < 500

    @property
    def is_server_error(self) -> bool:
        """True if the response was a 5xx server error."""
        return 500 <= self.status_code < 600


@dataclass
class MultiAPICallResult:
    """
    Result returned by MultiAPICaller.call_all() after executing a batch of concurrent
    HTTP requests.

    Preserves input order: ``results[i]`` corresponds to ``endpoints[i]``.

    Attributes:
        results: One :class:`APICallResult` per endpoint, in input order.
        endpoints: Corresponding endpoint metadata dicts (url, method, call_params, …).
    """

    results: list[APICallResult]
    endpoints: list[Dict[str, Any]]

    @property
    def all_succeeded(self) -> bool:
        """True if every result in the batch has ``success=True``."""
        return all(r.success for r in self.results)

    @property
    def successful_results(self) -> list[tuple[Dict[str, Any], APICallResult]]:
        """Return ``(endpoint, result)`` pairs where ``result.success`` is True."""
        return [
            (ep, res)
            for ep, res in zip(self.endpoints, self.results, strict=True)
            if res.success
        ]

    @property
    def failed_results(self) -> list[tuple[Dict[str, Any], APICallResult]]:
        """Return ``(endpoint, result)`` pairs where ``result.success`` is False."""
        return [
            (ep, res)
            for ep, res in zip(self.endpoints, self.results, strict=True)
            if not res.success
        ]
