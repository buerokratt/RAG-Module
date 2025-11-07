"""Helper module to load test data into Qdrant before running tests."""
import os
import json
import requests
import uuid
from typing import List, Dict, Any, Tuple
from pathlib import Path
from loguru import logger
from datetime import datetime


def load_test_data_into_qdrant(
    orchestration_url: str,
    qdrant_url: str,
) -> None:
    """Load test documents into Qdrant contextual collections for retrieval testing."""
    logger.info("Loading test data into Qdrant contextual collections...")

    # Try to load pre-computed embeddings first
    embeddings_file = Path(__file__).parent.parent / "data" / "test_embeddings.json"
    
    if embeddings_file.exists():
        logger.info(f"Loading pre-computed embeddings from {embeddings_file}")
        test_documents, embeddings, model_used = load_precomputed_embeddings(embeddings_file)
    else:
        logger.warning("Pre-computed embeddings not found, computing on-the-fly (slower)")
        test_documents = get_test_documents()
        embeddings, model_used = create_embeddings_on_the_fly(
            orchestration_url, test_documents
        )

    # Now index into Qdrant
    index_embeddings_to_qdrant(
        qdrant_url=qdrant_url,
        test_documents=test_documents,
        embeddings=embeddings,
        model_used=model_used
    )


def load_precomputed_embeddings(
    embeddings_file: Path
) -> Tuple[List[Dict[str, Any]], List[List[float]], str]:
    """Load pre-computed embeddings from file."""
    with open(embeddings_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    test_documents = [item["document"] for item in data["documents"]]
    embeddings = [item["embedding"] for item in data["documents"]]
    model_used = data["model_used"]
    
    logger.info(f"Loaded {len(embeddings)} pre-computed embeddings")
    logger.info(f"   Vector size: {data['vector_size']}")
    logger.info(f"   Model: {model_used}")
    
    return test_documents, embeddings, model_used


def create_embeddings_on_the_fly(
    orchestration_url: str,
    test_documents: List[Dict[str, Any]]
) -> Tuple[List[List[float]], str]:
    """Create embeddings on-the-fly (fallback when pre-computed file doesn't exist)."""
    texts = [doc["contextual_content"] for doc in test_documents]
    
    logger.info(f"Creating embeddings for {len(texts)} documents...")
    
    embedding_response = requests.post(
        f"{orchestration_url}/embeddings",
        json={
            "texts": texts,
            "environment": "development",
            "connection_id": "evalconnection-1",
            "batch_size": 25,
        },
        timeout=600,
    )
    
    if embedding_response.status_code != 200:
        logger.error(f"Embedding API error: {embedding_response.text}")
        raise RuntimeError(f"Embedding creation failed: {embedding_response.text}")
    
    embeddings_data = embedding_response.json()
    embeddings = embeddings_data.get("embeddings", [])
    model_used = embeddings_data.get("model_used", "text-embedding-3-large")
    
    if not embeddings:
        raise RuntimeError("No embeddings returned from API")
    
    logger.info(f"Created {len(embeddings)} embeddings")
    
    return embeddings, model_used


def index_embeddings_to_qdrant(
    qdrant_url: str,
    test_documents: List[Dict[str, Any]],
    embeddings: List[List[float]],
    model_used: str
) -> None:
    """Index embeddings into Qdrant."""
    vector_size = len(embeddings[0])
    collection_name = _determine_collection_from_model(model_used)
    
    logger.info(f"Indexing into Qdrant collection: {collection_name}")
    
    import httpx
    async_client = httpx.Client(timeout=30.0)
    
    try:
        # Check if collection exists
        response = async_client.get(f"{qdrant_url}/collections/{collection_name}")
        
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
            
            response = async_client.put(
                f"{qdrant_url}/collections/{collection_name}", 
                json=create_payload
            )
            
            if response.status_code not in [200, 201]:
                raise RuntimeError(f"Failed to create collection: {response.text}")
            
            logger.info(f"Created collection '{collection_name}'")
        else:
            logger.info(f"Collection '{collection_name}' already exists")
        
        # Prepare points
        points = []
        for doc, embedding in zip(test_documents, embeddings):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, doc["chunk_id"]))
            
            payload = {
                "chunk_id": doc["chunk_id"],
                "document_hash": doc["document_hash"],
                "chunk_index": doc["chunk_index"],
                "total_chunks": 1,
                "original_content": doc["original_content"],
                "contextual_content": doc["contextual_content"],
                "context_only": doc["context"],
                "embedding_model": model_used,
                "vector_dimensions": vector_size,
                "document_url": doc["metadata"].get("source", "test_document"),
                "dataset_collection": "test_collection",
                "processing_timestamp": datetime.now().isoformat(),
                "tokens_count": len(doc["contextual_content"]) // 4,
                **doc["metadata"],
            }
            
            points.append({"id": point_id, "vector": embedding, "payload": payload})
        
        # Upsert points in batches
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
        
        logger.info(f"Successfully indexed {len(points)} documents into Qdrant")
        
    except Exception as e:
        logger.error(f"Failed to index to Qdrant: {e}")
        raise


