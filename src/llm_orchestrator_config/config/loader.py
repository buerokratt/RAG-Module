"""Configuration loader for the LLM Config Module."""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, cast

import yaml
from dotenv import load_dotenv
from loguru import logger

from llm_orchestrator_config.config.schema import (
    LLMConfiguration,
    ProviderConfig,
    AzureOpenAIConfig,
    AWSBedrockConfig,
    VaultConfig,
)
from llm_orchestrator_config.vault.secret_resolver import SecretResolver
from llm_orchestrator_config.types import LLMProvider
from llm_orchestrator_config.exceptions import ConfigurationError, InvalidConfigurationError

# Constants
DEFAULT_CONFIG_FILENAME = "llm_config.yaml"

# Type alias for configuration values that can be processed
ConfigValue = Union[str, Dict[str, Any], List[Any], int, float, bool, None]


class ConfigurationLoader:
    """Loads and processes LLM configuration from YAML files with environment variable support."""

    def __init__(
        self,
        config_path: Optional[str] = None,
        environment: str = "development",
        connection_id: Optional[str] = None,
    ) -> None:
        """Initialize the configuration loader.

        Args:
            config_path: Path to the configuration file. If None, uses default location.
            environment: Environment type ("production", "development", "test")
            connection_id: Connection ID (required for development/test environments)
        """
        # Load environment variables from .env file if it exists
        self._load_environment_variables()

        self.config_path = self._resolve_config_path(config_path)
        self.environment = environment
        self.connection_id = connection_id

    def _load_environment_variables(self) -> None:
        """Load environment variables from .env file if it exists."""
        try:
            # Look for .env file in the project root
            # Start from the config file's directory and go up to find project root
            current_dir = Path(__file__).parent
            project_root = current_dir

            # Go up until we find the project root (containing pyproject.toml or similar)
            while project_root.parent != project_root:
                if (project_root / "pyproject.toml").exists() or (
                    project_root / ".git"
                ).exists():
                    break
                project_root = project_root.parent

            env_file = project_root / ".env"
            if env_file.exists():
                load_dotenv(env_file)
                logger.debug(f"Loaded environment variables from {env_file}")
            else:
                # Try loading from current directory as fallback
                load_dotenv(
                    verbose=False
                )  # This will look for .env in current directory

        except Exception as e:
            # Don't fail if .env loading fails, just log a warning
            logger.warning(f"Could not load .env file: {e}")

    def _resolve_config_path(self, config_path: Optional[str]) -> Path:
        """Resolve the configuration file path."""
        if config_path:
            return Path(config_path)

        # Default locations to search for config
        default_locations = [
            Path(DEFAULT_CONFIG_FILENAME),
            Path("config") / DEFAULT_CONFIG_FILENAME,
            Path(__file__).parent / DEFAULT_CONFIG_FILENAME,
        ]

        for location in default_locations:
            if location.exists():
                return location

        # If no config file found, use the default location in the config directory
        return Path(__file__).parent / DEFAULT_CONFIG_FILENAME

    def load_config(self) -> LLMConfiguration:
        """Load and parse the configuration file.

        Returns:
            Parsed LLM configuration.

        Raises:
            ConfigurationError: If configuration loading fails.
        """
        try:
            if not self.config_path.exists():
                raise ConfigurationError(
                    f"Configuration file not found: {self.config_path}"
                )
            with open(self.config_path, "r", encoding="utf-8") as file:
                raw_config = yaml.safe_load(file)

            if not raw_config or "llm" not in raw_config:
                raise ConfigurationError("Invalid configuration: missing 'llm' section")

            # Process vault configuration and resolve secrets
            processed_config = self._resolve_vault_secrets(raw_config["llm"])

            # Parse and validate configuration
            return self._parse_configuration(processed_config)

        except yaml.YAMLError as e:
            raise ConfigurationError(f"Failed to parse YAML configuration: {e}") from e
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {e}") from e

    def _resolve_vault_secrets(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve secrets from Vault for provider configurations.

        Args:
            config: Raw configuration dictionary.

        Returns:
            Configuration with Vault secrets resolved.

        Raises:
            ConfigurationError: If vault configuration is invalid or secrets cannot be resolved
        """
        try:
            # First process any remaining environment variables (like vault config)
            config = self._process_environment_variables(config)

            # Initialize vault resolver
            resolver = self._initialize_vault_resolver(config)

            # Process provider configurations
            self._resolve_provider_secrets(config, resolver)

            return config

        except Exception as e:
            if isinstance(e, ConfigurationError):
                raise
            raise ConfigurationError(f"Failed to resolve vault secrets: {e}") from e

    def _initialize_vault_resolver(self, config: Dict[str, Any]):
        """Initialize vault secret resolver from configuration.

        Args:
            config: Configuration dictionary

        Returns:
            Initialized SecretResolver or None if vault not available

        Raises:
            ConfigurationError: If vault configuration is invalid
        """
        vault_config = config.get("vault", {})
        if not vault_config.get("enabled", True):
            raise ConfigurationError("Vault is disabled in configuration")

        # SecretResolver uses Vault Agent, so no need for vault_token from config
        return SecretResolver()

    def _resolve_provider_secrets(
        self, config: Dict[str, Any], resolver: SecretResolver
    ) -> None:
        """Resolve secrets for providers using the new vault structure.

        Args:
            config: Configuration dictionary to update
            resolver: Secret resolver instance

        Raises:
            ConfigurationError: If secret resolution fails
        """
        if "providers" not in config:
            return

        # Validate environment-specific requirements
        if self.environment in ["development", "test"]:
            if not self.connection_id:
                raise ConfigurationError(
                    f"connection_id is required for {self.environment} environment"
                )

        try:
            providers_to_update: Dict[str, Dict[str, Any]] = {}

            # Process each provider defined in the config
            for provider_name, provider_config in config["providers"].items():
                try:
                    if not isinstance(provider_config, dict):
                        logger.warning(
                            f"Provider {provider_name} config is not a dictionary, skipping"
                        )
                        continue
                    provider_config = cast(Dict[str, Any], provider_config)

                    # Skip if provider doesn't have models defined
                    if "models" not in provider_config:
                        logger.warning(
                            f"Provider {provider_name} has no models defined, skipping"
                        )
                        continue

                    # For production: try to find any available model
                    # For dev/test: use connection_id to find specific model
                    if self.environment == "production":
                        # Find first available model for this provider
                        available_models = resolver.list_available_models(
                            provider_name, self.environment
                        )
                        if available_models:
                            # Use the first available model in production
                            model_name = available_models[0]
                            secret = resolver.get_secret_for_model(
                                provider_name, self.environment, model_name
                            )
                            if secret:
                                # Update provider config with secrets
                                updated_config = self._merge_config_with_secrets(
                                    provider_config, secret, model_name
                                )
                                providers_to_update[provider_name] = updated_config
                                logger.info(
                                    f"Configured {provider_name} with model {model_name}"
                                )
                            else:
                                logger.warning(
                                    f"No secret found for {provider_name} model {model_name}"
                                )
                        else:
                            logger.warning(
                                f"No available models found for provider {provider_name}"
                            )
                    else:
                        # For dev/test, try to find the specific connection_id
                        # Try each model to see if we can find the connection
                        for model_name in provider_config.get("models", {}):
                            secret = resolver.get_secret_for_model(
                                provider_name,
                                self.environment,
                                model_name,
                                self.connection_id,
                            )
                            if secret:
                                # Update provider config with secrets
                                updated_config = self._merge_config_with_secrets(
                                    provider_config, secret, model_name
                                )
                                providers_to_update[provider_name] = updated_config
                                logger.info(
                                    f"Configured {provider_name} with connection {self.connection_id}"
                                )
                                break
                        else:
                            logger.warning(
                                f"No connection found for {provider_name} with connection_id {self.connection_id}"
                            )

                except Exception as e:
                    logger.error(f"Failed to process provider {provider_name}: {e}")
                    logger.debug(
                        f"Provider {provider_name} processing error details",
                        exc_info=True,
                    )
                    # Continue to next provider instead of failing completely
                    continue

            # Check if we have any providers configured
            if not providers_to_update:
                if self.environment == "production":
                    raise ConfigurationError(
                        "No providers available for production environment. "
                        "At least one provider must have production models configured."
                    )
                else:
                    raise ConfigurationError(
                        f"No providers available for {self.environment} environment"
                        + (
                            f" with connection_id {self.connection_id}"
                            if self.connection_id
                            else ""
                        )
                    )

            # Update the configuration with only available providers
            config["providers"] = providers_to_update

            # Update default_provider if needed
            self._update_default_provider(config)

            logger.info(
                f"Successfully configured {len(providers_to_update)} providers: {list(providers_to_update.keys())}"
            )

        except Exception as e:
            if isinstance(e, ConfigurationError):
                raise
            raise ConfigurationError(f"Failed to resolve provider secrets: {e}") from e

    def _merge_config_with_secrets(
        self, provider_config: Dict[str, Any], secret: Any, model_name: str
    ) -> Dict[str, Any]:
        """Merge provider configuration with secrets from Vault.

        Args:
            provider_config: Provider configuration from YAML
            secret: Secret object from Vault (AzureOpenAISecret or AWSBedrockSecret)
            model_name: Model name being configured

        Returns:
            Updated provider configuration with secrets and model-specific config
        """
        # Start with the original config (provider-level settings)
        updated_config = provider_config.copy()

        # Set the active model
        updated_config["model"] = model_name

        # Get model-specific configuration from YAML
        model_config: Dict[str, Any] = {}
        if "models" in provider_config and model_name in provider_config["models"]:
            raw_model_config = provider_config["models"][model_name]
            if isinstance(raw_model_config, dict):
                model_config = cast(Dict[str, Any], raw_model_config.copy())

        # Add secret data based on provider type
        if hasattr(secret, "endpoint"):  # Azure OpenAI
            updated_config.update(
                {
                    "endpoint": secret.endpoint,
                    "api_key": secret.api_key,
                    "enabled": True,
                }
            )
            # Merge model-specific config, with secret taking precedence for deployment_name
            if model_config:
                # Add model-specific settings (max_tokens, temperature, etc.)
                updated_config.update(model_config)
                # Override deployment_name from secret if provided
                updated_config["deployment_name"] = secret.deployment_name

        elif hasattr(secret, "region"):  # AWS Bedrock
            updated_config.update(
                {
                    "region": secret.region,
                    "access_key_id": secret.access_key_id,
                    "secret_access_key": secret.secret_access_key,
                    "enabled": True,
                }
            )
            if hasattr(secret, "session_token") and secret.session_token:
                updated_config["session_token"] = secret.session_token

            # Merge model-specific config
            if model_config:
                updated_config.update(model_config)

        # Remove the models section since we're now using a single active model
        if "models" in updated_config:
            del updated_config["models"]

        return updated_config

    def _build_provider_configs(
        self, config: Dict[str, Any], available_providers: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """Build configuration for available providers.

        Args:
            config: Original configuration
            available_providers: Available providers from vault

        Returns:
            Dictionary of provider configurations
        """
        providers_to_process: Dict[str, Dict[str, Any]] = {}

        for provider_name, connection in available_providers.items():
            # Check if provider is defined in config
            if provider_name in config["providers"]:
                provider_config = config["providers"][provider_name]

                # Copy the template configuration
                if isinstance(provider_config, dict):
                    providers_to_process[provider_name] = {
                        **provider_config,
                        "enabled": True,  # Force enable since it's available in vault
                    }
                    logger.info(
                        f"Using provider {provider_name} from vault connection {connection.metadata.id}"
                    )
                else:
                    logger.warning(
                        f"Invalid configuration for provider {provider_name}, skipping"
                    )
            else:
                # Provider available in vault but not in config template
                # Create a minimal config for it
                providers_to_process[provider_name] = {
                    "enabled": True,
                    "cache": True,
                    "num_retries": 3,
                }
                logger.info(
                    f"Provider {provider_name} available in vault but not in config, using minimal configuration"
                )

        return providers_to_process

    def _update_default_provider(self, config: Dict[str, Any]) -> None:
        """Update default_provider if it's not available.

        Args:
            config: Configuration dictionary to update
        """
        if "default_provider" in config and "providers" in config:
            default_provider = config["default_provider"]
            available_providers = config["providers"]

            if default_provider not in available_providers:
                # Set default to the first available provider
                if available_providers:
                    new_default = next(iter(available_providers.keys()))
                    logger.warning(
                        f"Default provider '{default_provider}' not available, "
                        f"using '{new_default}' instead"
                    )
                    config["default_provider"] = new_default

    def _process_environment_variables(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Process environment variable substitutions in configuration.

        This method is now only used for vault configuration processing.

        Args:
            config: Raw configuration dictionary.

        Returns:
            Configuration with environment variables substituted.
        """

        def substitute_env_vars(obj: ConfigValue) -> ConfigValue:
            if isinstance(obj, str):
                # Pattern to match ${VAR_NAME} or ${VAR_NAME:default_value}
                pattern = r"\$\{([^}:]+)(?::([^}]*))?\}"

                def replace_env_var(match: re.Match[str]) -> str:
                    var_name = match.group(1)
                    default_value = match.group(2) if match.group(2) is not None else ""
                    return os.getenv(var_name, default_value)

                return re.sub(pattern, replace_env_var, obj)
            elif isinstance(obj, dict):
                result: Dict[str, ConfigValue] = {}
                for key, value in obj.items():
                    result[str(key)] = substitute_env_vars(value)
                return result
            elif isinstance(obj, list):
                result_list: List[ConfigValue] = []

                for item in obj:
                    result_list.append(substitute_env_vars(item))
                return result_list
            else:
                return obj

        result = substitute_env_vars(config)
        if isinstance(result, dict):
            return result
        else:
            # This should never happen given our input type, but provide a fallback
            raise ConfigurationError(
                "Environment variable substitution resulted in non-dictionary type"
            )

    def _parse_configuration(self, config: Dict[str, Any]) -> LLMConfiguration:
        """Parse the processed configuration into structured objects.

        Args:
            config: Processed configuration dictionary.

        Returns:
            Structured LLM configuration.

        Raises:
            InvalidConfigurationError: If configuration validation fails.
        """
        try:
            # Validate required fields
            if "default_provider" not in config:
                raise InvalidConfigurationError(
                    "Missing required field: default_provider"
                )

            if "providers" not in config:
                raise InvalidConfigurationError("Missing required field: providers")

            # Parse default provider
            try:
                default_provider = LLMProvider(config["default_provider"])
            except ValueError as e:
                raise InvalidConfigurationError(
                    f"Invalid default_provider: {config['default_provider']}"
                ) from e

            # Parse provider configurations
            providers: Dict[str, ProviderConfig] = {}

            for provider_name, provider_config in config["providers"].items():
                try:
                    provider_type = LLMProvider(provider_name)
                    providers[provider_name] = self._parse_provider_config(
                        provider_type, provider_config
                    )
                except ValueError as e:
                    raise InvalidConfigurationError(
                        f"Invalid provider name: {provider_name}"
                    ) from e

            # Validate that default provider exists and is enabled
            if default_provider.value not in providers:
                raise InvalidConfigurationError(
                    f"Default provider '{default_provider.value}' not found in providers"
                )

            if not providers[default_provider.value].enabled:
                raise InvalidConfigurationError(
                    f"Default provider '{default_provider.value}' is not enabled"
                )

            # Parse vault configuration
            vault_config = None
            if "vault" in config:
                vault_config = VaultConfig(**config["vault"])

            return LLMConfiguration(
                vault=vault_config,
                default_provider=default_provider,
                providers=providers,
            )

        except Exception as e:
            if isinstance(e, InvalidConfigurationError):
                raise
            raise InvalidConfigurationError(f"Configuration parsing failed: {e}") from e

    def _parse_provider_config(
        self, provider_type: LLMProvider, config: Dict[str, Any]
    ) -> ProviderConfig:
        """Parse provider-specific configuration.

        Args:
            provider_type: Type of the provider.
            config: Provider configuration dictionary.

        Returns:
            Parsed provider configuration.
        """
        # Validate required base fields
        required_fields = ["enabled", "model"]
        for field in required_fields:
            if field not in config:
                raise InvalidConfigurationError(
                    f"Missing required field '{field}' for provider {provider_type.value}"
                )

        if provider_type == LLMProvider.AZURE_OPENAI:
            return AzureOpenAIConfig(
                enabled=config["enabled"],
                model=config["model"],
                max_tokens=config.get("max_tokens", 4096),
                temperature=config.get("temperature", 0.7),
                endpoint=config.get("endpoint", ""),
                api_key=config.get("api_key", ""),
                api_version=config.get("api_version", "2024-02-15-preview"),
                deployment_name=config.get("deployment_name", ""),
            )
        elif provider_type == LLMProvider.AWS_BEDROCK:
            return AWSBedrockConfig(
                enabled=config["enabled"],
                model=config["model"],
                max_tokens=config.get("max_tokens", 4096),
                temperature=config.get("temperature", 0.7),
                region=config.get("region", ""),
                access_key_id=config.get("access_key_id", ""),
                secret_access_key=config.get("secret_access_key", ""),
                session_token=config.get("session_token"),
            )
        else:
            raise InvalidConfigurationError(
                f"Unsupported provider type: {provider_type}"
            )
