"""
Metrics module for DSPy optimization.
Contains evaluation metrics for guardrails, refiner, and generator components.

UPDATED:
- Generator uses DSPy's native SemanticF1 correctly
- Refiner uses LLM-as-Judge with ChainOfThought reasoning
"""

from .guardrails_metrics import (
    GuardrailsMetric,
    safety_weighted_accuracy,
    calculate_guardrails_stats,
)
from .refiner_metrics import (
    RefinerMetric,
    llm_judge_refinement_metric,
    FastRefinerMetric,
    calculate_refiner_stats,
    FallbackRefinerMetric,
)
from .generator_metrics import (
    GeneratorMetric,
    combined_scope_and_quality_metric,
    calculate_generator_stats,
    ScopeOnlyMetric,
)

__all__ = [
    # Guardrails
    "GuardrailsMetric",
    "safety_weighted_accuracy",
    "calculate_guardrails_stats",
    # Refiner (LLM-as-Judge)
    "RefinerMetric",
    "llm_judge_refinement_metric",
    "FastRefinerMetric",
    "FallbackRefinerMetric",
    "calculate_refiner_stats",
    # Generator (with DSPy SemanticF1)
    "GeneratorMetric",
    "combined_scope_and_quality_metric",
    "ScopeOnlyMetric",
    "calculate_generator_stats",
]
