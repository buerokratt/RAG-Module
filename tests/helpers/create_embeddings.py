"""Pre-compute embeddings for test data to avoid API calls during tests."""

import json
import requests
from pathlib import Path
from loguru import logger
from test_data_loader import get_test_documents


def precompute_embeddings(
    orchestration_url: str = "http://localhost:8100",
    output_file: str = "../data/test_embeddings.json"
):
    """
    Pre-compute embeddings for all test documents and save to file.
    
    Run this script once locally to generate embeddings, then commit the file.
    """
    logger.info("Loading test documents...")
    test_documents = get_test_documents()
    
    logger.info(f"Pre-computing embeddings for {len(test_documents)} documents...")
    
    # Extract texts
    texts = [doc["contextual_content"] for doc in test_documents]
    
    # Create embeddings
    response = requests.post(
        f"{orchestration_url}/embeddings",
        json={
            "texts": texts,
            "environment": "development",
            "connection_id": "evalconnection-1",
            "batch_size": 25,
        },
        timeout=600,
    )
    
    if response.status_code != 200:
        logger.error(f"Embedding creation failed: {response.text}")
        raise RuntimeError(f"Failed to create embeddings: {response.text}")
    
    embeddings_data = response.json()
    embeddings = embeddings_data["embeddings"]
    model_used = embeddings_data.get("model_used", "text-embedding-3-large")
    
    logger.info(f"Successfully created {len(embeddings)} embeddings")
    
    # Combine documents with their embeddings
    output_data = {
        "model_used": model_used,
        "vector_size": len(embeddings[0]),
        "documents": []
    }
    
    for doc, embedding in zip(test_documents, embeddings):
        output_data["documents"].append({
            "document": doc,
            "embedding": embedding
        })
    
    # Save to file
    output_path = Path(__file__).parent.parent / "data" / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)
    
    logger.info(f"Saved pre-computed embeddings to {output_path}")
    logger.info(f"File size: {output_path.stat().st_size / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    precompute_embeddings()