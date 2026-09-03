"""Shared utilities for agentic loop continuation detection."""

_YES_RESPONSES = frozenset(
    {
        "yes",
        "y",
        "jah",
        "ja",
        "да",
        "ok",
        "okay",
        "sure",
        "please",
        "continue",
        "jätka",
        "продолжить",
        "absolutely",
    }
)
"""Normalised affirmative responses recognised across Estonian, English, and Russian.

Any response that is not in this set is treated as a "no" so the loop falls
back to the RAG workflow.
"""


def detect_continuation_response(user_message: str) -> bool:
    """Detect whether the user's message indicates they want to continue.

    Checks the normalised (lower-cased, stripped) message against a set of
    known affirmative responses in Estonian, English, and Russian.
    Any response that is not clearly affirmative is treated as a "no" so
    the loop falls back to the RAG workflow.

    Args:
        user_message: The raw user message to inspect.

    Returns:
        True if the user wants to continue, False otherwise.
    """
    normalised = user_message.strip().lower()
    return normalised in _YES_RESPONSES
