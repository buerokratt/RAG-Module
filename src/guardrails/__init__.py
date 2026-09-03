"""
Guardrails package for NeMo Guardrails integration with DSPy.

This package provides:
- NeMoRailsAdapter: Main adapter for input/output guardrails
- DSPyNeMoLLM: Custom LLM provider for NeMo Guardrails using DSPy
- GuardrailCheckResult: Pydantic model for guardrail check results

Usage:
    from src.guardrails import NeMoRailsAdapter

    adapter = NeMoRailsAdapter(environment="production")
    result = adapter.check_input("user message")

    if result.allowed:
        # Process the message
    else:
        # Block the message
"""

from src.guardrails.nemo_rails_adapter import NeMoRailsAdapter, GuardrailCheckResult
from src.guardrails.dspy_nemo_adapter import DSPyNeMoLLM


__all__ = [
    "NeMoRailsAdapter",
    "GuardrailCheckResult",
    "DSPyNeMoLLM",
]
