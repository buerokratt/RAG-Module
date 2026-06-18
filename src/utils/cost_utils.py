"""Cost calculation utilities for LLM usage tracking."""

from typing import Dict, Any, List, Tuple
import logging
import dspy

logger = logging.getLogger(__name__)


def _to_float(value: str | int | float | bytes | bytearray | None) -> float:
    """Best-effort float conversion for cost values."""
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _extract_cost_with_fallback(
    item: Dict[str, Any], usage: Dict[str, Any]
) -> Tuple[float, str]:
    """Extract cost from history entry with streaming-safe fallbacks."""
    # Primary source used by DSPy for non-streaming calls.
    item_cost = _to_float(item.get("cost"))
    if item_cost > 0.0:
        return item_cost, "item.cost"

    # Some providers put cost directly into usage for streaming responses.
    usage_cost = _to_float(usage.get("cost")) if isinstance(usage, dict) else 0.0
    if usage_cost > 0.0:
        return usage_cost, "usage.cost"

    # Final fallback: estimate from model + tokens when available.
    prompt_tokens = int(usage.get("prompt_tokens", 0)) if isinstance(usage, dict) else 0
    completion_tokens = (
        int(usage.get("completion_tokens", 0)) if isinstance(usage, dict) else 0
    )
    model_name = item.get("model")

    if not model_name or (prompt_tokens == 0 and completion_tokens == 0):
        return 0.0, "missing_model_or_tokens"

    try:
        from litellm.cost_calculator import cost_per_token

        input_cost, output_cost = cost_per_token(
            model=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        estimated_cost = input_cost + output_cost
        return _to_float(estimated_cost), "litellm.cost_per_token"
    except Exception as e:
        logger.debug(f"Cost fallback failed for model '{model_name}': {e}")
        return 0.0, "fallback_error"


def extract_cost_from_lm_history(lm_history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract cost and usage information from LM history.

    Args:
        lm_history: List of LM history items from dspy.LM.history

    Returns:
        Dictionary containing:
            - total_cost: Total cost in dollars
            - total_prompt_tokens: Total input tokens
            - total_completion_tokens: Total output tokens
            - total_tokens: Total tokens used
            - num_calls: Number of LM calls
    """
    total_cost = 0.0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0
    num_calls = 0

    try:
        for item in lm_history:
            num_calls += 1

            # Extract usage information
            usage = item.get("usage", {})

            # Extract cost with fallback path for streaming entries.
            entry_cost, _ = _extract_cost_with_fallback(item, usage)
            total_cost += entry_cost

            if usage:
                total_prompt_tokens += usage.get("prompt_tokens", 0)
                total_completion_tokens += usage.get("completion_tokens", 0)
                total_tokens += usage.get("total_tokens", 0)

    except Exception as e:
        logger.error(f"Error extracting cost from LM history: {str(e)}")

    return {
        "total_cost": round(total_cost, 6),
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_tokens": total_tokens,
        "num_calls": num_calls,
    }


def calculate_total_costs(component_costs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate total costs across all components.

    Args:
        component_costs: Dictionary mapping component names to their cost dictionaries

    Returns:
        Dictionary containing aggregate totals
    """
    total = {
        "total_cost": 0.0,
        "total_prompt_tokens": 0,
        "total_completion_tokens": 0,
        "total_tokens": 0,
        "total_calls": 0,
    }

    try:
        for costs in component_costs.values():
            total["total_cost"] += costs.get("total_cost", 0.0)
            total["total_prompt_tokens"] += costs.get("total_prompt_tokens", 0)
            total["total_completion_tokens"] += costs.get("total_completion_tokens", 0)
            total["total_tokens"] += costs.get("total_tokens", 0)
            total["total_calls"] += costs.get("num_calls", 0)

        total["total_cost"] = round(total["total_cost"], 6)

    except Exception as e:
        logger.error(f"Error calculating total costs: {str(e)}")

    return total


def get_lm_usage_since(history_length_before: int) -> Dict[str, Any]:
    """
    Extract usage information from LM history since a specific point.

    Args:
        history_length_before: The history length to measure from

    Returns:
        Dictionary containing usage statistics
    """
    usage_info = get_default_usage_dict()

    try:
        lm = dspy.settings.lm
        if lm and hasattr(lm, "history"):
            new_history = lm.history[history_length_before:]
            usage_info = extract_cost_from_lm_history(new_history)
    except Exception as e:
        logger.warning(f"Failed to extract usage info: {str(e)}")

    return usage_info


def get_default_usage_dict() -> Dict[str, Any]:
    """
    Return a default usage dictionary with zero values.

    Returns:
        Dictionary with default usage values
    """
    return {
        "total_cost": 0.0,
        "total_prompt_tokens": 0,
        "total_completion_tokens": 0,
        "total_tokens": 0,
        "num_calls": 0,
    }
