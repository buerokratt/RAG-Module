"""
Sparse vector encoder for BM25-style term frequency vectors.

Shared module used by both:
- intent_data_enrichment (indexing time) — to create sparse vectors for service examples
- tool_classifier (query time) — to create sparse vectors for user queries

Uses hash-based indexing compatible with Qdrant's sparse vector format.
"""

import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import List


# Hash space for sparse vector indices
# Larger = fewer collisions but more memory; 50K is a good balance for intent classification
SPARSE_VOCAB_SIZE = 50_000

# Simple word tokenizer matching the pattern used in contextual_retrieval/bm25_search.py
TOKENIZER_PATTERN = re.compile(r"\w+")


@dataclass
class SparseVector:
    """Sparse vector representation for Qdrant.

    Attributes:
        indices: Sorted list of non-zero dimension indices
        values: Corresponding values for each index
    """

    indices: List[int] = field(default_factory=list)
    values: List[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to Qdrant API format."""
        return {"indices": self.indices, "values": self.values}

    def is_empty(self) -> bool:
        """Check if the sparse vector has no entries."""
        return len(self.indices) == 0


def compute_sparse_vector(text: str) -> SparseVector:
    """Convert text to a sparse vector using term-frequency hashing.

    Tokenizes the input text, counts term frequencies, and maps each token
    to a hash-based index in the sparse vector space. This creates a
    BM25-compatible representation that Qdrant can use for sparse search.

    Args:
        text: Input text to vectorize

    Returns:
        SparseVector with hash-based indices and term frequency values
    """
    if not text or not text.strip():
        return SparseVector()

    # Tokenize: lowercase and extract word tokens
    tokens = TOKENIZER_PATTERN.findall(text.lower())
    if not tokens:
        return SparseVector()

    # Count term frequencies
    token_counts = Counter(tokens)

    # Hash-based indexing: map each token to an index in [0, SPARSE_VOCAB_SIZE)
    # Uses MD5 (first 4 bytes) for deterministic cross-process indices.
    # Collisions are handled by summing values at the same index.
    hash_counts: dict[int, float] = {}
    for token, count in token_counts.items():
        digest = hashlib.md5(token.encode(), usedforsecurity=False).digest()  # noqa: S324
        idx = int.from_bytes(digest[:4], "little") % SPARSE_VOCAB_SIZE
        # Handle hash collisions by accumulating
        hash_counts[idx] = hash_counts.get(idx, 0) + float(count)

    # Sort indices for consistent representation (Qdrant requirement)
    sorted_indices = sorted(hash_counts.keys())
    sorted_values = [hash_counts[i] for i in sorted_indices]

    return SparseVector(indices=sorted_indices, values=sorted_values)
