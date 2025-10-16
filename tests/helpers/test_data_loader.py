"""Helper module to load test data into Qdrant before running tests."""

import requests
import uuid
from typing import List, Dict, Any
from loguru import logger
from datetime import datetime


def load_test_data_into_qdrant(
    orchestration_url: str,
    qdrant_url: str,
) -> None:
    """
    Load test documents into Qdrant contextual collections for retrieval testing.

    Uses the LLM Orchestration Service's embedding endpoint to create embeddings
    and stores them in the contextual_chunks_azure collection (matching production setup).

    Args:
        orchestration_url: URL of the orchestration service
        qdrant_url: URL of Qdrant service
    """
    logger.info("Loading test data into Qdrant contextual collections...")

    # Test documents matching the test dataset
    test_documents = get_test_documents()

    try:
        # Step 1: Create embeddings via orchestration service
        texts = [doc["contextual_content"] for doc in test_documents]

        logger.info(f"Creating embeddings for {len(texts)} documents...")
        embedding_response = requests.post(
            f"{orchestration_url}/embeddings",
            json={
                "texts": texts,
                "environment": "test",
                "connection_id": "evalconnection-1",  # Must match Vault secret
                "batch_size": 50,
            },
            timeout=120,
        )

        if embedding_response.status_code != 200:
            logger.error(f"Embedding API error: {embedding_response.status_code}")
            logger.error(f"Response: {embedding_response.text}")
            raise RuntimeError(f"Embedding creation failed: {embedding_response.text}")

        embeddings_data = embedding_response.json()

        # Debug: Log the actual response structure
        logger.info("=" * 60)
        logger.info("EMBEDDING API RESPONSE DEBUG")
        logger.info("=" * 60)
        logger.info(f"Response keys: {list(embeddings_data.keys())}")
        for key, value in embeddings_data.items():
            if key == "embeddings":
                logger.info(f"  {key}: list of {len(value)} embeddings")
                if value:
                    logger.info(f"    First embedding length: {len(value[0])}")
            else:
                logger.info(f"  {key}: {value}")
        logger.info("=" * 60)

        # Extract embeddings and metadata with proper fallbacks
        embeddings = embeddings_data.get("embeddings", [])
        if not embeddings:
            raise RuntimeError("No embeddings returned from API")

        # Get vector size from first embedding (most reliable method)
        vector_size = len(embeddings[0])

        # Try to get model name from various possible fields
        model_used = (
            embeddings_data.get("model_used")
            or embeddings_data.get("model")
            or embeddings_data.get("embedding_model")
            or "text-embedding-3-large"  # Fallback
        )

        logger.info(f"Created {len(embeddings)} embeddings")
        logger.info(f"   Vector size: {vector_size}")
        logger.info(f"   Model: {model_used}")

        # Step 2: Determine which collection to use based on model
        collection_name = _determine_collection_from_model(model_used)
        logger.info(f"Using collection: {collection_name}")

        # Step 3: Ensure collection exists with proper configuration
        import httpx

        async_client = httpx.Client(timeout=30.0)

        try:
            # Check if collection exists
            response = async_client.get(f"{qdrant_url}/collections/{collection_name}")

            if response.status_code == 404:
                # Create collection
                logger.info(f"Creating collection '{collection_name}'...")
                create_payload = {
                    "vectors": {
                        "size": vector_size,
                        "distance": "Cosine",
                    },
                    "optimizers_config": {"default_segment_number": 2},
                    "replication_factor": 1,
                }

                response = async_client.put(
                    f"{qdrant_url}/collections/{collection_name}", json=create_payload
                )

                if response.status_code not in [200, 201]:
                    raise RuntimeError(f"Failed to create collection: {response.text}")

                logger.info(f"Created collection '{collection_name}'")
            else:
                logger.info(f"Collection '{collection_name}' already exists")

        except Exception as e:
            logger.error(f"Collection setup failed: {e}")
            raise

        # Step 4: Index documents in Qdrant using the contextual format
        points = []
        for _, (doc, embedding) in enumerate(zip(test_documents, embeddings)):
            # Generate UUID for point ID (Qdrant requirement)
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, doc["chunk_id"]))

            # Create payload matching ContextualChunk structure
            payload = {
                # Core identifiers
                "chunk_id": doc["chunk_id"],
                "document_hash": doc["document_hash"],
                "chunk_index": doc["chunk_index"],
                "total_chunks": 1,
                # Content (matching contextual retrieval format)
                "original_content": doc["original_content"],
                "contextual_content": doc["contextual_content"],
                "context_only": doc["context"],
                # Embedding info
                "embedding_model": model_used,
                "vector_dimensions": vector_size,
                # Document metadata
                "document_url": doc["metadata"].get("source", "test_document"),
                "dataset_collection": "test_collection",
                # Processing metadata
                "processing_timestamp": datetime.now().isoformat(),
                "tokens_count": len(doc["contextual_content"]) // 4,  # Rough estimate
                # Additional metadata
                **doc["metadata"],
            }

            points.append({"id": point_id, "vector": embedding, "payload": payload})

        # Step 5: Upsert points in batches
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]

            upsert_payload = {"points": batch}

            response = async_client.put(
                f"{qdrant_url}/collections/{collection_name}/points",
                json=upsert_payload,
            )

            if response.status_code not in [200, 201]:
                raise RuntimeError(f"Failed to upsert points: {response.text}")

            logger.info(f"Indexed batch {i // batch_size + 1} ({len(batch)} points)")

        async_client.close()

        # Step 6: Verify indexing
        response = requests.get(f"{qdrant_url}/collections/{collection_name}")
        if response.status_code == 200:
            collection_info = response.json()
            points_count = collection_info.get("result", {}).get("points_count", 0)
            logger.info(f"Collection verification - Points count: {points_count}")

        logger.info(f"Successfully indexed {len(points)} documents into Qdrant")

    except Exception as e:
        logger.error(f"Failed to load test data: {e}")
        raise