# Keep your existing get_test_documents() and helper functions...

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
    """Get test documents in contextual retrieval format."""
    
    # Get path to tests/data/agencies_data
    current_file = Path(__file__)
    tests_dir = current_file.parent.parent
    data_dir = tests_dir / "data" / "agencies_data"
    
    if not data_dir.exists():
        logger.error(f"Data directory not found: {data_dir}")
        raise FileNotFoundError(f"Data directory not found: {data_dir}")
    
    contexts: List[dict[str, Any]] = []
    doc_counter = 0
    
    for agency in os.listdir(data_dir):
        agency_dir = data_dir / agency
        if not agency_dir.is_dir():
            continue
        per_agency_topic_counter = 0
        for topic in os.listdir(agency_dir):
            topic_dir = agency_dir / topic
            if not topic_dir.is_dir():
                continue
            per_agency_topic_counter += 1
            # Read cleaned text
            cleaned_file = topic_dir / "cleaned.txt"
            if not cleaned_file.exists():
                logger.warning(f"Skipping {cleaned_file} - file not found")
                continue
                
            with open(cleaned_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
            
            # Read metadata
            meta_file = topic_dir / "cleaned.meta.json"
            if meta_file.exists():
                with open(meta_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
            else:
                metadata = {}
            
            # Split into chunks (split by \n\n\n or limit by character count)
            raw_chunks = content.split("\n\n\n")
            
            for chunk_idx, raw_chunk in enumerate(raw_chunks):
                # Clean the chunk
                chunk_text = raw_chunk.replace("\n\n", "\n").strip()
                
                # Skip empty chunks
                if not chunk_text or len(chunk_text) < 10:
                    continue
                
                # Limit chunk size (rough estimate: 1 token ≈ 4 chars)
                # Max 8000 tokens = ~32000 chars, but be conservative
                MAX_CHUNK_SIZE = 10000
                if len(chunk_text) > MAX_CHUNK_SIZE:
                    logger.warning(f"Chunk too long ({len(chunk_text)} chars), truncating")
                    chunk_text = chunk_text[:MAX_CHUNK_SIZE]
                
                # Clean up navigation artifacts and dates
                # Remove common noise patterns
                chunk_text = _clean_chunk_text(chunk_text)
                
                if len(chunk_text) < 10:  # Skip if too short after cleaning
                    continue
                
                context_dict = {
                    "chunk_id": f"test_doc_{doc_counter:03d}_chunk_{chunk_idx:03d}",
                    "document_hash": f"test_doc_{doc_counter:03d}",
                    "chunk_index": chunk_idx,
                    "original_content": chunk_text,
                    "context": f"This is a document about {agency} - {topic}",
                    "contextual_content": f"This is a document about {agency} - {topic}\n\n{chunk_text}",
                    "metadata": {
                        "category": metadata.get(agency, agency),
                        "language": "et",
                        "source": metadata.get("source_url", f"{agency}/{topic}"),
                        "agency": agency,
                        "topic": topic,
                    },
                }
                contexts.append(context_dict)
            
            doc_counter += 1
    
    logger.info(f"Loaded {len(contexts)} test document chunks from {doc_counter} documents")
    return contexts


def _clean_chunk_text(text: str) -> str:
    """Clean chunk text to remove navigation elements and artifacts."""
    import re
    
    # Remove date patterns like "10.07.2025 11:22"
    text = re.sub(r'\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}', '', text)
    
    # Remove pagination (1\n2\n3\n...)
    text = re.sub(r'(?:\d+\n){3,}', '', text)
    

    
    # Remove multiple consecutive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    return text
    