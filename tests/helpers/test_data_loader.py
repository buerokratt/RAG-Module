"""Helper module to load test data into Qdrant before running tests."""

import json
import uuid
from typing import List, Dict, Any, Tuple
from pathlib import Path
from loguru import logger
from datetime import datetime
import httpx


def load_test_data_into_qdrant(
    orchestration_url: str,
    qdrant_url: str,
) -> None:
    """Load test documents into Qdrant contextual collections for retrieval testing."""
    logger.info("Loading test data into Qdrant contextual collections...")

    # Load pre-computed embeddings
    embeddings_file = Path(__file__).parent.parent / "data" / "test_embeddings.json"

    if not embeddings_file.exists():
        raise FileNotFoundError(
            f"Pre-computed embeddings not found at {embeddings_file}. "
            "Run create_embeddings.py first!"
        )

    logger.info(f"Loading pre-computed embeddings from {embeddings_file}")
    chunks_data, model_used = load_precomputed_embeddings(embeddings_file)

    # Index into Qdrant
    index_embeddings_to_qdrant(
        qdrant_url=qdrant_url, chunks_data=chunks_data, model_used=model_used
    )


def load_precomputed_embeddings(
    embeddings_file: Path,
) -> Tuple[List[Dict[str, Any]], str]:
    """Load pre-computed embeddings from file."""
    with open(embeddings_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    chunks_data = data["chunks"]
    model_used = data["model_used"]

    logger.info(f"Loaded {len(chunks_data)} pre-computed chunks")
    logger.info(f"   Vector size: {data['vector_size']}")
    logger.info(f"   Model: {model_used}")
    logger.info(f"   Documents: {data['total_documents']}")

    return chunks_data, model_used


def index_embeddings_to_qdrant(
    qdrant_url: str, chunks_data: List[Dict[str, Any]], model_used: str
) -> None:
    """Index embeddings into Qdrant."""
    if not chunks_data:
        logger.warning("No chunks to index")
        return

    vector_size = chunks_data[0]["vector_dimensions"]
    collection_name = _determine_collection_from_model(model_used)

    logger.info(f"Indexing into Qdrant collection: {collection_name}")

    client = httpx.Client(timeout=30.0)

    try:
        # Check if collection exists
        response = client.get(f"{qdrant_url}/collections/{collection_name}")

        if response.status_code == 404:
            logger.info(f"Creating collection '{collection_name}'...")
            create_payload = {
                "vectors": {
                    "size": vector_size,
                    "distance": "Cosine",
                },
                "optimizers_config": {"default_segment_number": 2},
                "replication_factor": 1,
            }

            response = client.put(
                f"{qdrant_url}/collections/{collection_name}", json=create_payload
            )

            if response.status_code not in [200, 201]:
                raise RuntimeError(f"Failed to create collection: {response.text}")

            logger.info(f"Created collection '{collection_name}'")
        else:
            logger.info(f"Collection '{collection_name}' already exists")

        # Prepare points
        points = []
        for chunk in chunks_data:
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk["chunk_id"]))

            payload = {
                "chunk_id": chunk["chunk_id"],
                "document_hash": chunk["document_hash"],
                "chunk_index": chunk["chunk_index"],
                "total_chunks": chunk["total_chunks"],
                "original_content": chunk["original_content"],
                "contextual_content": chunk["contextual_content"],
                "context_only": chunk["context"],
                "embedding_model": chunk["embedding_model"],
                "vector_dimensions": chunk["vector_dimensions"],
                "document_url": chunk["metadata"].get("source", "test_document"),
                "dataset_collection": chunk["metadata"].get(
                    "dataset_collection", "test_collection"
                ),
                "processing_timestamp": datetime.now().isoformat(),
                "tokens_count": chunk["tokens_count"],
                **chunk["metadata"],
            }

            points.append(
                {"id": point_id, "vector": chunk["embedding"], "payload": payload}
            )

        # Upsert points in batches
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            upsert_payload = {"points": batch}

            response = client.put(
                f"{qdrant_url}/collections/{collection_name}/points",
                json=upsert_payload,
            )

            if response.status_code not in [200, 201]:
                raise RuntimeError(f"Failed to upsert points: {response.text}")

            logger.info(f"Indexed batch {i // batch_size + 1} ({len(batch)} points)")

        client.close()

        logger.info(f" Successfully indexed {len(points)} chunks into Qdrant")

    except Exception as e:
        logger.error(f"Failed to index to Qdrant: {e}")
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
