"""
Integration tests for LLM connection management via Ruuter.

These tests verify:
1. Adding LLM connections via Ruuter endpoints
2. Storing connection data in PostgreSQL
3. Storing credentials in Vault
4. Retrieving connection information
5. Updating and deleting connections
"""

import requests
import time
from loguru import logger


class TestLLMConnectionsRuuter:
    """Test LLM connection management via Ruuter endpoints."""

    def test_ruuter_service_health(self, ruuter_private_client):
        """Verify Ruuter service is responding."""
        response = requests.get(
            f"{ruuter_private_client.base_url}/rag-search/health", timeout=10
        )
        assert response.status_code == 200, "Ruuter health check failed"
        logger.info("Ruuter service is healthy")

    def test_add_azure_testing_connection_via_ruuter(
        self, ruuter_private_client, postgres_client, rag_stack
    ):
        """Test adding an Azure LLM connection via Ruuter with testing environment."""
        # Prepare request payload for Azure connection
        payload = {
            "connection_name": "Test Azure Connection via Ruuter",
            "llm_platform": "azure",
            "llm_model": "gpt-4o-mini",
            "deployment_name": "gpt-4o-mini-deployment-ruuter",
            "target_uri": "https://test-ruuter.openai.azure.com/",
            "api_key": "test-api-key-ruuter-12345...TESTONLY",
            "embedding_platform": "azure",
            "embedding_model": "text-embedding-3-large",
            "embedding_deployment_name": "text-embedding-deployment-ruuter",
            "embedding_target_uri": "https://test-ruuter.openai.azure.com/",
            "embedding_azure_api_key": "test-embedding-api-key-ruuter-67890...TESTONLY",
            "monthly_budget": 1000.00,
            "warn_budget_threshold": 80,
            "stop_budget_threshold": 95,
            "disconnect_on_budget_exceed": False,
            "deployment_environment": "testing",
        }

        # Make request to add connection via Ruuter
        logger.info("Adding Azure testing connection via Ruuter...")
        response = requests.post(
            f"{ruuter_private_client.base_url}/rag-search/llm-connections/add",
            json=payload,
            timeout=30,
        )

        # Assert response
        assert response.status_code == 200, f"Failed with: {response.text}"
        data = response.json()

        logger.info(f"Response from Ruuter: {data}")

        # Handle nested response structure
        response_data = data.get("response", data)
        assert response_data.get("operationSuccess") is True, (
            f"Operation should succeed. Response: {data}"
        )
        assert "id" in response_data, "Response should include connection ID"
        connection_id = response_data["id"]
        logger.info(f"Connection created via Ruuter with ID: {connection_id}")

        # Wait for database write
        time.sleep(2)

        # Verify in database
        cursor = postgres_client.cursor()
        try:
            cursor.execute(
                "SELECT connection_name, llm_platform, llm_model, "
                "deployment_name, target_uri, embedding_platform, "
                "embedding_model, monthly_budget, warn_budget_threshold, "
                "stop_budget_threshold, disconnect_on_budget_exceed, environment "
                "FROM llm_connections WHERE id = %s",
                (connection_id,),
            )
            row = cursor.fetchone()
            assert row is not None, "Connection not found in database"

            (
                db_connection_name,
                db_llm_platform,
                db_llm_model,
                db_deployment_name,
                db_target_uri,
                db_embedding_platform,
                db_embedding_model,
                db_monthly_budget,
                db_warn_threshold,
                db_stop_threshold,
                db_disconnect_on_exceed,
                db_environment,
            ) = row

            assert db_connection_name == payload["connection_name"]
            assert db_llm_platform == payload["llm_platform"]
            assert db_llm_model == payload["llm_model"]
            assert db_deployment_name == payload["deployment_name"]
            assert db_target_uri == payload["target_uri"]
            assert db_embedding_platform == payload["embedding_platform"]
            assert db_embedding_model == payload["embedding_model"]
            assert float(db_monthly_budget) == payload["monthly_budget"]
            assert db_warn_threshold == payload["warn_budget_threshold"]
            assert db_stop_threshold == payload["stop_budget_threshold"]
            assert db_disconnect_on_exceed == payload["disconnect_on_budget_exceed"]
            assert db_environment == payload["deployment_environment"]

            logger.info("Database verification passed for Ruuter-added connection")
        finally:
            cursor.close()

        logger.info("All verifications passed for Azure testing connection via Ruuter")

    def test_add_azure_production_connection_via_ruuter(
        self, ruuter_private_client, postgres_client, rag_stack
    ):
        """Test adding an Azure LLM connection via Ruuter with production environment."""
        payload = {
            "connection_name": "Production Azure Connection via Ruuter",
            "llm_platform": "azure",
            "llm_model": "gpt-4o",
            "deployment_name": "gpt-4o-production-deployment-ruuter",
            "target_uri": "https://production-ruuter.openai.azure.com/",
            "api_key": "prod-api-key-ruuter-12345...TESTONLY",
            "embedding_platform": "azure",
            "embedding_model": "text-embedding-3-large",
            "embedding_deployment_name": "text-embedding-prod-deployment-ruuter",
            "embedding_target_uri": "https://production-ruuter.openai.azure.com/",
            "embedding_azure_api_key": "prod-embedding-api-key-ruuter-67890...TESTONLY",
            "monthly_budget": 5000.00,
            "warn_budget_threshold": 75,
            "stop_budget_threshold": 90,
            "disconnect_on_budget_exceed": True,
            "deployment_environment": "production",
        }

        logger.info("Adding Azure production connection via Ruuter...")
        response = requests.post(
            f"{ruuter_private_client.base_url}/rag-search/llm-connections/add",
            json=payload,
            timeout=30,
        )

        assert response.status_code == 200, f"Failed with: {response.text}"
        data = response.json()
        # Handle nested response structure
        response_data = data.get("response", data)
        assert response_data.get("operationSuccess") is True
        assert "id" in response_data
        connection_id = response_data["id"]
        logger.info(
            f"Production connection created via Ruuter with ID: {connection_id}"
        )

        # Wait for database write
        time.sleep(2)

        # Verify in database
        cursor = postgres_client.cursor()
        try:
            cursor.execute(
                "SELECT connection_name, environment FROM llm_connections WHERE id = %s",
                (connection_id,),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == payload["connection_name"]
            assert row[1] == "production"
            logger.info("Production connection verified in database")
        finally:
            cursor.close()

    def test_get_llm_connection_via_ruuter(
        self, ruuter_private_client, postgres_client, rag_stack
    ):
        """Test retrieving LLM connection details via Ruuter."""
        # First, add a connection
        payload = {
            "connection_name": "Test Get Connection",
            "llm_platform": "azure",
            "llm_model": "gpt-4o-mini",
            "deployment_name": "test-deployment",
            "target_uri": "https://test.openai.azure.com/",
            "api_key": "test-api-key...TESTONLY",
            "embedding_platform": "azure",
            "embedding_model": "text-embedding-3-large",
            "embedding_deployment_name": "test-embedding",
            "embedding_target_uri": "https://test.openai.azure.com/",
            "embedding_azure_api_key": "test-embedding-key...TESTONLY",
            "monthly_budget": 1000.00,
            "warn_budget_threshold": 80,
            "stop_budget_threshold": 95,
            "disconnect_on_budget_exceed": False,
            "deployment_environment": "testing",
        }

        logger.info("Adding connection to test GET endpoint...")
        add_response = requests.post(
            f"{ruuter_private_client.base_url}/rag-search/llm-connections/add",
            json=payload,
            timeout=30,
        )
        assert add_response.status_code == 200
        add_data = add_response.json()
        add_response_data = add_data.get("response", add_data)
        connection_id = add_response_data["id"]
        logger.info(f"Connection added with ID: {connection_id}")

        time.sleep(2)

        # Now get the connection
        logger.info("Retrieving connection via Ruuter GET endpoint...")
        get_response = requests.post(
            f"{ruuter_private_client.base_url}/rag-search/llm-connections/get",
            json={"connection_id": connection_id},
            timeout=10,
        )

        assert get_response.status_code == 200, (
            f"Failed to get connection: {get_response.text}"
        )
        get_data = get_response.json()
        # GET endpoint returns object directly, not nested
        connection_data = get_data["response"]
        logger.info(f"Retrieved connection data: {connection_data}")

        # Verify returned data
        assert connection_data["id"] == connection_id
        assert connection_data["connectionName"] == payload["connection_name"]
        assert connection_data["llmPlatform"] == payload["llm_platform"]
        assert connection_data["llmModel"] == payload["llm_model"]
        assert connection_data["environment"] == payload["deployment_environment"]

        logger.info("Successfully retrieved connection via Ruuter GET endpoint")

    def test_production_connection_demotion_via_ruuter(
        self, ruuter_private_client, postgres_client, rag_stack
    ):
        """Test that adding a new production connection demotes the existing one to testing via Ruuter."""
        # First production connection
        first_payload = {
            "connection_name": "First Production Connection Ruuter",
            "llm_platform": "azure",
            "llm_model": "gpt-4o-mini",
            "deployment_name": "first-deployment-ruuter",
            "target_uri": "https://first-ruuter.openai.azure.com/",
            "api_key": "first-api-key-ruuter...TESTONLY",
            "embedding_platform": "azure",
            "embedding_model": "text-embedding-3-large",
            "embedding_deployment_name": "first-embedding-deployment-ruuter",
            "embedding_target_uri": "https://first-ruuter.openai.azure.com/",
            "embedding_azure_api_key": "first-embedding-key-ruuter...TESTONLY",
            "monthly_budget": 2000.00,
            "warn_budget_threshold": 70,
            "stop_budget_threshold": 85,
            "disconnect_on_budget_exceed": False,
            "deployment_environment": "production",
        }

        logger.info("Adding first production connection via Ruuter...")
        response1 = requests.post(
            f"{ruuter_private_client.base_url}/rag-search/llm-connections/add",
            json=first_payload,
            timeout=30,
        )
        assert response1.status_code == 200
        response1_data = response1.json()
        first_connection_data = response1_data.get("response", response1_data)
        first_connection_id = first_connection_data["id"]
        logger.info(f"First production connection ID: {first_connection_id}")

        time.sleep(2)

        # Verify it's production
        cursor = postgres_client.cursor()
        try:
            cursor.execute(
                "SELECT environment FROM llm_connections WHERE id = %s",
                (first_connection_id,),
            )
            row = cursor.fetchone()
            assert row[0] == "production"
            logger.info("First connection is production")
        finally:
            cursor.close()

        # Now add a second production connection
        second_payload = {
            "connection_name": "Second Production Connection Ruuter",
            "llm_platform": "azure",
            "llm_model": "gpt-4o",
            "deployment_name": "second-deployment-ruuter",
            "target_uri": "https://second-ruuter.openai.azure.com/",
            "api_key": "second-api-key-ruuter...TESTONLY",
            "embedding_platform": "azure",
            "embedding_model": "text-embedding-3-large",
            "embedding_deployment_name": "second-embedding-deployment-ruuter",
            "embedding_target_uri": "https://second-ruuter.openai.azure.com/",
            "embedding_azure_api_key": "second-embedding-key-ruuter...TESTONLY",
            "monthly_budget": 3000.00,
            "warn_budget_threshold": 80,
            "stop_budget_threshold": 95,
            "disconnect_on_budget_exceed": True,
            "deployment_environment": "production",
        }

        logger.info("Adding second production connection via Ruuter...")
        response2 = requests.post(
            f"{ruuter_private_client.base_url}/rag-search/llm-connections/add",
            json=second_payload,
            timeout=30,
        )
        assert response2.status_code == 200
        response2_data = response2.json()
        second_connection_data = response2_data.get("response", response2_data)
        second_connection_id = second_connection_data["id"]
        logger.info(f"Second production connection ID: {second_connection_id}")

        time.sleep(2)

        # Verify first connection was demoted to testing
        cursor = postgres_client.cursor()
        try:
            cursor.execute(
                "SELECT environment FROM llm_connections WHERE id = %s",
                (first_connection_id,),
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "testing", "First connection should be demoted to testing"
            logger.info("First connection was demoted to testing")

            # Verify second connection is production
            cursor.execute(
                "SELECT environment FROM llm_connections WHERE id = %s",
                (second_connection_id,),
            )
            row = cursor.fetchone()
            assert row[0] == "production", "Second connection should be production"
            logger.info("Second connection is production")
        finally:
            cursor.close()

        logger.info("Production connection demotion test passed via Ruuter")

    def test_delete_llm_connection_via_ruuter(
        self, ruuter_private_client, postgres_client, rag_stack
    ):
        """Test deleting an LLM connection via Ruuter."""
        # First, add a connection to delete
        payload = {
            "connection_name": "Connection To Delete",
            "llm_platform": "azure",
            "llm_model": "gpt-4o-mini",
            "deployment_name": "delete-deployment",
            "target_uri": "https://delete.openai.azure.com/",
            "api_key": "delete-api-key...TESTONLY",
            "embedding_platform": "azure",
            "embedding_model": "text-embedding-3-large",
            "embedding_deployment_name": "delete-embedding",
            "embedding_target_uri": "https://delete.openai.azure.com/",
            "embedding_azure_api_key": "delete-embedding-key...TESTONLY",
            "monthly_budget": 500.00,
            "warn_budget_threshold": 80,
            "stop_budget_threshold": 95,
            "disconnect_on_budget_exceed": False,
            "deployment_environment": "testing",
        }

        logger.info("Adding connection to test DELETE endpoint...")
        add_response = requests.post(
            f"{ruuter_private_client.base_url}/rag-search/llm-connections/add",
            json=payload,
            timeout=30,
        )
        assert add_response.status_code == 200
        add_data = add_response.json()
        add_response_data = add_data.get("response", add_data)
        connection_id = add_response_data["id"]
        logger.info(f"Connection added with ID: {connection_id}")

        time.sleep(2)

        # Delete the connection
        logger.info("Deleting connection via Ruuter DELETE endpoint...")
        delete_response = requests.post(
            f"{ruuter_private_client.base_url}/rag-search/llm-connections/delete",
            json={"connection_id": connection_id},
            timeout=10,
        )

        assert delete_response.status_code == 200, (
            f"Failed to delete connection: {delete_response.text}"
        )
        logger.info("Delete request succeeded")

        time.sleep(2)

        # Verify connection no longer exists in database
        cursor = postgres_client.cursor()
        try:
            cursor.execute(
                "SELECT COUNT(*) FROM llm_connections WHERE id = %s", (connection_id,)
            )
            count = cursor.fetchone()[0]
            assert count == 0, "Connection should be deleted from database"
            logger.info("Connection successfully deleted from database")
        finally:
            cursor.close()
