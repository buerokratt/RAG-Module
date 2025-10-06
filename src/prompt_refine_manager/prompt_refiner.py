from __future__ import annotations

from typing import Any, Sequence, Optional, Dict, Union, cast, List
import logging
import dspy
from pydantic import BaseModel, Field

from llm_orchestrator_config import LLMManager, LLMProvider
from src.utils.cost_utils import get_lm_usage_since

LOGGER = logging.getLogger(__name__)


class ConversationHistory(BaseModel):
    """Pydantic model for conversation history data."""

    messages: List[Dict[str, Any]] = Field(
        ..., description="List of conversation messages"
    )


HistoryList = Sequence[Dict[str, str]]
HistoryLike = Union[HistoryList, ConversationHistory]


class PromptRefiner(dspy.Signature):
    """Produce N distinct, concise rewrites of the user's question using chat history.

    Constraints:
    - Preserve the original intent; don't inject unsupported constraints.
    - Resolve pronouns with context when safe; avoid changing semantics.
    - Prefer explicit, searchable phrasing (entities, dates, units).
    - Make each rewrite meaningfully distinct.
    - Return exactly N items as a valid JSON list.
    """

    history: str = dspy.InputField(desc="Recent conversation history (turns).")
    question: str = dspy.InputField(desc="The user's latest question to refine.")
    n: int = dspy.InputField(desc="Number of rewrites to produce (N).")

    rewrites: list[str] = dspy.OutputField(
        desc="Exactly N refined variations of the question, each a single sentence."
    )


def _validate_inputs(question: str, n: int) -> None:
    """Validate input parameters."""
    if not question.strip():
        raise ValueError("`question` must be a non-empty string.")
    if n <= 0:
        raise ValueError("`n` must be a positive integer.")


def _is_history_like(history: HistoryLike) -> bool:
    """Check if history is in valid format."""
    if hasattr(history, "messages"):
        return True
    if isinstance(history, Sequence) and not isinstance(history, str):
        return _validate_history_sequence(history)
    return False


def _validate_history_sequence(history: Sequence[Dict[str, str]]) -> bool:
    """Validate that history sequence has proper structure."""
    try:
        for item in history:
            if "role" not in item or "content" not in item:
                return False
        return True
    except (KeyError, TypeError):
        return False


def _format_history(history: HistoryLike) -> str:
    """Convert history to a string format suitable for the LM."""
    if hasattr(history, "messages"):
        # Handle DSPy History object
        messages = getattr(history, "messages", [])
        return "\n".join(
            f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
            for msg in messages
        )
    elif isinstance(history, Sequence):
        return "\n".join(
            f"{turn.get('role', 'unknown')}: {turn.get('content', '')}"
            for turn in history
        )
    return str(history)


def _dedupe_keep_order(items: list[str], limit: int) -> list[str]:
    """Deduplicate case-insensitively, keep order, truncate to limit."""
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        # Normalize for comparison
        key = it.strip().rstrip(".?!").lower()
        if key and key not in seen:
            seen.add(key)
            out.append(it.strip())
            if len(out) >= limit:
                break
    return out


class PromptRefinerAgent(dspy.Module):
    """Config-driven Prompt Refiner that emits N rewrites from history + question.

    Uses DSPy 2.5+ best practices with proper structured outputs and adapters.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        provider: Optional[LLMProvider] = None,
        default_n: int = 5,
        llm_manager: Optional[LLMManager] = None,
        use_json_adapter: bool = True,
    ) -> None:
        super().__init__()
        if default_n <= 0:
            raise ValueError("`default_n` must be a positive integer.")

        self._default_n = int(default_n)

        if llm_manager is not None:
            self._manager = llm_manager
            LOGGER.debug("PromptRefinerAgent using provided LLMManager instance.")
        else:
            self._manager = LLMManager(config_path)

        self._provider = provider
        self._use_json_adapter = use_json_adapter

        # Use ChainOfThought for better reasoning about how to rewrite
        self._predictor = dspy.Predict(PromptRefiner)

    def _get_adapter_context(self):
        """Return appropriate adapter context manager."""
        if self._use_json_adapter:
            return dspy.context(adapter=dspy.JSONAdapter())
        return dspy.context(adapter=dspy.ChatAdapter())

    def forward(
        self,
        history: Sequence[Dict[str, str]] | Any,
        question: str,
        n: int | None = None,
    ) -> list[str]:
        """Generate N refined versions of the question.

        Args:
            history: Conversation history (DSPy History or list of dicts)
            question: Original question to refine
            n: Number of rewrites (defaults to default_n)

        Returns:
            List of refined question strings
        """
        k = int(n) if n is not None else self._default_n
        _validate_inputs(question, k)

        if not _is_history_like(history):
            raise ValueError(
                "`history` must be a dspy.History or a sequence of {'role','content'}."
            )

        # Format history for the LM
        history_str = _format_history(history)

        # Use appropriate adapter and provider
        with self._get_adapter_context():
            with self._manager.use_task_local(self._provider):
                result = self._predictor(history=history_str, question=question, n=k)

        # Extract rewrites - DSPy should handle parsing automatically
        rewrites = cast(Optional[list[str]], getattr(result, "rewrites", None))

        # If rewrites is already a list, use it directly
        if isinstance(rewrites, list):
            # Clean up the rewrites
            cleaned = [str(r).strip() for r in rewrites if str(r).strip()]
            deduped = _dedupe_keep_order(cleaned, k)

            # If we got enough, return them
            if len(deduped) >= k:
                return deduped[:k]

            # If not enough, try one more time with explicit instruction
            LOGGER.warning(
                f"Only got {len(deduped)} rewrites, expected {k}. Retrying..."
            )

            with self._get_adapter_context():
                with self._manager.use_task_local(self._provider):
                    # Use a fresh rollout to bypass cache
                    retry_result = self._predictor(
                        history=history_str,
                        question=question,
                        n=k,
                        config={"rollout_id": 1, "temperature": 0.8},
                    )

            retry_rewrites = cast(list[str], getattr(retry_result, "rewrites", []))
            all_rewrites = cleaned + [str(r).strip() for r in retry_rewrites]
            deduped = _dedupe_keep_order(all_rewrites, k)
            return deduped[:k]

        # Fallback: if parsing failed or result is not a list
        LOGGER.error(
            f"Failed to get proper list output. Got type: {type(rewrites)}, "
            f"value: {str(rewrites)}"
        )
        # Return original question as fallback
        return [question]

    def forward_structured(
        self,
        history: Sequence[Dict[str, str]] | Any,
        question: str,
        n: int | None = None,
    ) -> Dict[str, Any]:
        """Generate refined questions and return structured output with usage info.

        Returns:
            Dict with 'original_question', 'refined_questions', and 'usage' keys
        """
        # Record history length before operation
        lm = dspy.settings.lm
        history_length_before = len(lm.history) if lm and hasattr(lm, "history") else 0

        # Perform refinement
        refined = self.forward(history, question, n)

        # Extract usage using centralized utility
        usage_info = get_lm_usage_since(history_length_before)

        return {
            "original_question": question,
            "refined_questions": refined,
            "usage": usage_info,
        }
