"""Enumerations and constants for tool classifier system."""

from enum import Enum


class WorkflowType(Enum):
    """
    Workflow types representing different query handling strategies.

    The tool classifier uses a layer-wise approach to determine which
    workflow should handle each user query:

    - SERVICE: External service/API calls (Layer 1)
    - API_TOOL_CALLING: External API tool calling via agentic loop (Layer 2)
    - CONTEXT: Conversation history or greetings (Layer 3)
    - RAG: Knowledge base retrieval (Layer 4)
    - OOD: Out-of-domain fallback (Layer 5)
    """

    SERVICE = "service"
    API_TOOL_CALLING = "api_tool_calling"
    CONTEXT = "context"
    RAG = "rag"
    OOD = "ood"


# Layer configuration - defines the order of workflow evaluation
WORKFLOW_LAYER_ORDER = [
    WorkflowType.SERVICE,  # Layer 1: Try service first
    WorkflowType.API_TOOL_CALLING,  # Layer 2: Try API tool calling
    WorkflowType.CONTEXT,  # Layer 3: Then context
    WorkflowType.RAG,  # Layer 4: Then RAG
    WorkflowType.OOD,  # Layer 5: Finally OOD (always succeeds)
]

# Workflow display names for logging
WORKFLOW_DISPLAY_NAMES = {
    WorkflowType.SERVICE: "Service Workflow",
    WorkflowType.API_TOOL_CALLING: "API Tool Calling Workflow",
    WorkflowType.CONTEXT: "Context Workflow",
    WorkflowType.RAG: "RAG Workflow",
    WorkflowType.OOD: "Out-of-Domain Workflow",
}


class AgenticLoopStatus(str, Enum):
    """
    Status values returned by the agentic loop after each turn.

    - COMPLETED: All required parameters have been collected.
    - NEEDS_INPUT: One or more required parameters are still missing;
      a clarifying question is available for the user.
    - MAX_TURNS_REACHED: The turn limit was hit before collection completed;
      the caller should fall back gracefully.
    - AWAITING_CONTINUATION_DECISION: The continuation threshold has been reached
      with params still missing; a yes/no question is returned asking whether to
      keep collecting or fall back to the RAG workflow.
    """

    COMPLETED = "completed"
    NEEDS_INPUT = "needs_input"
    MAX_TURNS_REACHED = "max_turns_reached"
    AWAITING_CONTINUATION_DECISION = "awaiting_continuation_decision"


class ExecutionMode(str, Enum):
    """Execution mode for the API Tool Calling workflow.

    - SINGLE:   One endpoint matched — existing single-API path, no changes.
    - PARALLEL: Multiple independent endpoints matched via intent decomposition —
                params collected together, APIs called concurrently.
    """

    SINGLE = "single"
    PARALLEL = "parallel"
