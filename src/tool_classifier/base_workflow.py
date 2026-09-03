"""Abstract base class for workflow executors."""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, Optional, Union

from models.request_models import (
    OrchestrationRequest,
    OrchestrationResponse,
    TestOrchestrationResponse,
)


class BaseWorkflow(ABC):
    """
    Abstract base class for all workflow executors.

    This class defines the contract that all workflow implementations must follow.
    Each workflow must implement both streaming and non-streaming execution methods.

    Design Pattern: Strategy Pattern
    - Each workflow is a concrete strategy for handling queries
    - ToolClassifier acts as the context that selects the appropriate strategy

    Workflows:
    - ServiceWorkflowExecutor: Handles external service/API calls
    - ContextWorkflowExecutor: Handles conversation history and greetings
    - RAGWorkflowExecutor: Handles knowledge base retrieval (existing)
    - OODWorkflowExecutor: Handles out-of-domain queries

    Return None Pattern:
    Workflows return None when they cannot handle a query, triggering
    fallback to the next layer in the classification chain.
    """

    @abstractmethod
    async def execute_async(
        self,
        request: OrchestrationRequest,
        context: Dict[str, Any],
        time_metric: Optional[Dict[str, float]] = None,
    ) -> Optional[Union[OrchestrationResponse, TestOrchestrationResponse]]:
        """
        Execute workflow in non-streaming mode.

        This method is called for the /orchestrate and /orchestrate/test endpoints
        which return complete responses in a single HTTP response.

        Args:
            request: The orchestration request containing user query and context
            context: Workflow-specific metadata from ClassificationResult.metadata
            time_metric: Optional dictionary for tracking step execution times

        Returns:
            OrchestrationResponse if workflow can handle this query
            None if workflow cannot handle (triggers fallback to next layer)

        Example:
            # If Service workflow detects no matching service:
            return None  # Falls back to Context workflow

            # If Service workflow successfully executes:
            return OrchestrationResponse(
                chatId=request.chatId,
                llmServiceActive=True,
                questionOutOfLLMScope=False,
                inputGuardFailed=False,
                content="EUR/USD rate is 1.0850"
            )
        """
        pass

    @abstractmethod
    async def execute_streaming(
        self,
        request: OrchestrationRequest,
        context: Dict[str, Any],
        time_metric: Optional[Dict[str, float]] = None,
    ) -> Optional[AsyncIterator[str]]:
        """
        Execute workflow in streaming mode (Server-Sent Events).

        This method is called for the /orchestrate/stream endpoint which yields
        response chunks progressively to the client.

        Args:
            request: The orchestration request containing user query and context
            context: Workflow-specific metadata from ClassificationResult.metadata
            time_metric: Optional dictionary for tracking step execution times

        Returns:
            AsyncIterator[str] yielding SSE-formatted strings if workflow can handle
            None if workflow cannot handle (triggers fallback to next layer)

        SSE Format:
            Each yielded string should be formatted as:
            'data: {"chatId": "...", "payload": {"content": "..."}, ...}\\n\\n'

        Streaming Types:
            - Real streaming (RAG): LLM generates tokens progressively
            - Simulated streaming (Service/Context): Complete response chunked for UX

        Example:
            # If Context workflow cannot answer from history:
            return None  # Falls back to RAG workflow

            # If Context workflow can answer:
            async def stream_response():
                # Validate complete response first
                answer = "The rate I mentioned was 1.08"
                is_safe = await validate_with_guardrails(answer)

                if not is_safe:
                    yield format_sse(chatId, VIOLATION_MESSAGE)
                    yield format_sse(chatId, "END")
                    return

                # Stream validated response token-by-token
                for chunk in split_into_chunks(answer):
                    yield format_sse(chatId, chunk)
                    await asyncio.sleep(0.01)

                yield format_sse(chatId, "END")

            return stream_response()
        """
        pass
