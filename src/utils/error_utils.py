"""Error tracking and sanitization utilities."""

from datetime import datetime
import random
import string
from typing import Optional, Dict, Any


def generate_error_id() -> str:
    """
    Generate unique error ID for tracking.
    Format: ERR-YYYYMMDD-HHMMSS-XXXX

    Example: ERR-20251123-143022-A7F3

    Returns:
        str: Unique error ID with timestamp and random suffix
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    random_code = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"ERR-{timestamp}-{random_code}"


def log_error_with_context(
    logger: Any,  # noqa: ANN401 - loguru logger type is complex, use Any
    error_id: str,
    stage: str,
    chat_id: Optional[str],
    exception: Exception,
    extra_context: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log error with full context for internal tracking.

    This function logs complete error details internally (including stack traces)
    while ensuring no sensitive information is exposed to clients.

    Args:
        logger: Logger instance (loguru or standard logging)
        error_id: Generated error ID for correlation
        stage: Pipeline stage where error occurred (e.g., "prompt_refinement", "streaming")
        chat_id: Chat session ID (can be None for non-request errors)
        exception: The exception that occurred
        extra_context: Additional context dictionary (optional)

    Example:
        log_error_with_context(
            logger,
            "ERR-20251123-143022-A7F3",
            "streaming_generation",
            "abc123",
            TimeoutError("LLM timeout"),
            {"duration": 120.5, "model": "gpt-4"}
        )

    Log Output:
        [ERR-20251123-143022-A7F3] Error in streaming_generation for chat abc123: TimeoutError
          Stage: streaming_generation
          Chat ID: abc123
          Error Type: TimeoutError
          Error Message: LLM timeout
          Duration: 120.5
          Model: gpt-4
          [Full stack trace here]
    """
    context = {
        "error_id": error_id,
        "stage": stage,
        "chat_id": chat_id or "unknown",
        "error_type": type(exception).__name__,
        "error_message": str(exception),
    }

    if extra_context:
        context.update(extra_context)

    # Format log message with error ID
    log_message = (
        f"[{error_id}] Error in {stage}"
        f"{f' for chat {chat_id}' if chat_id else ''}: "
        f"{type(exception).__name__}"
    )

    # Log with full context and stack trace
    # exc_info=True ensures stack trace is logged to file, NOT sent to client
    logger.error(log_message, extra=context, exc_info=True)
