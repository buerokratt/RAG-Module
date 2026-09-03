"""Data models for diff identifier."""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ProcessedFileInfo(BaseModel):
    """Information about a processed file."""

    content_hash: str = Field(..., description="SHA256 hash of file content")
    original_path: str = Field(..., description="Original path in datasets folder")
    file_size: int = Field(..., description="File size in bytes")
    processed_at: str = Field(..., description="ISO timestamp when file was processed")
    chunk_count: int = Field(
        default=0, description="Number of chunks created from this file"
    )


class DiffResult(BaseModel):
    """Result of diff identification process."""

    new_files: List[str] = Field(..., description="List of new file paths to process")
    modified_files: List[str] = Field(
        default_factory=list, description="List of modified file paths to reprocess"
    )
    deleted_files: List[str] = Field(
        default_factory=list,
        description="List of deleted file paths (chunks to remove)",
    )
    unchanged_files: List[str] = Field(
        default_factory=list,
        description="List of unchanged file paths (skip processing)",
    )

    total_files_scanned: int = Field(
        ..., description="Total files found in current scan"
    )
    previously_processed_count: int = Field(
        ..., description="Number of previously processed files"
    )
    is_first_run: bool = Field(
        ..., description="Whether this is the first time running"
    )

    # Cleanup metadata
    chunks_to_delete: Dict[str, str] = Field(
        default_factory=dict,
        description="Map of document_hash to original_path for deletion",
    )
    estimated_cleanup_count: int = Field(
        default=0, description="Total estimated chunks to be removed"
    )


class VersionState(BaseModel):
    """Version state information."""

    last_updated: str = Field(..., description="ISO timestamp of last update")
    processed_files: Dict[str, ProcessedFileInfo] = Field(
        ..., description="Map of hash to file info"
    )
    total_processed: int = Field(..., description="Total number of processed files")
    processing_stats: Dict[str, Any] = Field(
        default_factory=dict, description="Statistics from last processing run"
    )


class DiffConfig(BaseModel):
    """Configuration for diff identifier."""

    # S3Ferry Configuration (handles metadata operations)
    s3_ferry_url: str = Field(..., description="S3Ferry service URL")

    # Metadata Configuration
    metadata_s3_path: str = Field(..., description="Full S3 path for metadata file")

    # DVC Configuration (requires direct S3 access for version control)
    datasets_path: str = Field(..., description="Path to datasets folder")
    metadata_filename: str = Field(
        default="processed-metadata.json", description="Metadata file name"
    )

    # DVC S3 Remote Configuration (minimal - only for DVC operations)
    dvc_remote_url: str = Field(..., description="DVC S3 remote URL")
    s3_endpoint_url: str = Field(..., description="S3 endpoint URL for DVC")
    s3_access_key_id: str = Field(..., description="S3 access key for DVC")
    s3_secret_access_key: str = Field(..., description="S3 secret key for DVC")

    # Retry Configuration
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    max_delay_seconds: int = Field(
        default=8, description="Maximum delay between retries"
    )


class DiffError(Exception):
    """Custom exception for diff identification errors."""

    def __init__(self, message: str, cause: Optional[Exception] = None) -> None:
        self.message = message
        self.cause = cause
        super().__init__(self.message)
