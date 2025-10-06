"""Cost calculation utilities for LLM usage tracking."""

from typing import Dict, Any, List
import logging
import dspy

logger = logging.getLogger(__name__)


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

            # Extract cost (may be None or 0 for some providers)
            cost = item.get("cost", 0.0)
            if cost is not None:
                total_cost += float(cost)

            # Extract usage information
            usage = item.get("usage", {})
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
