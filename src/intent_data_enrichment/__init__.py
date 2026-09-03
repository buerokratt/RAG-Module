"""
Data Enrichment Module

This module handles enrichment of service data before indexing into Qdrant.
Services are enriched with LLM-generated context and stored in intent_collections.
"""

__version__ = "1.0.0"

from intent_data_enrichment.models import ServiceData, EnrichedService, EnrichmentResult
from intent_data_enrichment.api_client import LLMAPIClient
from intent_data_enrichment.qdrant_manager import QdrantManager
from intent_data_enrichment.constants import EnrichmentConstants

__all__ = [
    "ServiceData",
    "EnrichedService",
    "EnrichmentResult",
    "LLMAPIClient",
    "QdrantManager",
    "EnrichmentConstants",
]
