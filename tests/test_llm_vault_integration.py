#!/usr/bin/env python3
"""Test script for LLM Config Module with Vault integration using Testcontainers."""

import sys
from pathlib import Path
import pytest
from typing import Dict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from loguru import logger
from src.llm_config_module.llm_manager import LLMManager


# Configure loguru
logger.remove()  # Remove default handler
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)


def test_production_environment(vault_env_vars: Dict[str, str]) -> None:
    """Test LLM manager with production environment using Testcontainers."""
    logger.info("Testing LLM Manager with production environment...")

    # Reset singleton for fresh test
    LLMManager.reset_instance()

    # Initialize LLM Manager for production
    llm_manager = LLMManager(environment="production")

    logger.success("LLM Manager initialized successfully for production")

    # Try to get a provider
    providers = llm_manager.get_available_providers()
    logger.info(f"Available providers: {providers}")

    # Assert that we got providers as a dictionary
    assert isinstance(providers, dict), "Providers should be a dictionary"
    assert len(providers) > 0, "Should have at least one provider configured"


def test_development_environment(vault_env_vars: Dict[str, str]) -> None:
    """Test LLM manager with development environment using Testcontainers."""
    logger.info("Testing LLM Manager with development environment...")

    # Reset singleton for fresh test
    LLMManager.reset_instance()

    # For development environment, test with valid connection ID from test data
    test_connection_id = "conn_azure_prod_01"

    try:
        # Initialize LLM Manager for development
        llm_manager = LLMManager(
            environment="development", connection_id=test_connection_id
        )

        logger.success("LLM Manager initialized successfully for development")

        # Try to get a provider
        providers = llm_manager.get_available_providers()
        logger.info(f"Available providers: {providers}")

        # Assert that we got providers as a dictionary
        assert isinstance(providers, dict), "Providers should be a dictionary"
        assert "azure_openai" in providers, (
            "Azure OpenAI provider should be available for conn_azure_prod_01 connection"
        )

    except Exception as e:
        logger.error(f"Development test failed unexpectedly: {e}")
        raise


def test_invalid_connection_id(vault_env_vars: Dict[str, str]) -> None:
    """Test that invalid connection_id fails properly."""
    logger.info("Testing LLM Manager with invalid connection ID...")

    # Reset singleton for fresh test
    LLMManager.reset_instance()

    with pytest.raises(Exception):  # Should fail with invalid connection
        LLMManager(environment="development", connection_id="invalid-connection-12345")

    logger.success("Invalid connection ID properly rejected")


def test_missing_connection_id(vault_env_vars: Dict[str, str]) -> None:
    """Test that missing connection_id in development fails properly."""
    logger.info("Testing LLM Manager with missing connection ID...")

    # Reset singleton for fresh test
    LLMManager.reset_instance()

    with pytest.raises(Exception):  # Should fail without connection_id
        LLMManager(environment="development")

    logger.success("Missing connection ID properly rejected")


if __name__ == "__main__":
    logger.info(
        "This test file is designed to run with pytest and Testcontainers fixtures"
    )
    logger.info("Run with: pytest tests/test_llm_vault_integration.py -v")
