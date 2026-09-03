"""Constants for vector indexer components."""

from typing import List


class DocumentConstants:
    """Constants for document processing and validation."""

    # Content validation
    MIN_CONTENT_LENGTH = 10
    MAX_CONTENT_LENGTH = 10_000_000  # 10MB text limit
    ENCODING = "utf-8"

    # Default file names
    DEFAULT_TARGET_FILE = "cleaned.txt"
    DEFAULT_METADATA_FILE = "cleaned.meta.json"

    # Directory scanning
    MAX_SCAN_DEPTH = 5
    DEFAULT_COLLECTION_NAME = "default"


class ValidationConstants:
    """Constants for document and metadata validation."""

    # Metadata validation
    MIN_METADATA_FIELDS = 1  # At least one field required
    REQUIRED_METADATA_FIELDS: List[str] = ["source_url"]

    # Document hash validation
    HASH_MIN_LENGTH = 8  # Minimum hash length for document IDs
    HASH_MAX_LENGTH = 64  # Maximum hash length for document IDs

    # File size validation
    MIN_FILE_SIZE_BYTES = 1
    MAX_FILE_SIZE_BYTES = 50_000_000  # 50MB file size limit


class PerformanceConstants:
    """Constants for performance optimization."""

    # Caching
    DEFAULT_CACHE_SIZE_MB = 100
    CACHE_ENABLED_DEFAULT = False

    # Concurrency
    DEFAULT_MAX_CONCURRENT_DOCS = 5
    DEFAULT_MAX_CONCURRENT_CHUNKS = 10

    # Batch processing
    DEFAULT_BATCH_SIZE = 50
    MAX_BATCH_SIZE = 1000


class ChunkingConstants:
    """Constants for document chunking operations."""

    # Token estimation
    CHARS_PER_TOKEN = 4  # Rough estimate for fallback tokenization
    CHARS_PER_TOKEN_FALLBACK = 4  # Duplicate constant for token estimation

    # Chunk size limits
    MIN_CHUNK_SIZE_TOKENS = 50  # Minimum viable chunk size
    MAX_CHUNK_SIZE_TOKENS = 2000  # Safety limit for very large chunks

    # Tokenizer configuration
    DEFAULT_TOKENIZER_ENCODING = "cl100k_base"  # OpenAI's tiktoken encoding

    # Chunk ID formatting
    CHUNK_ID_PATTERN = "{document_hash}_chunk_{index:03d}"
    CHUNK_ID_SEPARATOR = "_chunk_"
    CHUNK_ID_PADDING = 3  # Number of digits for zero-padding

    # Content templates (Anthropic methodology)
    CONTEXTUAL_CONTENT_TEMPLATE = "{context}\n\n{content}"
    CONTEXT_CONTENT_SEPARATOR = "\n\n"

    # Content quality thresholds
    MIN_CONTENT_LENGTH = 10  # Minimum characters for valid content
    MAX_WHITESPACE_RATIO = 0.8  # Maximum ratio of whitespace to content


class ProcessingConstants:
    """Constants for processing operations."""

    # Batch processing delays
    BATCH_DELAY_SECONDS = 0.1  # Delay between embedding batches
    CONTEXT_DELAY_SECONDS = 0.05  # Delay between context generation batches

    # Provider detection patterns
    AZURE_PATTERNS = ["azure", "text-embedding-3"]
    AWS_PATTERNS = ["amazon", "titan"]
    OPENAI_PATTERNS = ["openai", "gpt"]

    # Quality validation
    MIN_WORD_COUNT = 5  # Minimum words for valid chunk content
    MAX_REPETITION_RATIO = 0.5  # Maximum allowed repetition in content


class ResponseGenerationConstants:
    """Constants for response generation and context retrieval."""

    # Controls both:
    #   1. How many chunks the contextual retriever returns after RRF fusion
    #   2. How many context blocks the response generator feeds to the LLM
    # Change this value to adjust both retrieval and generation together.
    DEFAULT_MAX_BLOCKS = 5
    MIN_BLOCKS_REQUIRED = 3  # Minimum blocks required for valid response


class LoggingConstants:
    """Constants for logging configuration."""

    # Log levels
    DEFAULT_LOG_LEVEL = "INFO"
    DEBUG_LOG_LEVEL = "DEBUG"

    # Log file settings
    LOG_ROTATION_SIZE = "10 MB"
    LOG_RETENTION_DAYS = "7 days"

    # Progress reporting
    PROGRESS_REPORT_INTERVAL = 10  # Report every N documents


def get_s3_ferry_payload(
    destination_file_path: str,
    destination_storage_type: str,
    source_file_path: str,
    source_storage_type: str,
) -> dict[str, str]:
    """
    Generate S3Ferry payload for file transfer operations.

    Args:
        destination_file_path: Path where file should be stored
        destination_storage_type: "S3" or "FS" (filesystem)
        source_file_path: Path of source file
        source_storage_type: "S3" or "FS" (filesystem)

    Returns:
        dict: Payload for S3Ferry API
    """
    return {
        "destinationFilePath": destination_file_path,
        "destinationStorageType": destination_storage_type,
        "sourceFilePath": source_file_path,
        "sourceStorageType": source_storage_type,
    }
