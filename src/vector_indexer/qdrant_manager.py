"""Qdrant vector database manager for storing contextual chunks."""

from typing import List, Dict, Any, Optional
from loguru import logger
import httpx
import uuid

from vector_indexer.config.config_loader import VectorIndexerConfig
from vector_indexer.models import ContextualChunk


class QdrantOperationError(Exception):
    """Custom exception for Qdrant operations."""

    pass


class QdrantManager:
    """Manages Qdrant vector database operations for contextual chunks."""

    def __init__(self, config: VectorIndexerConfig):
        self.config = config
        self.qdrant_url: str = getattr(config, "qdrant_url", "http://localhost:6333")
        self.client = httpx.AsyncClient(timeout=30.0)

        # Collection configurations based on embedding models
        self.collections_config: Dict[str, Dict[str, Any]] = {
            "contextual_chunks_azure": {
                "vector_size": 3072,  # text-embedding-3-large
                "distance": "Cosine",
                "models": ["text-embedding-3-large", "text-embedding-ada-002"],
            },
            "contextual_chunks_aws": {
                "vector_size": 1024,  # amazon.titan-embed-text-v2:0
                "distance": "Cosine",
                "models": [
                    "amazon.titan-embed-text-v2:0",
                    "amazon.titan-embed-text-v1",
                ],
            },
        }

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> None:
        """Async context manager exit."""
        await self.client.aclose()

    async def ensure_collections_exist(self):
        """Create collections if they don't exist."""
        logger.info("Ensuring Qdrant collections exist")

        for collection_name, config in self.collections_config.items():
            await self._create_collection_if_not_exists(collection_name, config)

    async def _create_collection_if_not_exists(
        self, collection_name: str, collection_config: Dict[str, Any]
    ):
        """Create a collection if it doesn't exist."""

        try:
            # Check if collection exists
            response = await self.client.get(
                f"{self.qdrant_url}/collections/{collection_name}"
            )

            if response.status_code == 200:
                logger.debug(f"Collection {collection_name} already exists")
                return
            elif response.status_code == 404:
                logger.info(f"Creating collection {collection_name}")

                # Create collection
                create_payload = {
                    "vectors": {
                        "size": collection_config["vector_size"],
                        "distance": collection_config["distance"],
                    },
                    "optimizers_config": {"default_segment_number": 2},
                    "replication_factor": 1,
                }

                response = await self.client.put(
                    f"{self.qdrant_url}/collections/{collection_name}",
                    json=create_payload,
                )

                if response.status_code in [200, 201]:
                    logger.info(f"Successfully created collection {collection_name}")
                else:
                    logger.error(
                        f"Failed to create collection {collection_name}: {response.status_code} {response.text}"
                    )

            else:
                logger.error(
                    f"Unexpected response checking collection {collection_name}: {response.status_code}"
                )

        except Exception as e:
            logger.error(f"Error ensuring collection {collection_name} exists: {e}")
            raise

    async def store_chunks(self, chunks: List[ContextualChunk]):
        """
        Store contextual chunks in appropriate Qdrant collection.

        Args:
            chunks: List of contextual chunks to store
        """
        if not chunks:
            logger.warning("No chunks to store")
            return

        logger.info(f"Storing {len(chunks)} chunks in Qdrant")

        # Group chunks by embedding model
        chunks_by_model: Dict[str, List[ContextualChunk]] = {}
        for chunk in chunks:
            model_key = self._get_collection_for_model(chunk.embedding_model)
            if model_key not in chunks_by_model:
                chunks_by_model[model_key] = []
            chunks_by_model[model_key].append(chunk)

        # Store chunks in appropriate collections
        for collection_name, chunk_list in chunks_by_model.items():
            await self._store_chunks_in_collection(collection_name, chunk_list)

    async def _store_chunks_in_collection(
        self, collection_name: str, chunks: List[ContextualChunk]
    ):
        """Store chunks in specific collection."""

        logger.debug(f"Storing {len(chunks)} chunks in collection {collection_name}")

        # Prepare points for upsert
        points: List[Dict[str, Any]] = []
        for chunk in chunks:
            if not chunk.embedding:
                logger.warning(f"Skipping chunk {chunk.chunk_id} - no embedding")
                continue

            # Convert chunk_id to UUID for Qdrant compatibility
            # Qdrant requires point IDs to be either integers or UUIDs
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.chunk_id))

            point = {
                "id": point_id,
                "vector": chunk.embedding,
                "payload": self._create_chunk_payload(chunk),
            }
            points.append(point)

        if not points:
            logger.warning(f"No valid points to store in {collection_name}")
            return

        try:
            # Upsert points in batches to avoid request size limits
            batch_size = 100
            for i in range(0, len(points), batch_size):
                batch = points[i : i + batch_size]

                upsert_payload = {"points": batch}

                # DEBUG: Log the actual HTTP request payload being sent to Qdrant
                logger.info("=== QDRANT HTTP REQUEST PAYLOAD DEBUG ===")
                logger.info(
                    f"URL: {self.qdrant_url}/collections/{collection_name}/points"
                )
                logger.info("Method: PUT")
                logger.info(f"Batch size: {len(batch)} points")
                for idx, point in enumerate(batch):
                    logger.info(f"Point {idx + 1}:")
                    logger.info(f"  ID: {point['id']} (type: {type(point['id'])})")
                    logger.info(
                        f"  Vector length: {len(point['vector'])} (type: {type(point['vector'])})"
                    )
                    logger.info(f"  Vector sample: {point['vector'][:3]}...")
                    logger.info(f"  Payload keys: {list(point['payload'].keys())}")
                logger.info("=== END QDRANT REQUEST DEBUG ===")

                response = await self.client.put(
                    f"{self.qdrant_url}/collections/{collection_name}/points",
                    json=upsert_payload,
                )

                if response.status_code in [200, 201]:
                    logger.debug(
                        f"Successfully stored batch {i // batch_size + 1} in {collection_name}"
                    )
                else:
                    logger.error(
                        f"Failed to store batch in {collection_name}: {response.status_code} {response.text}"
                    )
                    raise QdrantOperationError(
                        f"Qdrant upsert failed: {response.status_code}"
                    )

            logger.info(
                f"Successfully stored {len(points)} chunks in {collection_name}"
            )

        except Exception as e:
            logger.error(f"Error storing chunks in {collection_name}: {e}")
            raise

    def _create_chunk_payload(self, chunk: ContextualChunk) -> Dict[str, Any]:
        """Create payload for Qdrant point."""

        return {
            # Core identifiers
            "chunk_id": chunk.chunk_id,
            "document_hash": chunk.document_hash,
            "chunk_index": chunk.chunk_index,
            "total_chunks": chunk.total_chunks,
            # Content
            "original_content": chunk.original_content,
            "contextual_content": chunk.contextual_content,
            "context_only": chunk.context,
            # Embedding info
            "embedding_model": chunk.embedding_model,
            "vector_dimensions": chunk.vector_dimensions,
            # Document metadata
            "document_url": chunk.source_url,
            "dataset_collection": chunk.dataset_collection,
            # Processing metadata
            "processing_timestamp": chunk.processing_timestamp.isoformat(),
            "tokens_count": chunk.tokens_count,
            # Additional metadata from source
            "file_type": chunk.metadata.get("file_type"),
            "created_at": chunk.metadata.get("created_at"),
        }

    def _get_collection_for_model(self, embedding_model: Optional[str]) -> str:
        """Determine which collection to use based on embedding model."""

        if not embedding_model:
            logger.warning("No embedding model specified, using azure collection")
            return "contextual_chunks_azure"

        model_lower = embedding_model.lower()

        # Check Azure models
        for azure_model in self.collections_config["contextual_chunks_azure"]["models"]:
            if azure_model.lower() in model_lower:
                return "contextual_chunks_azure"

        # Check AWS models
        for aws_model in self.collections_config["contextual_chunks_aws"]["models"]:
            if aws_model.lower() in model_lower:
                return "contextual_chunks_aws"

        # Default to Azure if no match
        logger.warning(
            f"Unknown embedding model {embedding_model}, using azure collection"
        )
        return "contextual_chunks_azure"

    async def get_collection_info(
        self, collection_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get information about a collection."""

        try:
            response = await self.client.get(
                f"{self.qdrant_url}/collections/{collection_name}"
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(
                    f"Failed to get collection info for {collection_name}: {response.status_code}"
                )
                return None

        except Exception as e:
            logger.error(f"Error getting collection info for {collection_name}: {e}")
            return None

    async def count_points(self, collection_name: str) -> int:
        """Count points in a collection."""

        try:
            response = await self.client.get(
                f"{self.qdrant_url}/collections/{collection_name}"
            )

            if response.status_code == 200:
                collection_info = response.json()
                return collection_info.get("result", {}).get("points_count", 0)
            else:
                logger.error(
                    f"Failed to get point count for {collection_name}: {response.status_code}"
                )
                return 0

        except Exception as e:
            logger.error(f"Error counting points in {collection_name}: {e}")
            return 0

    async def delete_collection(self, collection_name: str) -> bool:
        """Delete a collection (for cleanup/testing)."""

        try:
            response = await self.client.delete(
                f"{self.qdrant_url}/collections/{collection_name}"
            )

            if response.status_code in [200, 404]:  # 404 means already deleted
                logger.info(f"Successfully deleted collection {collection_name}")
                return True
            else:
                logger.error(
                    f"Failed to delete collection {collection_name}: {response.status_code}"
                )
                return False

        except Exception as e:
            logger.error(f"Error deleting collection {collection_name}: {e}")
            return False

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
