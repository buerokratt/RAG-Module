"""
Integration tests for the vector indexing pipeline.

These tests verify the full flow:
1. Upload document to MinIO
2. Generate presigned URL
3. Run VectorIndexer
4. Verify embeddings in Qdrant
"""

import pytest
import zipfile
import tempfile
from pathlib import Path
from datetime import timedelta
import json
import requests
import sys
import time
from loguru import logger

from minio import Minio
from qdrant_client import QdrantClient

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


class TestIndexingPipeline:
    """Test the complete indexing pipeline from MinIO to Qdrant."""

    def test_minio_connection(self, minio_client: Minio):
        """Verify MinIO is accessible."""
        # List buckets to verify connection
        buckets = minio_client.list_buckets()
        assert buckets is not None

    def test_qdrant_connection(self, qdrant_client: QdrantClient):
        """Verify Qdrant is accessible."""
        # Get collections to verify connection
        collections = qdrant_client.get_collections()
        assert collections is not None

    def test_create_and_upload_document(self, minio_client: Minio, test_bucket: str):
        """Test document upload to MinIO."""
        # Verify bucket was created
        assert minio_client.bucket_exists(test_bucket)

        # Create and upload a simple test file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test content")
            temp_path = f.name

        try:
            minio_client.fput_object(test_bucket, "test.txt", temp_path)

            # Verify object exists
            stat = minio_client.stat_object(test_bucket, "test.txt")
            assert stat is not None
            assert stat.size > 0
        finally:
            Path(temp_path).unlink()

    def test_presigned_url_generation(self, minio_client: Minio, test_document):
        """Test presigned URL generation."""
        bucket_name, object_prefix, _ = test_document

        # Generate presigned URL
        url = minio_client.presigned_get_object(
            bucket_name, f"{object_prefix}/cleaned.txt", expires=timedelta(hours=1)
        )

        assert url is not None
        assert "localhost:9000" in url
        assert bucket_name in url

    def test_document_structure(self, minio_client: Minio, test_document):
        """Verify test document has correct structure."""
        bucket_name, object_prefix, local_path = test_document

        # Check local files exist
        cleaned_file = local_path / "cleaned.txt"
        meta_file = local_path / "source.meta.json"

        assert cleaned_file.exists()
        assert meta_file.exists()

        # Verify content
        content = cleaned_file.read_text()
        assert "RAG" in content
        assert "integration testing" in content

        # Verify metadata
        meta = json.loads(meta_file.read_text())
        assert meta["source"] == "integration_test"
        assert "title" in meta

    @pytest.mark.asyncio
    async def test_indexing_pipeline_e2e(
        self,
        rag_stack,
        minio_client: Minio,
        qdrant_client: QdrantClient,
        test_bucket: str,
        postgres_client,
        setup_agency_sync_schema,
        tmp_path: Path,
        llm_orchestration_url: str,
    ):
        """
        End-to-end test of the indexing pipeline using Ruuter and Cron-Manager.

        This test:
        1. Creates test document and uploads to MinIO
        2. Generates presigned URL
        3. Prepares database (agency_sync + mock_ckb)
        4. Calls Ruuter endpoint to trigger indexing via Cron-Manager
        5. Waits for async indexing to complete (polls Qdrant)
        6. Verifies vectors stored in Qdrant
        """
        # Step 0: Wait for LLM orchestration service to be healthy
        max_retries = 30
        for i in range(max_retries):
            try:
                response = requests.get(f"{llm_orchestration_url}/health", timeout=5)
                if response.status_code == 200:
                    health_data = response.json()
                    if health_data.get("orchestration_service") == "initialized":
                        break
            except requests.exceptions.RequestException:
                logger.debug(
                    f"LLM orchestration health check attempt {i + 1}/{max_retries} failed"
                )
            time.sleep(2)
        else:
            pytest.fail("LLM orchestration service not healthy after 60 seconds")

        # Step 1: Create test document and upload to MinIO
        # Create structure: test_agency/<hash_dir>/cleaned.txt
        # so when extracted it becomes: extracted_datasets/test_agency/<hash_dir>/cleaned.txt
        # The document loader expects: collection/hash_dir/cleaned.txt
        source_dir = tmp_path / "source"
        hash_dir = source_dir / "test_agency" / "doc_hash_001"
        hash_dir.mkdir(parents=True)
        dataset_dir = hash_dir

        cleaned_content = """This is an integration test document for the RAG Module.

It tests the full vector indexing pipeline from end to end.

The document will be chunked and embedded using the configured embedding model.

Each chunk will be stored in Qdrant with contextual information generated by the LLM.

The RAG (Retrieval-Augmented Generation) system uses semantic search to find relevant documents.

Vector embeddings are numerical representations of text that capture semantic meaning.

Qdrant is a vector database that enables fast similarity search across embeddings.

The contextual retrieval process adds context to each chunk before embedding.

This helps improve search accuracy by providing more context about each chunk's content.

The LLM orchestration service manages connections to various language model providers.

Supported providers include Azure OpenAI and AWS Bedrock for both LLM and embedding models.

Integration testing ensures all components work together correctly in the pipeline.

The MinIO object storage is used to store and retrieve dataset files for processing.

Presigned URLs allow secure, temporary access to objects in MinIO buckets.

The vector indexer downloads datasets, processes documents, and stores embeddings.

Each document goes through chunking, contextual enrichment, and embedding stages.

The final embeddings are upserted into Qdrant collections for later retrieval.

This test verifies the complete flow from upload to storage in the vector database.
"""
        (dataset_dir / "cleaned.txt").write_text(cleaned_content)

        meta = {
            "source": "e2e_test",
            "title": "E2E Test Document",
            "agency_id": "test_agency",
        }
        (dataset_dir / "cleaned.meta.json").write_text(json.dumps(meta))

        # Create ZIP without datasets/ prefix - just test_agency/files
        zip_path = tmp_path / "test_dataset.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in dataset_dir.rglob("*"):
                if file.is_file():
                    # Archive path: test_agency/cleaned.txt
                    arcname = file.relative_to(source_dir)
                    zf.write(file, arcname)

        object_name = "datasets/test_dataset.zip"
        minio_client.fput_object(test_bucket, object_name, str(zip_path))

        # Use simple direct URL instead of presigned URL
        # Bucket is public, so no signature needed
        dataset_url = f"http://minio:9000/{test_bucket}/{object_name}"
        logger.info(f"Dataset URL for Docker network: {dataset_url}")

        # Step 1: Prepare database state for agency sync
        cursor = postgres_client.cursor()
        try:
            # Insert agency_sync record with initial hash
            cursor.execute(
                """
                INSERT INTO public.agency_sync (agency_id, agency_data_hash, data_url)
                VALUES (%s, %s, %s)
                ON CONFLICT (agency_id) DO UPDATE
                SET agency_data_hash = EXCLUDED.agency_data_hash
                """,
                ("test_agency", "initial_hash_000", ""),
            )

            # Insert mock CKB data with new hash and presigned URL
            cursor.execute(
                """
                INSERT INTO public.mock_ckb (client_id, client_data_hash, signed_s3_url)
                VALUES (%s, %s, %s)
                ON CONFLICT (client_id) DO UPDATE
                SET client_data_hash = EXCLUDED.client_data_hash,
                    signed_s3_url = EXCLUDED.signed_s3_url
                """,
                ("test_agency", "new_hash_001", dataset_url),
            )

            postgres_client.commit()
            logger.info(
                "Database prepared: agency_sync (initial_hash_000) and mock_ckb (new_hash_001)"
            )
        finally:
            cursor.close()

        # Step 2: Call Ruuter Public endpoint to trigger indexing via Cron-Manager
        logger.info("Calling /rag-search/data/update to trigger indexing...")
        ruuter_public_url = "http://localhost:8086"

        response = requests.post(
            f"{ruuter_public_url}/rag-search/data/update",
            json={},  # No body required
            timeout=60,
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()
        response_data = data.get("response", {})
        assert response_data.get("operationSuccessful") is True, (
            f"Operation failed: {data}"
        )
        logger.info(
            f"Indexing triggered successfully: {response_data.get('message', 'No message')}"
        )

        # Give Cron-Manager time to start the indexing process
        logger.info("Waiting 5 seconds for Cron-Manager to start indexing...")
        time.sleep(5)

        # Step 3: Wait for indexing to complete (poll Qdrant with verbose logging)
        import asyncio

        max_wait = 120  # 2 minutes
        poll_interval = 5  # seconds
        start_time = time.time()

        logger.info(f"Waiting for indexing to complete (max {max_wait}s)...")

        # First, wait for collection to be created
        collection_created = False
        logger.info("Waiting for collection 'contextual_chunks_azure' to be created...")

        while time.time() - start_time < max_wait:
            elapsed = time.time() - start_time

            try:
                # Try to get collection info (will fail if doesn't exist)
                collection_info = qdrant_client.get_collection(
                    "contextual_chunks_azure"
                )
                if collection_info:
                    logger.info(
                        f"[{elapsed:.1f}s] Collection 'contextual_chunks_azure' created!"
                    )
                    collection_created = True
                    break
            except Exception as e:
                logger.debug(
                    f"[{elapsed:.1f}s] Collection not yet created: {type(e).__name__}"
                )

            await asyncio.sleep(poll_interval)

        if not collection_created:
            # Capture Cron-Manager logs for debugging
            import subprocess

            try:
                logger.error(
                    "Collection was not created - capturing Cron-Manager logs..."
                )
                result = subprocess.run(
                    ["docker", "logs", "cron-manager", "--tail", "200"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                logger.error("=" * 80)
                logger.error("CRON-MANAGER LOGS:")
                logger.error("=" * 80)
                if result.stdout:
                    logger.error(result.stdout)
                if result.stderr:
                    logger.error(f"STDERR: {result.stderr}")
            except Exception as e:
                logger.error(f"Failed to capture logs: {e}")

            pytest.fail(
                f"Collection 'contextual_chunks_azure' was not created within {max_wait}s timeout"
            )

        # Now wait for documents to be indexed
        indexing_completed = False
        logger.info("Waiting for documents to be indexed in contextual_chunks_azure...")
        poll_count = 0
        while time.time() - start_time < max_wait:
            elapsed = time.time() - start_time
            poll_count += 1

            try:
                azure_points = qdrant_client.count(
                    collection_name="contextual_chunks_azure"
                )
                current_count = azure_points.count

                logger.info(
                    f"[{elapsed:.1f}s] Polling Qdrant: {current_count} documents in contextual_chunks_azure"
                )

                if current_count > 0:
                    logger.info(
                        f"✓ Indexing completed successfully in {elapsed:.1f}s with {current_count} documents"
                    )
                    indexing_completed = True
                    break

                # After 30 seconds with no documents, check Cron-Manager logs once
                if poll_count == 6 and current_count == 0:
                    import subprocess

                    try:
                        logger.warning(
                            "No documents after 30s - checking Cron-Manager logs..."
                        )
                        result = subprocess.run(
                            ["docker", "logs", "cron-manager", "--tail", "100"],
                            capture_output=True,
                            text=True,
                            timeout=5,
                        )
                        if (
                            "error" in result.stdout.lower()
                            or "failed" in result.stdout.lower()
                        ):
                            logger.error("Found errors in Cron-Manager logs:")
                            logger.error(result.stdout[-2000:])  # Last 2000 chars
                    except Exception as e:
                        logger.warning(f"Could not check logs: {e}")

            except Exception as e:
                logger.warning(f"[{elapsed:.1f}s] Qdrant polling error: {e}")

            await asyncio.sleep(poll_interval)

        if not indexing_completed:
            # Capture final state and Cron-Manager logs
            try:
                final_count = qdrant_client.count(
                    collection_name="contextual_chunks_azure"
                )
                logger.error(
                    f"Final count after timeout: {final_count.count} documents"
                )
            except Exception as e:
                logger.error(f"Could not get final count: {e}")

            # Get Cron-Manager logs to see what happened
            import subprocess

            try:
                logger.error("=" * 80)
                logger.error("CRON-MANAGER LOGS (indexing phase):")
                logger.error("=" * 80)
                result = subprocess.run(
                    ["docker", "logs", "cron-manager", "--tail", "300"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.stdout:
                    logger.error(result.stdout)
                if result.stderr:
                    logger.error(f"STDERR: {result.stderr}")
            except Exception as e:
                logger.error(f"Failed to capture logs: {e}")

            pytest.fail(
                f"Indexing did not complete within {max_wait}s timeout - no documents found in collection"
            )

        # Step 4: Verify vectors are stored in Qdrant
        collections_to_check = ["contextual_chunks_azure", "contextual_chunks_aws"]
        total_points = 0

        for collection_name in collections_to_check:
            try:
                collection_info = qdrant_client.get_collection(collection_name)
                if collection_info:
                    total_points += collection_info.points_count
            except Exception:
                # Collection might not exist
                pass

        assert total_points > 0, (
            f"No vectors stored in Qdrant. Expected chunks but found {total_points} points."
        )

        logger.info(
            f"E2E Test passed: Indexing completed via Ruuter/Cron-Manager, "
            f"{total_points} points stored in Qdrant"
        )


class TestQdrantOperations:
    """Test Qdrant-specific operations."""

    def test_collection_operations(self, qdrant_client: QdrantClient):
        """Test creating and querying collections."""
        from qdrant_client.models import Distance, VectorParams

        test_collection = "test_integration_collection"

        try:
            # Create collection
            qdrant_client.create_collection(
                collection_name=test_collection,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
            )

            # Verify collection exists
            collections = qdrant_client.get_collections()
            collection_names = [c.name for c in collections.collections]
            assert test_collection in collection_names

            # Get collection info
            info = qdrant_client.get_collection(test_collection)
            assert info.config.params.vectors.size == 1536

        finally:
            # Cleanup
            try:
                qdrant_client.delete_collection(test_collection)
            except Exception:
                pass

    def test_point_operations(self, qdrant_client: QdrantClient):
        """Test inserting and querying points."""
        from qdrant_client.models import Distance, VectorParams, PointStruct

        test_collection = "test_points_collection"

        try:
            # Create collection
            qdrant_client.create_collection(
                collection_name=test_collection,
                vectors_config=VectorParams(size=4, distance=Distance.COSINE),
            )

            # Insert points
            points = [
                PointStruct(
                    id=1,
                    vector=[0.1, 0.2, 0.3, 0.4],
                    payload={"document_hash": "test123", "text": "test chunk"},
                ),
                PointStruct(
                    id=2,
                    vector=[0.2, 0.3, 0.4, 0.5],
                    payload={"document_hash": "test123", "text": "another chunk"},
                ),
            ]

            qdrant_client.upsert(collection_name=test_collection, points=points)

            # Query by filter
            results = qdrant_client.scroll(
                collection_name=test_collection,
                scroll_filter={
                    "must": [{"key": "document_hash", "match": {"value": "test123"}}]
                },
                limit=10,
            )

            assert len(results[0]) == 2

        finally:
            # Cleanup
            try:
                qdrant_client.delete_collection(test_collection)
            except Exception:
                pass
