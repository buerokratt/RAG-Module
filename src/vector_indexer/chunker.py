"""Chunk retriever module for processing datasets and creating embeddings."""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import uuid
from dataclasses import dataclass
import logging

from openai import AzureOpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
)

from vector_indexer.chunk_config import ChunkConfig

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TextChunk:
    """Represents a text chunk with metadata."""

    text: str
    chunk_id: str
    document_id: str
    chunk_index: int
    metadata: Dict[str, Any]
    source_file: str


class DocumentProcessor:
    """Processes documents and creates text chunks."""

    def __init__(self, config: ChunkConfig):
        """Initialize the document processor.

        Args:
            config: Configuration for chunk processing.
        """
        self.config = config

    def create_chunks(
        self, text: str, document_id: str, source_file: str
    ) -> List[TextChunk]:
        """Create chunks from text.

        Args:
            text: The text to chunk.
            document_id: Unique identifier for the document.
            source_file: Path to the source file.

        Returns:
            List of TextChunk objects.
        """
        # Simple sliding window chunking
        chunks: List[TextChunk] = []
        start = 0
        chunk_index = 0

        while start < len(text):
            end = min(start + self.config.chunk_size, len(text))

            # Try to break at sentence boundary if possible
            if end < len(text):
                # Look for sentence endings within overlap distance
                sentence_break = self._find_sentence_break(
                    text, end, self.config.chunk_overlap
                )
                if sentence_break is not None:
                    end = sentence_break

            chunk_text = text[start:end].strip()

            if chunk_text:
                chunk = TextChunk(
                    text=chunk_text,
                    chunk_id=f"{document_id}_chunk_{chunk_index}",
                    document_id=document_id,
                    chunk_index=chunk_index,
                    metadata={
                        "source_file": source_file,
                        "chunk_size": len(chunk_text),
                        "start_char": start,
                        "end_char": end,
                    },
                    source_file=source_file,
                )
                chunks.append(chunk)
                chunk_index += 1

            # Move start position with overlap
            start = max(start + self.config.chunk_size - self.config.chunk_overlap, end)

        return chunks

    def _find_sentence_break(
        self, text: str, position: int, search_distance: int
    ) -> Optional[int]:
        """Find a good sentence break point near the given position.

        Args:
            text: The text to search in.
            position: Target position to break at.
            search_distance: Distance to search for sentence breaks.

        Returns:
            Position of sentence break or None if not found.
        """
        start_search = max(0, position - search_distance)
        end_search = min(len(text), position + search_distance)
        search_text = text[start_search:end_search]

        # Look for sentence endings (., !, ?)
        sentence_endings = [m.end() for m in re.finditer(r"[.!?]\s+", search_text)]

        if sentence_endings:
            # Find the closest to our target position
            target_in_search = position - start_search
            closest = min(sentence_endings, key=lambda x: abs(x - target_in_search))
            return start_search + closest

        return None


