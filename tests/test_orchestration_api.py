"""
Test file for validating the RAG Stack orchestration service using testcontainers.

This includes:
- Health endpoint validation
- Vault KV secret validation
- Request structure validation for /orchestrate and /orchestrate-test
- Langfuse integration validation
"""

from typing import Any, Dict
from loguru import logger
from requests import Session, Response
import requests
from pathlib import Path


# -------------------- LLM Orchestration Tests --------------------


def test_health_endpoint(orchestration_client: Session) -> None:
    """Test that the orchestration service health endpoint is available and initialized"""
    base_url: str = getattr(orchestration_client, "base_url", "")
    response: Response = orchestration_client.get(f"{base_url}/health")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    health_data: Dict[str, Any] = response.json()
    assert health_data.get("status") == "healthy", (
        f"Unexpected status: {health_data.get('status')}"
    )
    assert health_data.get("service") == "llm-orchestration-service", (
        f"Unexpected service: {health_data.get('service')}"
    )
    assert health_data.get("orchestration_service") == "initialized", (
        f"Unexpected orchestration_service: {health_data.get('orchestration_service')}"
    )

    logger.info("Health endpoint test successfully passed.")


def test_orchestrate_endpoint_structure(orchestration_client: Session) -> None:
    """Test that the /orchestrate endpoint accepts a valid request structure"""
    base_url: str = getattr(orchestration_client, "base_url", "")

    test_request: Dict[str, Any] = {
        "chatId": "test-chat-123",
        "message": "Hello, this is a test message",
        "authorId": "test-user-456",
        "conversationHistory": [],
        "url": "https://test.example.com",
        "environment": "test",
    }

    response: Response = orchestration_client.post(
        f"{base_url}/orchestrate", json=test_request
    )

    assert response.status_code in {200, 400, 500}, (
        f"Unexpected status: {response.status_code}"
    )
    logger.info("Orchestrate endpoint accepted the request structure.")


