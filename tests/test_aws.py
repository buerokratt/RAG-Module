import pytest
import dspy
from typing import Any, Dict
from pathlib import Path
from src.llm_config_module.llm_manager import LLMManager
from src.llm_config_module.types import LLMProvider


def test_aws_llm_inference(vault_env_vars: Dict[str, str]) -> None:
    """Test AWS Bedrock inference using Testcontainers vault."""
    cfg_path = (
        Path(__file__).parent.parent
        / "src"
        / "llm_config_module"
        / "config"
        / "llm_config.yaml"
    )
    assert cfg_path.exists(), f"llm_config.yaml not found at {cfg_path}"

    # Reset singleton to ensure fresh vault discovery
    LLMManager.reset_instance()

    # Initialize with production environment to use vault credentials
    manager = LLMManager(str(cfg_path), environment="production")

    # Check if AWS Bedrock provider is available from vault test data
    providers = manager.get_available_providers()

    if "aws" not in providers:
        pytest.skip("AWS Bedrock not available in vault test data")

    is_aws_available = manager.is_provider_available(LLMProvider.AWS_BEDROCK)

    if not is_aws_available:
        print("\nAWS Bedrock provider is disabled in configuration")
        print("Test passed - AWS Bedrock provider is properly disabled")
        return  # Test passes without doing inference

    # If AWS is enabled, proceed with inference test
    print("\nAWS Bedrock provider is enabled - running inference test")
    manager.configure_dspy()

    class QA(dspy.Signature):
        """Short factual answer"""

        question = dspy.InputField()
        answer = dspy.OutputField()

    qa = dspy.Predict(QA)
    out = qa(
        question="If this pass through the AWS Bedrock provider, say 'AWS DSPY Configuration Successful'"
    )

    print(
        "Question: If this pass through the AWS Bedrock provider, say 'AWS DSPY Configuration Successful'"
    )
    print(f"Answer: {out.answer}")

    # Type-safe assertions
    answer: Any = getattr(out, "answer", None)
    assert answer is not None, "Answer should not be None"
    assert isinstance(answer, str), f"Answer should be string, got {type(answer)}"
