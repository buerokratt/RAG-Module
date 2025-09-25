"""Pytest configuration and fixtures."""

import sys
import os
import pytest
from pathlib import Path
from typing import Dict, Generator
from testcontainers.vault import VaultContainer
from testcontainers.core.wait_strategies import LogMessageWaitStrategy
from loguru import logger
import hvac


# Add src directory to Python path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture(scope="session")
def vault_container() -> Generator[VaultContainer, None, None]:
    """Create a Vault container for testing with modern wait strategies."""
    container = VaultContainer()

    container.waiting_for(
        LogMessageWaitStrategy("Vault server started!")
        .with_startup_timeout(60)
        .with_poll_interval(0.5)
    )

    container.start()
    try:
        yield container
    finally:
        container.stop()


@pytest.fixture(scope="session")
def vault_client(vault_container: VaultContainer) -> hvac.Client:
    """Get the Vault client."""
    vault_url = vault_container.get_connection_url()
    return hvac.Client(url=vault_url, token=vault_container.root_token)


@pytest.fixture(scope="session")
def populated_vault(vault_client: hvac.Client) -> None:
    """Populate Vault with test data using Connection model structure."""
    from datetime import datetime

    test_data = {
        "users/testuser/aws_bedrock/credentials": {
            "metadata": {
                "id": "conn_aws_prod_01",
                "name": "AWS Bedrock Production",
                "description": "Production AWS Bedrock connection",
                "provider": "aws_bedrock",
                "environment": "production",
                "created_by": "testuser",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "last_used": None,
                "usage_count": 0,
                "tags": ["production", "aws"],
                "is_active": True,
                "is_default": False,
            },
            "connection_data": {
                "region": "us-east-1",
                "access_key_id": "AKIA...",
                "secret_access_key": "test-secret-key",
                "session_token": None,
            },
        },
        "users/testuser/azure_openai/credentials": {
            "metadata": {
                "id": "conn_azure_prod_01",
                "name": "Azure OpenAI Production",
                "description": "Production Azure OpenAI connection",
                "provider": "azure_openai",
                "environment": "production",
                "created_by": "testuser",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "last_used": None,
                "usage_count": 0,
                "tags": ["production", "azure"],
                "is_active": True,
                "is_default": False,
            },
            "connection_data": {
                "endpoint": "https://test.openai.azure.com/",
                "api_key": "test-azure-api-key",
                "deployment_name": "gpt-4",
                "api_version": "2025-01-01-preview",
            },
        },
    }

    for path, data in test_data.items():
        try:
            vault_client.secrets.kv.v2.create_or_update_secret(path=path, secret=data)
            logger.debug(f"Created test secret at {path}")
        except Exception as e:
            logger.error(f"Failed to create secret at {path}: {e}")
            raise


@pytest.fixture
def vault_env_vars(
    vault_container: VaultContainer, populated_vault: None
) -> Generator[Dict[str, str], None, None]:
    """Set environment variables for Vault access."""
    env_vars: Dict[str, str] = {
        "VAULT_ADDR": vault_container.get_connection_url(),
        "VAULT_URL": vault_container.get_connection_url(),
        "VAULT_TOKEN": vault_container.root_token,
        "ENVIRONMENT": "production",
    }

    for key, value in env_vars.items():
        os.environ[key] = value

    try:
        yield env_vars
    finally:
        for key in env_vars.keys():
            os.environ.pop(key, None)


@pytest.fixture(autouse=True)
def reset_singletons() -> Generator[None, None, None]:
    """Reset singleton instances between tests."""

    # Reset LLMManager
    from src.llm_config_module.llm_manager import LLMManager

    if hasattr(LLMManager, "_instance"):
        LLMManager._instance = None

    # Reset VaultConnectionManager if available
    try:
        from src.rag_config_manager.vault.connection_manager import (
            ConnectionManager as VaultConnectionManager,
        )

        if hasattr(VaultConnectionManager, "_instance"):
            VaultConnectionManager._instance = None
    except ImportError:
        pass

    yield

    # Clean up again after test
    if hasattr(LLMManager, "_instance"):
        LLMManager._instance = None
    try:
        from src.rag_config_manager.vault.connection_manager import (
            ConnectionManager as VaultConnectionManager,
        )

        if hasattr(VaultConnectionManager, "_instance"):
            VaultConnectionManager._instance = None
    except ImportError:
        pass
