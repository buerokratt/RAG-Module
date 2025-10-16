"""
Contextual Retrieval Module

Implements Anthropic's Contextual Retrieval methodology for 49% improvement
in retrieval accuracy using contextual embeddings + BM25 + RRF fusion.
"""

# Import main components when module is loaded
from contextual_retrieval.contextual_retriever import ContextualRetriever
from contextual_retrieval.config import ContextualRetrievalConfig, ConfigLoader

__all__ = ["ContextualRetriever", "ContextualRetrievalConfig", "ConfigLoader"]