def _determine_collection_from_model(model_name: str) -> str:
    """Determine which Qdrant collection to use based on embedding model."""
    model_lower = model_name.lower()

    # Azure OpenAI models -> contextual_chunks_azure
    if any(
        keyword in model_lower for keyword in ["azure", "text-embedding", "ada-002"]
    ):
        return "contextual_chunks_azure"

    # AWS Bedrock models -> contextual_chunks_aws
    elif any(
        keyword in model_lower for keyword in ["titan", "amazon", "aws", "bedrock"]
    ):
        return "contextual_chunks_aws"

    # Default to Azure collection
    else:
        logger.warning(
            f"Unknown model {model_name}, defaulting to contextual_chunks_azure"
        )
        return "contextual_chunks_azure"


def get_test_documents() -> List[Dict[str, Any]]:
    """
    Get test documents in contextual retrieval format.

    Each document includes:
    - original_content: The raw chunk text
    - context: Brief contextual description (simulating Anthropic methodology)
    - contextual_content: context + original_content (what gets embedded)
    """
    return [
        {
            "chunk_id": "test_doc_001_chunk_000",
            "document_hash": "test_doc_001",
            "chunk_index": 0,
            "original_content": "In 2021, the pension will become more flexible. People will be able to choose the most suitable time for their retirement, partially withdraw their pension or stop payment of their pension if they wish, in effect creating their own personal pension plan.",
            "context": "This chunk discusses pension flexibility reforms in Estonia.",
            "contextual_content": "This chunk discusses pension flexibility reforms in Estonia.\n\nIn 2021, the pension will become more flexible. People will be able to choose the most suitable time for their retirement, partially withdraw their pension or stop payment of their pension if they wish, in effect creating their own personal pension plan.",
            "metadata": {
                "category": "pension_information",
                "language": "en",
                "source": "gov_policy_2021",
            },
        },
        {
            "chunk_id": "test_doc_002_chunk_000",
            "document_hash": "test_doc_002",
            "chunk_index": 0,
            "original_content": "Starting in 2027, retirement age calculations will be based on the life expectancy of 65-year-olds. The pension system will thus be in line with demographic developments.",
            "context": "This chunk explains future pension age calculation changes.",
            "contextual_content": "This chunk explains future pension age calculation changes.\n\nStarting in 2027, retirement age calculations will be based on the life expectancy of 65-year-olds. The pension system will thus be in line with demographic developments.",
            "metadata": {
                "category": "pension_information",
                "language": "en",
                "source": "pension_reform_2027",
            },
        },
        {
            "chunk_id": "test_doc_003_chunk_000",
            "document_hash": "test_doc_003",
            "chunk_index": 0,
            "original_content": "From 2021, the formula for the state old-age pension will be upgraded - starting in 2021, we will start collecting the so-called joint part.",
            "context": "This chunk describes pension formula updates.",
            "contextual_content": "This chunk describes pension formula updates.\n\nFrom 2021, the formula for the state old-age pension will be upgraded - starting in 2021, we will start collecting the so-called joint part.",
            "metadata": {
                "category": "pension_information",
                "language": "en",
                "source": "pension_formula_update",
            },
        },
        {
            "chunk_id": "test_doc_004_chunk_000",
            "document_hash": "test_doc_004",
            "chunk_index": 0,
            "original_content": "In 2021, a total of approximately 653 million euros in benefits were paid to families. Approximately 310 million euros for family benefits; Approximately 280 million euros for parental benefit.",
            "context": "This chunk provides family benefit payment statistics.",
            "contextual_content": "This chunk provides family benefit payment statistics.\n\nIn 2021, a total of approximately 653 million euros in benefits were paid to families. Approximately 310 million euros for family benefits; Approximately 280 million euros for parental benefit.",
            "metadata": {
                "category": "family_benefits",
                "language": "en",
                "source": "benefits_report_2021",
            },
        },
        {
            "chunk_id": "test_doc_005_chunk_000",
            "document_hash": "test_doc_005",
            "chunk_index": 0,
            "original_content": "The Estonian parental benefit system is one of the most generous in the world, both in terms of the length of the period covered by the benefit and the amount of the benefit.",
            "context": "This chunk describes Estonia's parental benefit system.",
            "contextual_content": "This chunk describes Estonia's parental benefit system.\n\nThe Estonian parental benefit system is one of the most generous in the world, both in terms of the length of the period covered by the benefit and the amount of the benefit.",
            "metadata": {
                "category": "family_benefits",
                "language": "en",
                "source": "parental_benefits_overview",
            },
        },
        {
            "chunk_id": "test_doc_006_chunk_000",
            "document_hash": "test_doc_006",
            "chunk_index": 0,
            "original_content": "23,687 families and 78,296 children receive support for families with many children, including 117 families with seven or more children.",
            "context": "This chunk provides statistics on multi-child family support.",
            "contextual_content": "This chunk provides statistics on multi-child family support.\n\n23,687 families and 78,296 children receive support for families with many children, including 117 families with seven or more children.",
            "metadata": {
                "category": "family_benefits",
                "language": "en",
                "source": "family_support_stats",
            },
        },
        {
            "chunk_id": "test_doc_007_chunk_000",
            "document_hash": "test_doc_007",
            "chunk_index": 0,
            "original_content": "8,804 parents and 10,222 children receive single parent support.",
            "context": "This chunk provides single parent support statistics.",
            "contextual_content": "This chunk provides single parent support statistics.\n\n8,804 parents and 10,222 children receive single parent support.",
            "metadata": {
                "category": "single_parent_support",
                "language": "en",
                "source": "single_parent_stats",
            },
        },
        {
            "chunk_id": "test_doc_008_chunk_000",
            "document_hash": "test_doc_008",
            "chunk_index": 0,
            "original_content": "Single-parent (mostly mother) families are at the highest risk of poverty, of whom 5.3% live in absolute poverty and 27.3% in relative poverty.",
            "context": "This chunk discusses poverty risks for single-parent families.",
            "contextual_content": "This chunk discusses poverty risks for single-parent families.\n\nSingle-parent (mostly mother) families are at the highest risk of poverty, of whom 5.3% live in absolute poverty and 27.3% in relative poverty.",
            "metadata": {
                "category": "single_parent_support",
                "language": "en",
                "source": "poverty_statistics",
            },
        },
        {
            "chunk_id": "test_doc_009_chunk_000",
            "document_hash": "test_doc_009",
            "chunk_index": 0,
            "original_content": "Since January 2022, the Ministry of Social Affairs has been looking for solutions to support single-parent families.",
            "context": "This chunk describes ministry initiatives for single parents.",
            "contextual_content": "This chunk describes ministry initiatives for single parents.\n\nSince January 2022, the Ministry of Social Affairs has been looking for solutions to support single-parent families.",
            "metadata": {
                "category": "single_parent_support",
                "language": "en",
                "source": "ministry_initiatives_2022",
            },
        },
        {
            "chunk_id": "test_doc_010_chunk_000",
            "document_hash": "test_doc_010",
            "chunk_index": 0,
            "original_content": "Ticket refund is only possible if at least 60 minutes remain until the departure of the trip.",
            "context": "This chunk explains train ticket refund timing policy.",
            "contextual_content": "This chunk explains train ticket refund timing policy.\n\nTicket refund is only possible if at least 60 minutes remain until the departure of the trip.",
            "metadata": {
                "category": "train_services",
                "language": "en",
                "source": "elron_refund_policy",
            },
        },
        {
            "chunk_id": "test_doc_011_chunk_000",
            "document_hash": "test_doc_011",
            "chunk_index": 0,
            "original_content": "The ticket cost is refunded to the Elron travel card without service charge only if the refund request is submitted through the Elron homepage refund form.",
            "context": "This chunk describes fee-free refund process.",
            "contextual_content": "This chunk describes fee-free refund process.\n\nThe ticket cost is refunded to the Elron travel card without service charge only if the refund request is submitted through the Elron homepage refund form.",
            "metadata": {
                "category": "train_services",
                "language": "en",
                "source": "elron_refund_process",
            },
        },
        {
            "chunk_id": "test_doc_012_chunk_000",
            "document_hash": "test_doc_012",
            "chunk_index": 0,
            "original_content": "If ticket refund is requested to a bank account, a service fee of 1 euro is deducted from the refundable amount.",
            "context": "This chunk explains bank refund fees.",
            "contextual_content": "This chunk explains bank refund fees.\n\nIf ticket refund is requested to a bank account, a service fee of 1 euro is deducted from the refundable amount.",
            "metadata": {
                "category": "train_services",
                "language": "en",
                "source": "elron_bank_refund",
            },
        },
        {
            "chunk_id": "test_doc_013_chunk_000",
            "document_hash": "test_doc_013",
            "chunk_index": 0,
            "original_content": "Europe must act more jointly and in a more coordinated way to stop the spread of health-related misinformation, said Estonia's Minister of Social Affairs, Karmen Joller.",
            "context": "This chunk contains a minister's statement on health misinformation.",
            "contextual_content": "This chunk contains a minister's statement on health misinformation.\n\nEurope must act more jointly and in a more coordinated way to stop the spread of health-related misinformation, said Estonia's Minister of Social Affairs, Karmen Joller.",
            "metadata": {
                "category": "health_cooperation",
                "language": "en",
                "source": "minister_statement_eu",
            },
        },
        {
            "chunk_id": "test_doc_014_chunk_000",
            "document_hash": "test_doc_014",
            "chunk_index": 0,
            "original_content": "Estonian Minister of Social Affairs Karmen Joller and Ukrainian Minister of Health Viktor Liashko today signed the next stage of a health cooperation agreement.",
            "context": "This chunk announces a health cooperation agreement signing.",
            "contextual_content": "This chunk announces a health cooperation agreement signing.\n\nEstonian Minister of Social Affairs Karmen Joller and Ukrainian Minister of Health Viktor Liashko today signed the next stage of a health cooperation agreement.",
            "metadata": {
                "category": "health_cooperation",
                "language": "en",
                "source": "ukraine_agreement",
            },
        },
        {
            "chunk_id": "test_doc_015_chunk_000",
            "document_hash": "test_doc_015",
            "chunk_index": 0,
            "original_content": "The aim of the agreement is to reinforce health collaboration, support Ukraine's healthcare system recovery.",
            "context": "This chunk describes health agreement objectives.",
            "contextual_content": "This chunk describes health agreement objectives.\n\nThe aim of the agreement is to reinforce health collaboration, support Ukraine's healthcare system recovery.",
            "metadata": {
                "category": "health_cooperation",
                "language": "en",
                "source": "agreement_objectives",
            },
        },
    ]
