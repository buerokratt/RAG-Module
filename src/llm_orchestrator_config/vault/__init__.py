"""Vault integration for LLM Config Module."""

from llm_orchestrator_config.vault.secret_resolver import SecretResolver
from llm_orchestrator_config.vault.vault_client import VaultAgentClient
from llm_orchestrator_config.vault.models import AzureOpenAISecret, AWSBedrockSecret
from llm_orchestrator_config.vault.exceptions import VaultSecretError, VaultConnectionError

__all__ = [
    "SecretResolver",
    "VaultAgentClient",
    "AzureOpenAISecret",
    "AWSBedrockSecret",
    "VaultSecretError",
    "VaultConnectionError",
]
