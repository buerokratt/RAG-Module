from __future__ import annotations

from typing import (
    Any,
    Iterable,
    List,
    Mapping,
    Sequence,
    Optional,
    Dict,
    Union,
    Protocol,
)

import logging
import dspy

from llm_config_module import LLMManager, LLMProvider


LOGGER = logging.getLogger(__name__)


# Protocol for DSPy History objects
class DSPyHistoryProtocol(Protocol):
    messages: Any


DSPyOutput = Union[str, Sequence[str], Sequence[Any], None]
HistoryList = Sequence[Mapping[str, str]]
# Use Protocol for DSPy History objects instead of Any
HistoryLike = Union[HistoryList, DSPyHistoryProtocol]


# 1. SIGNATURE: Defines the interface for the DSPy module
class PromptRefineSig(dspy.Signature):
    """Produce N distinct, concise rewrites of the user's question using chat history.

    Constraints:
    - Preserve the original intent; don't inject unsupported constraints.
    - Resolve pronouns with context when safe; avoid changing semantics.
    - Prefer explicit, searchable phrasing (entities, dates, units).
    - Make each rewrite meaningfully distinct.
    - Return exactly N items.
    """

    history = dspy.InputField(desc="Recent conversation history (turns).")
    question = dspy.InputField(desc="The user's latest question to refine.")
    n = dspy.InputField(desc="Number of rewrites to produce (N).")

    rewrites: List[str] = dspy.OutputField(
        desc="Exactly N refined variations of the question, each a single sentence."
    )


def _coerce_to_list(value: DSPyOutput) -> list[str]:
    """Coerce model output into a list[str] safely."""
    if isinstance(value, (list, tuple)):  # Handle sequences
        # Ensure elements are strings
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        lines = [ln.strip() for ln in value.splitlines() if ln.strip()]
        cleaned: list[str] = []
        for ln in lines:
            s = ln.lstrip("•*-—-").strip()
            while s and (s[0].isdigit() or s[0] in ".)]"):
                s = s[1:].lstrip()
            if s:
                cleaned.append(s)
        return cleaned
    return []


def _dedupe_keep_order(items: Iterable[str], limit: int) -> list[str]:
    """Deduplicate case-insensitively, keep order, truncate to limit."""
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        key = it.strip().rstrip(".").lower()
        if key and key not in seen:
            seen.add(key)
            out.append(it.strip().rstrip("."))
            if len(out) >= limit:
                break
    return out


def _validate_inputs(question: str, n: int) -> None:
    """Validate inputs with clear errors (Sonar: no magic, explicit checks)."""
    if not question.strip():
        raise ValueError("`question` must be a non-empty string.")
    if n <= 0:
        raise ValueError("`n` must be a positive integer.")


def _is_history_like(history: HistoryLike) -> bool:
    """Accept dspy.History or list[{'role': str, 'content': str}] to stay flexible."""

    # Case 1: Object with `messages` attribute (e.g., dspy.History)
    if hasattr(history, "messages"):
        return True

    # Case 2: Sequence of dict-like items
    if isinstance(history, Sequence) and not isinstance(history, str):
        return _validate_history_sequence(history)

    return False


def _validate_history_sequence(history: Sequence[Mapping[str, str]]) -> bool:
    """Helper function to validate history sequence structure."""
    try:
        for item in history:
            # Check if required keys exist
            if "role" not in item or "content" not in item:
                return False
        return True
    except (KeyError, TypeError):
        return False


# 3. MODULE: Uses the signature + adds logic
class PromptRefinerAgent(dspy.Module):
    """Config-driven Prompt Refiner that emits N rewrites from history + question.

    This module uses the LLMManager to access configured providers and configures
    DSPy globally via the manager's configure_dspy method.

    Parameters
    ----------
    config_path : str, optional
        Path to the YAML configuration file. If None, uses default config.
    provider : LLMProvider, optional
        Specific provider to use. If None, uses default provider from config.
    default_n : int
        Fallback number of rewrites when `n` not provided in `forward`.
    llm_manager : LLMManager, optional
        Existing LLMManager instance to reuse. If provided, config_path is ignored.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        provider: Optional[LLMProvider] = None,
        default_n: int = 5,
        llm_manager: Optional[LLMManager] = None,
    ) -> None:
        super().__init__()  # type: ignore
        if default_n <= 0:
            raise ValueError("`default_n` must be a positive integer.")

        self._default_n = int(default_n)

        # Use existing LLMManager if provided, otherwise create new one
        if llm_manager is not None:
            self._manager = llm_manager
            LOGGER.debug("PromptRefinerAgent using provided LLMManager instance.")
        else:
            self._manager = LLMManager(config_path)
            LOGGER.debug("PromptRefinerAgent created new LLMManager instance.")

        self._manager.configure_dspy(provider)

        provider_info = self._manager.get_provider_info(provider)
        LOGGER.debug(
            "PromptRefinerAgent configured with provider '%s'.",
            provider_info.get("provider", "unknown"),
        )

        # Use ChainOfThought for better reasoning before output fields
        self._predictor = dspy.ChainOfThought(PromptRefineSig)

    def forward(
        self,
        history: Sequence[Mapping[str, str]] | Any,
        question: str,
        n: int | None = None,
    ) -> list[str]:
        """Return up to N refined variants (exactly N when possible).

        `history` can be a DSPy History or a list of {role, content}.
        """
        k = int(n) if n is not None else self._default_n
        _validate_inputs(question, k)

        if not _is_history_like(history):
            raise ValueError(
                "`history` must be a dspy.History or a sequence of {'role','content'}."
            )

        # Primary prediction
        result = self._predictor(history=history, question=question, n=k)
        rewrites = _coerce_to_list(getattr(result, "rewrites", []))
        deduped = _dedupe_keep_order(rewrites, k)

        if len(deduped) == k:
            return deduped

        # If short, ask for a few more variants to top up
        missing = k - len(deduped)
        if missing > 0:
            follow = self._predictor(
                history=history,
                question=f"Create {missing} additional, *new* paraphrases of: {question}",
                n=missing,
            )
            extra = _coerce_to_list(getattr(follow, "rewrites", []))
            combined = _dedupe_keep_order(deduped + extra, k)
            return combined

        return deduped

    def forward_structured(
        self,
        history: Sequence[Mapping[str, str]] | Any,
        question: str,
        n: int | None = None,
    ) -> Dict[str, Any]:
        """Return structured output with original question and refined variants.

        Returns dictionary in format:
        {
            "original_question": "original question text",
            "refined_questions": ["variant1", "variant2", ...]
        }

        Args:
            history: Conversation history (DSPy History or list of {role, content})
            question: Original user question to refine
            n: Number of variants to generate (uses default_n if None)

        Returns:
            Dictionary with original_question and refined_questions
        """
        # Get refined variants using existing forward method
        refined_variants = self.forward(history, question, n)

        # Return structured format
        return {"original_question": question, "refined_questions": refined_variants}