class EmbeddingGenerator:
    """Generates embeddings using Azure OpenAI."""

    def __init__(self, config: ChunkConfig):
        """Initialize the embedding generator.

        Args:
            config: Configuration for embedding generation.
        """
        self.config = config
        config.validate()

        if not config.azure_embedding_endpoint:
            raise ValueError("Azure embedding endpoint is required")
        if not config.azure_embedding_deployment_name:
            raise ValueError("Azure embedding deployment name is required")

        self.client = AzureOpenAI(
            api_key=config.azure_embedding_api_key,
            api_version=config.azure_embedding_api_version,
            azure_endpoint=config.azure_embedding_endpoint,
        )

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors.
        """
        try:
            deployment_name = self.config.azure_embedding_deployment_name
            if not deployment_name:
                raise ValueError("Azure embedding deployment name is required")

            response = self.client.embeddings.create(input=texts, model=deployment_name)

            embeddings = [data.embedding for data in response.data]
            logger.info(f"Generated embeddings for {len(texts)} texts")
            return embeddings

        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise

    def generate_embedding_batch(
        self, chunks: List[TextChunk]
    ) -> List[Tuple[TextChunk, List[float]]]:
        """Generate embeddings for a batch of chunks.

        Args:
            chunks: List of TextChunk objects.

        Returns:
            List of tuples (chunk, embedding).
        """
        texts = [chunk.text for chunk in chunks]
        embeddings = self.generate_embeddings(texts)

        return list(zip(chunks, embeddings))


class QdrantManager:
    """Manages Qdrant vector database operations."""

    def __init__(self, config: ChunkConfig):
        """Initialize the Qdrant manager.

        Args:
            config: Configuration for Qdrant operations.
        """
        self.config = config
        self.client = QdrantClient(
            host=config.qdrant_host,
            port=config.qdrant_port,
            timeout=config.qdrant_timeout,  # type: ignore
        )
        logger.info(f"Connected to Qdrant at {config.qdrant_host}:{config.qdrant_port}")

    def ensure_collection(self) -> None:
        """Ensure the collection exists in Qdrant."""
        try:
            # Check if collection exists
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]

            if self.config.qdrant_collection not in collection_names:
                logger.info(f"Creating collection: {self.config.qdrant_collection}")
                self.client.create_collection(
                    collection_name=self.config.qdrant_collection,
                    vectors_config=VectorParams(
                        size=self.config.embedding_dimension, distance=Distance.COSINE
                    ),
                )
            else:
                logger.info(
                    f"Collection {self.config.qdrant_collection} already exists"
                )

        except Exception as e:
            logger.error(f"Failed to ensure collection: {e}")
            raise

    def store_embeddings(
        self, chunk_embeddings: List[Tuple[TextChunk, List[float]]]
    ) -> None:
        """Store embeddings in Qdrant.

        Args:
            chunk_embeddings: List of tuples (chunk, embedding).
        """
        points: List[PointStruct] = []

        for chunk, embedding in chunk_embeddings:
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "chunk_index": chunk.chunk_index,
                    "text": chunk.text,
                    "source_file": chunk.source_file,
                    "metadata": chunk.metadata,
                },
            )
            points.append(point)

        try:
            self.client.upsert(
                collection_name=self.config.qdrant_collection, points=points
            )
            logger.info(f"Stored {len(points)} embeddings in Qdrant")

        except Exception as e:
            logger.error(f"Failed to store embeddings: {e}")
            raise


class ChunkRetriever:
    """Main class for processing datasets and creating embeddings."""

    def __init__(self, config: Optional[ChunkConfig] = None):
        """Initialize the chunk retriever.

        Args:
            config: Configuration for chunk retrieval. If None, uses default config.
        """
        self.config = config or ChunkConfig()
        self.processor = DocumentProcessor(self.config)
        self.embedding_generator = EmbeddingGenerator(self.config)
        self.qdrant_manager = QdrantManager(self.config)

        # Ensure Qdrant collection exists
        self.qdrant_manager.ensure_collection()

    def discover_documents(
        self, dataset_path: Optional[str] = None
    ) -> List[Tuple[str, str]]:
        """Discover cleaned.txt files in the dataset directory.

        Args:
            dataset_path: Path to the dataset directory. If None, uses config default.

        Returns:
            List of tuples (document_id, file_path).
        """
        base_path = Path(dataset_path or self.config.dataset_path)
        documents: List[Tuple[str, str]] = []

        # Look for cleaned.txt files in the dataset structure
        for txt_file in base_path.rglob("cleaned.txt"):
            # Use the parent directory name as document ID
            document_id = txt_file.parent.name
            documents.append((document_id, str(txt_file)))

        logger.info(f"Discovered {len(documents)} documents")
        return documents

    def load_document(self, file_path: str) -> str:
        """Load text content from a file.

        Args:
            file_path: Path to the text file.

        Returns:
            Text content of the file.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            logger.info(f"Loaded document: {file_path} ({len(content)} characters)")
            return content
        except Exception as e:
            logger.error(f"Failed to load document {file_path}: {e}")
            raise

    def process_documents(self, dataset_path: Optional[str] = None) -> None:
        """Process all documents in the dataset and store embeddings.

        Args:
            dataset_path: Path to the dataset directory. If None, uses config default.
        """
        documents = self.discover_documents(dataset_path)

        if not documents:
            logger.warning("No documents found to process")
            return

        total_chunks = 0

        for document_id, file_path in documents:
            logger.info(f"Processing document: {document_id}")

            try:
                # Load document content
                text = self.load_document(file_path)

                # Create chunks
                chunks = self.processor.create_chunks(text, document_id, file_path)
                logger.info(f"Created {len(chunks)} chunks for document {document_id}")

                # Process chunks in batches
                for i in range(0, len(chunks), self.config.batch_size):
                    batch = chunks[i : i + self.config.batch_size]

                    # Generate embeddings
                    chunk_embeddings = (
                        self.embedding_generator.generate_embedding_batch(batch)
                    )

                    # Store in Qdrant
                    self.qdrant_manager.store_embeddings(chunk_embeddings)

                    total_chunks += len(batch)
                    logger.info(
                        f"Processed batch {i // self.config.batch_size + 1} for document {document_id}"
                    )

            except Exception as e:
                logger.error(f"Failed to process document {document_id}: {e}")
                continue

        logger.info(f"Processing complete. Total chunks processed: {total_chunks}")

    def search_similar(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for similar chunks using a query.

        Args:
            query: Search query text.
            limit: Maximum number of results to return.

        Returns:
            List of similar chunks with scores.
        """
        try:
            # Generate embedding for query
            query_embedding = self.embedding_generator.generate_embeddings([query])[0]

            # Search in Qdrant
            search_result = self.qdrant_manager.client.search(
                collection_name=self.config.qdrant_collection,
                query_vector=query_embedding,
                limit=limit,
            )

            results: List[Dict[str, Any]] = []
            for scored_point in search_result:
                payload = scored_point.payload or {}
                results.append(
                    {
                        "score": scored_point.score,
                        "chunk_id": payload.get("chunk_id", ""),
                        "document_id": payload.get("document_id", ""),
                        "text": payload.get("text", ""),
                        "source_file": payload.get("source_file", ""),
                        "metadata": payload.get("metadata", {}),
                    }
                )

            return results

        except Exception as e:
            logger.error(f"Failed to search similar chunks: {e}")
            raise


def main():
    """CLI interface for chunker operations."""
    import argparse
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(
        description="Document Chunker and Embedding Storage"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Process command
    process_parser = subparsers.add_parser(
        "process", help="Process documents and store embeddings"
    )
    process_parser.add_argument(
        "--dataset-path",
        default="data_sets",
        help="Path to dataset directory (default: data_sets)",
    )
    process_parser.add_argument(
        "--environment",
        default="development",
        choices=["development", "staging", "production", "testing"],
        help="Environment for configuration (default: development)",
    )
    process_parser.add_argument(
        "--connection-id", help="Vault connection ID for configuration (optional)"
    )

    # Search command
    search_parser = subparsers.add_parser("search", help="Search for similar chunks")
    search_parser.add_argument("query", help="Search query text")
    search_parser.add_argument(
        "--limit", type=int, default=5, help="Number of results (default: 5)"
    )
    search_parser.add_argument(
        "--environment",
        default="development",
        choices=["development", "staging", "production", "testing"],
        help="Environment for configuration (default: development)",
    )
    search_parser.add_argument(
        "--connection-id", help="Vault connection ID for configuration (optional)"
    )

    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Setup Qdrant collection")
    setup_parser.add_argument(
        "--environment",
        default="development",
        choices=["development", "staging", "production", "testing"],
        help="Environment for configuration (default: development)",
    )
    setup_parser.add_argument(
        "--connection-id", help="Vault connection ID for configuration (optional)"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == "process":
            # Check if dataset path exists
            dataset_path = Path(args.dataset_path)
            if not dataset_path.exists():
                logger.error(f"Dataset path does not exist: {dataset_path}")
                sys.exit(1)

            # Create configuration
            config = ChunkConfig()
            config.dataset_path = str(dataset_path)

            # Initialize retriever
            retriever = ChunkRetriever(config)

            # Process all documents in the dataset
            logger.info(f"Processing documents from: {dataset_path}")
            retriever.process_documents(str(dataset_path))
            logger.info("Processing completed successfully!")

        elif args.command == "search":
            # Create configuration
            config = ChunkConfig()

            # Initialize retriever
            retriever = ChunkRetriever(config)

            # Perform search
            logger.info(f"Searching for: {args.query}")
            results = retriever.search_similar(args.query, args.limit)

            if results:
                print(f"\nFound {len(results)} similar chunks:")
                print("-" * 80)
                for i, result in enumerate(results, 1):
                    print(f"Result {i}:")
                    print(f"  Score: {result['score']:.4f}")
                    print(f"  Document ID: {result['document_id']}")
                    print(f"  Chunk ID: {result['chunk_id']}")
                    print(f"  Source: {result['source_file']}")
                    print(f"  Text: {result['text'][:200]}...")
                    print("-" * 80)
            else:
                print("No similar chunks found.")

        elif args.command == "setup":
            # Create configuration
            config = ChunkConfig()

            # Initialize retriever
            retriever = ChunkRetriever(config)

            # Setup collection
            logger.info("Setting up Qdrant collection...")
            retriever.qdrant_manager.ensure_collection()
            logger.info("Collection setup completed successfully!")

    except Exception as e:
        logger.error(f"Command failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
