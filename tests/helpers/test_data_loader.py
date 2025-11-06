"""Helper module to load test data into Qdrant before running tests."""

import os
import json
import requests
import uuid
from typing import List, Dict, Any
from loguru import logger
from datetime import datetime
from pathlib import Path

def load_test_data_into_qdrant(
    orchestration_url: str,
    qdrant_url: str,
) -> None:
    """Load test documents into Qdrant contextual collections for retrieval testing."""
    logger.info("Loading test data into Qdrant contextual collections...")

    test_documents = get_test_documents()

    try:
        # Create embeddings via orchestration service
        texts = [doc["contextual_content"] for doc in test_documents]

        logger.info(f"Creating embeddings for {len(texts)} documents...")

        # CRITICAL: Use correct test environment values
        embedding_response = requests.post(
            f"{orchestration_url}/embeddings",
            json={
                "texts": texts,
                "environment": "development",  # ← MUST be "development"
                "connection_id": "evalconnection-1",  # ← MUST match Vault
                "batch_size": 50,
            },
            timeout=120,
        )

        # Debug logging
        logger.info(f"Embedding API response status: {embedding_response.status_code}")
        if embedding_response.status_code != 200:
            logger.error(f"Embedding API error: {embedding_response.text}")
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
    """
    contexts: List[dict[str, Any]] = []
    
    # Get absolute path to data directory
    current_file = Path(__file__)  # tests/helpers/test_data_loader.py
    project_root = current_file.parent.parent.parent  # Go up to project root
    data_dir = project_root / "data" / "agencies_data"
    
    # Check if directory exists
    if not data_dir.exists():
        logger.error(f"Data directory not found: {data_dir}")
        raise FileNotFoundError(f"Data directory not found: {data_dir}")
    
    i = 0
    for i, agency in enumerate(os.listdir(data_dir)):
        agency_dir = data_dir / agency
        for _, topic in enumerate(os.listdir(agency_dir)):
            topic_dir = agency_dir / topic
            
            # Read cleaned text
            cleaned_file = topic_dir / "cleaned.txt"
            with open(cleaned_file, "r") as f:
                context_temp = f.read().strip().split("\n\n\n")
            
            current_contexts = [
                context.replace("\n\n", "\n") for context in context_temp
            ]
            
            # Read metadata
            meta_file = topic_dir / "cleaned.meta.json"
            with open(meta_file, "r") as f:
                metadata = json.load(f)
            
            for k, context in enumerate(current_contexts):
                context_dict = {
                    "chunk_id": f"test_doc_{i:03d}_chunk_{k:03d}",
                    "document_hash": f"test_doc_{i:03d}",
                    "chunk_index": k,
                    "original_content": context,
                    "context": context,
                    "contextual_content": context,
                    "metadata": {
                        "category": metadata.get(agency, "general"),
                        "language": "et",
                        "source": metadata.get("source_url", "unknown"),
                    },
                }
                contexts.append(context_dict)
                i += 1

    return contexts