def test_orchestrate_test_endpoint_available(orchestration_client: Session) -> None:
    """Test that the /orchestrate-test endpoint is available in testing mode"""
    base_url: str = getattr(orchestration_client, "base_url", "")

    test_request: Dict[str, Any] = {
        "chatId": "test-chat-456",
        "message": "What is RAG?",
        "authorId": "test-user-789",
        "conversationHistory": [],
        "url": "https://test.example.com",
        "environment": "test",
        "connection_id": "evalconnection-1",
    }

    response: Response = orchestration_client.post(
        f"{base_url}/orchestrate-test", json=test_request
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    response_data: Dict[str, Any] = response.json()

    # Verify standard response fields
    assert "chatId" in response_data, "Missing chatId in response"
    assert "llmServiceActive" in response_data, "Missing llmServiceActive in response"
    assert "content" in response_data, "Missing content in response"

    # Verify testing-specific fields
    assert "retrieval_context" in response_data, (
        "Missing retrieval_context in test response"
    )
    assert "refined_questions" in response_data, (
        "Missing refined_questions in test response"
    )

    logger.info("Orchestrate-test endpoint test passed.")
    logger.info(
        f"   Retrieved {len(response_data.get('retrieval_context', []))} context chunks"
    )


def test_orchestrate_test_endpoint_returns_context(
    orchestration_client: Session,
) -> None:
    """Test that /orchestrate-test returns retrieval context for DeepEval"""
    base_url: str = getattr(orchestration_client, "base_url", "")

    test_request: Dict[str, Any] = {
        "chatId": "deepeval-test-001",
        "message": "Explain contextual retrieval",
        "authorId": "deepeval-tester",
        "conversationHistory": [],
        "url": "https://test.example.com",
        "environment": "test",
        "connection_id": "evalconnection-1",
    }

    response: Response = orchestration_client.post(
        f"{base_url}/orchestrate-test", json=test_request
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    response_data: Dict[str, Any] = response.json()

    # Verify retrieval context structure
    retrieval_context = response_data.get("retrieval_context", [])
    if retrieval_context:  # Only check structure if context was retrieved
        assert isinstance(retrieval_context, list), "retrieval_context should be a list"

        # Check first chunk structure
        first_chunk = retrieval_context[0]
        assert "content" in first_chunk, "Chunk missing content field"
        assert "score" in first_chunk, "Chunk missing score field"
        assert isinstance(first_chunk["score"], (int, float)), "Score should be numeric"

        logger.info(f"Retrieved context with {len(retrieval_context)} chunks")
        logger.info(f"   First chunk score: {first_chunk['score']:.4f}")
    else:
        logger.info("No context retrieved (this is ok for out-of-scope queries)")


# -------------------- Vault Integration Test --------------------


def test_vault_service_kv_secrets(rag_stack: Any) -> None:
    """
    Verify that all required secrets are properly written to Vault:
    - LLM connection secrets
    - Langfuse configuration
    - Embedding model secrets
    - Guardrails configuration
    """
    vault_url = rag_stack.get_vault_url()
    vault_token_path = Path("test-vault/agent-out/token")

    assert vault_token_path.exists(), "Vault Agent token file not found"
    token = vault_token_path.read_text().strip()
    assert token, "Vault token is empty"

    headers = {"X-Vault-Token": token}

    # Test 1: LLM Connection Secret
    kv_path = "secret/data/llm/connections/azure_openai/test/gpt-4o-mini"
    url = f"{vault_url}/v1/{kv_path}"
    logger.info(f"Testing LLM connection secret at: {url}")

    response = requests.get(url, headers=headers, timeout=10)
    assert response.status_code == 200, (
        f"LLM secret read failed: {response.status_code}"
    )

    llm_data = response.json()["data"]["data"]
    expected_llm_fields = [
        "connection_id",
        "endpoint",
        "api_key",
        "deployment_name",
        "model",
    ]
    for field in expected_llm_fields:
        assert field in llm_data, f"Missing field in LLM secret: {field}"

    logger.info("LLM connection secret validated")

    # Test 2: Langfuse Configuration Secret
    langfuse_path = "secret/data/langfuse/config"
    url = f"{vault_url}/v1/{langfuse_path}"
    logger.info(f"Testing Langfuse secret at: {url}")

    response = requests.get(url, headers=headers, timeout=10)
    assert response.status_code == 200, (
        f"Langfuse secret read failed: {response.status_code}"
    )

    langfuse_data = response.json()["data"]["data"]
    expected_langfuse_fields = ["public_key", "secret_key", "host"]
    for field in expected_langfuse_fields:
        assert field in langfuse_data, f"Missing field in Langfuse secret: {field}"

    logger.info("Langfuse configuration secret validated")

    # Test 3: Embedding Model Secret
    embedding_path = "secret/data/embeddings/azure_openai/test/text-embedding-3-large"
    url = f"{vault_url}/v1/{embedding_path}"
    logger.info(f"📡 Testing embedding model secret at: {url}")

    response = requests.get(url, headers=headers, timeout=10)
    assert response.status_code == 200, (
        f"Embedding secret read failed: {response.status_code}"
    )

    embedding_data = response.json()["data"]["data"]
    expected_embedding_fields = [
        "connection_id",
        "endpoint",
        "api_key",
        "deployment_name",
        "model",
    ]
    for field in expected_embedding_fields:
        assert field in embedding_data, f"Missing field in embedding secret: {field}"

    logger.info("Embedding model secret validated")

    # Test 4: Guardrails Configuration Secret
    guardrails_path = "secret/data/guardrails/anthropic/test/claude-3-5-sonnet"
    url = f"{vault_url}/v1/{guardrails_path}"
    logger.info(f"Testing guardrails secret at: {url}")

    response = requests.get(url, headers=headers, timeout=10)
    assert response.status_code == 200, (
        f"Guardrails secret read failed: {response.status_code}"
    )

    guardrails_data = response.json()["data"]["data"]
    expected_guardrails_fields = ["connection_id", "api_key", "model"]
    for field in expected_guardrails_fields:
        assert field in guardrails_data, f"Missing field in guardrails secret: {field}"

    logger.info("Guardrails configuration secret validated")
    logger.info("All Vault KV secrets validated successfully")
