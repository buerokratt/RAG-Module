# src/guardrails/rails_config.py
"""
Guardrails configuration loader for NeMo's Colang format.
"""

from pathlib import Path

# Get the path to the YAML file relative to this module
RAILS_CONFIG_PATH = Path(__file__).parent / "rails_config.yaml"
