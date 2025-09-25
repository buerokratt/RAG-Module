"""Test LLM Config Module integration with Vault using Testcontainers."""

import os
import pytest
from pathlib import Path
from typing import Dict
from src.llm_config_module.llm_manager import LLMManager
from src.llm_config_module.exceptions import ConfigurationError


class TestVaultIntegration:
    """Test suite for vault integration using Testcontainers."""

    def setup_method(self):
        """Setup for each test method."""
        # Reset the singleton instance to ensure each test gets a fresh instance
        LLMManager.reset_instance()

        self.cfg_path = (
            Path(__file__).parent.parent
            / "src"
            / "llm_config_module"
            / "config"
            / "llm_config.yaml"
        )
        assert self.cfg_path.exists(), f"llm_config.yaml not found at {self.cfg_path}"

    def test_production_environment_initialization(
        self, vault_env_vars: Dict[str, str]
    ) -> None:
        """Test that production environment initializes correctly with Testcontainers vault."""
        manager = LLMManager(config_path=str(self.cfg_path), environment="production")

        # Should successfully initialize with vault connections
        providers = manager.get_available_providers()
        assert isinstance(providers, dict)
        assert len(providers) > 0, "Should have at least one provider configured"

        print(
            f"Production environment initialized with providers: {list(providers.keys())}"
        )

    def test_development_environment_requires_connection_id(
        self, vault_env_vars: Dict[str, str]
    ) -> None:
        """Test that development environment requires connection_id."""
        with pytest.raises(
            ConfigurationError, match=r".*connection_id is required.*development"
        ):
            LLMManager(
                config_path=str(self.cfg_path),
                environment="development",
                # Missing connection_id parameter
            )

    def test_valid_connection_id_works(self, vault_env_vars: Dict[str, str]) -> None:
        """Test that valid connection_id works in development environment."""
        # First get available connections
        manager = LLMManager(config_path=str(self.cfg_path), environment="production")
        providers = manager.get_available_providers()

        if providers:
            # Reset and try development mode with actual connection ID from vault
            LLMManager.reset_instance()
            provider_name = list(providers.keys())[0]

            # Use the actual connection IDs from our vault data
            connection_id = (
                "conn_azure_prod_01"
                if provider_name == "azure_openai"
                else "conn_aws_prod_01"
            )

            dev_manager = LLMManager(
                config_path=str(self.cfg_path),
                environment="development",
                connection_id=connection_id,
            )

            dev_providers = dev_manager.get_available_providers()
            assert provider_name in dev_providers
            print(f"Development environment works with connection_id: {connection_id}")

    def test_invalid_connection_id_fails(self, vault_env_vars: Dict[str, str]) -> None:
        """Test that invalid connection_id causes failure."""
        with pytest.raises(
            ConfigurationError,
            match=r".*(Connection not found|Failed to discover providers)",
        ):
            LLMManager(
                config_path=str(self.cfg_path),
                environment="development",
                connection_id="invalid-connection-id-12345",
            )

    def test_vault_configuration_loaded(self, vault_env_vars: Dict[str, str]) -> None:
        """Test that vault configuration is properly loaded."""
        manager = LLMManager(config_path=str(self.cfg_path), environment="production")

        # Access the configuration through public method
        config = manager.get_configuration()
        assert config is not None, "Configuration should be loaded"
        assert config.vault is not None, "Vault configuration should be loaded"
        assert config.vault.enabled is True, "Vault should be enabled"
        assert config.vault.url is not None, "Vault URL should be configured"
        assert config.vault.url != "", "Vault URL should not be empty"

        print("Vault configuration properly loaded")

    def test_environment_variable_substitution_in_vault_config(
        self, vault_env_vars: Dict[str, str]
    ) -> None:
        """Test that environment variables in vault config are properly substituted."""
        manager = LLMManager(config_path=str(self.cfg_path), environment="production")

        config = manager.get_configuration()
        assert config is not None, "Configuration should be loaded"
        assert config.vault is not None, "Vault configuration should be loaded"
        assert config.vault.url == vault_env_vars["VAULT_URL"], (
            f"Expected vault URL {vault_env_vars['VAULT_URL']}, got {config.vault.url}"
        )

        print("Environment variable substitution working")

    def test_aws_provider_configuration(self, vault_env_vars: Dict[str, str]) -> None:
        """Test that AWS provider can be configured from vault."""
        manager = LLMManager(config_path=str(self.cfg_path), environment="production")

        providers = manager.get_available_providers()

        if "aws" in [
            str(k) for k in providers.keys()
        ]:  # Convert to string for comparison
            aws_config = providers[next(k for k in providers.keys() if str(k) == "aws")]
            assert aws_config is not None
            print("AWS provider successfully configured from vault")
        else:
            print("AWS provider not available in vault test data")

    def test_azure_provider_configuration(self, vault_env_vars: Dict[str, str]) -> None:
        """Test that Azure provider can be configured from vault."""
        manager = LLMManager(config_path=str(self.cfg_path), environment="production")

        providers = manager.get_available_providers()

        if "azure" in [
            str(k) for k in providers.keys()
        ]:  # Convert to string for comparison
            azure_config = providers[
                next(k for k in providers.keys() if str(k) == "azure")
            ]
            assert azure_config is not None
            print("Azure provider successfully configured from vault")
        else:
            print("Azure provider not available in vault test data")


def test_vault_unavailable_fallback() -> None:
    """Test behavior when vault is unavailable (no fixtures used)."""
    cfg_path = (
        Path(__file__).parent.parent
        / "src"
        / "llm_config_module"
        / "config"
        / "llm_config.yaml"
    )

    # Clear any vault environment variables to ensure clean test
    vault_env_vars = ["VAULT_ADDR", "VAULT_URL", "VAULT_TOKEN", "ENVIRONMENT"]
    original_values: Dict[str, str | None] = {}
    for var in vault_env_vars:
        original_values[var] = os.environ.get(var)
        if var in os.environ:
            del os.environ[var]

    # Also clear any AWS/Azure credentials that might provide fallback
    aws_azure_vars = [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
    ]
    for var in aws_azure_vars:
        if var in os.environ:
            original_values[var] = os.environ.get(var)
            del os.environ[var]

    LLMManager.reset_instance()

    try:
        # Set vault URL to an unreachable address and empty token to force failure
        os.environ["VAULT_ADDR"] = "http://localhost:99999"  # Invalid port
        os.environ["VAULT_TOKEN"] = ""

        # This should fail since vault is unreachable and token is empty
        with pytest.raises(
            ConfigurationError,
            match=r".*(Vault URL and token must be provided|Failed to load LLM configuration|No production connections found|Connection refused|Failed to connect|must be provided.*configuration.*environment)",
        ):
            LLMManager(config_path=str(cfg_path), environment="production")

        print("System properly fails when vault unavailable (as expected)")
    finally:
        # Clean up and restore original environment variables
        for var in ["VAULT_ADDR", "VAULT_TOKEN"]:
            if var in os.environ:
                del os.environ[var]

        for var, value in original_values.items():
            if value is not None:
                os.environ[var] = value
            elif var in os.environ:
                del os.environ[var]
