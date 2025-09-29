from typing import List, Dict, Optional, Any, Tuple, Union
import numpy as np
import logging
from qdrant_client import QdrantClient
from qdrant_client.models import SearchParams
from rank_bm25 import BM25Okapi
from rerankers import Reranker

from vector_indexer.chunk_config import ChunkConfig
from vector_indexer.chunker import ChunkRetriever

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def rrf_fuse(runs: List[List[Dict[str, Any]]], k: float = 60.0) -> List[Dict[str, Any]]:
    """Reciprocal Rank Fusion for combining multiple ranking results."""
    agg: Dict[str, Dict[str, Any]] = {}
    for run in runs:
        for rank, item in enumerate(run, start=1):
            pid = item["id"]
            if pid not in agg:
                agg[pid] = {
                    "id": pid,
                    "text": item["text"],
                    "rrf": 0.0,
                    "meta": item.get("meta", {}),
                }
            agg[pid]["rrf"] += 1.0 / (k + rank)
    return sorted(agg.values(), key=lambda x: x["rrf"], reverse=True)


def build_bm25_index(
    qdrant: QdrantClient, collection: str
) -> Tuple[List[str], List[str], Optional[Any]]:
    """Build a BM25 index from Qdrant collection."""
    try:
        points, _ = qdrant.scroll(
            collection_name=collection,
            limit=100000,
            with_payload=True,
            with_vectors=False,
        )
        ids: List[str] = []
        texts: List[str] = []
        for p in points:
            payload = p.payload or {}
            t = payload.get("text", "")
            if t:
                ids.append(str(p.id))
                texts.append(t)

        if not texts:
            logger.warning(f"No texts found in collection {collection}")
            return ids, texts, None

        tokenized = [t.split() for t in texts]
        return ids, texts, BM25Okapi(tokenized)
    except Exception as e:
        logger.error(f"Failed to build BM25 index: {e}")
        return [], [], None


def dense_search(
    qdrant: QdrantClient, collection: str, query_vec: List[float], topk: int = 40
) -> List[Dict[str, Any]]:
    """Search using dense vectors in Qdrant."""
    try:
        hits = qdrant.search(
            collection_name=collection,
            query_vector=query_vec,
            with_payload=True,
            limit=topk,
            search_params=SearchParams(hnsw_ef=256),
        )
        out: List[Dict[str, Any]] = []
        for h in hits:
            pl = h.payload or {}
            meta = {}

            # Move source to meta if it exists in payload
            if "source" in pl:
                meta["source"] = pl["source"]
            if "source_file" in pl:
                meta["source_file"] = pl["source_file"]

            out.append({"id": str(h.id), "text": pl.get("text", ""), "meta": meta})
        return out
    except Exception as e:
        logger.error(f"Dense search failed: {e}")
        return []


def bm25_search(
    query: str, ids: List[str], texts: List[str], bm25: Optional[Any], topk: int = 40
) -> List[Dict[str, Any]]:
    """Search using BM25 algorithm."""
    if bm25 is None or not ids or not texts:
        logger.warning("BM25 index not available or empty")
        return []

    try:
        scores = bm25.get_scores(query.split())
        idx = np.argsort(scores)[::-1][:topk]
        return [{"id": ids[i], "text": texts[i], "meta": {}} for i in idx]
    except Exception as e:
        logger.error(f"BM25 search failed: {e}")
        return []


class HybridRetriever:
    """Hybrid retrieval combining dense search, BM25, and reranking."""

    def __init__(self, cfg: ChunkConfig):
        """Initialize hybrid retriever with configuration."""
        self.cfg = cfg
        self.cr = ChunkRetriever(cfg)
        self.qdrant = self.cr.qdrant_manager.client
        self.ids, self.texts, self.bm25 = build_bm25_index(
            self.qdrant, self.cfg.qdrant_collection
        )

        # Initialize reranker
        try:
            self.reranker = Reranker(
                "BAAI/bge-reranker-v2-m3", model_type="cross-encoder"
            )
        except Exception as e:
            logger.warning(
                f"Failed to initialize reranker: {e}. Using identity reranker."
            )
            self.reranker = None

    def _search_query(
        self, query: str, topk_dense: int, topk_bm25: int
    ) -> List[List[Dict[str, Any]]]:
        """Search a single query using both dense and BM25 methods."""
        qvec = self.cr.embedding_generator.generate_embeddings([query])[0]
        dense = dense_search(
            self.qdrant, self.cfg.qdrant_collection, qvec, topk=topk_dense
        )
        bm = bm25_search(query, self.ids, self.texts, self.bm25, topk=topk_bm25)
        return [dense, bm]

    def _rerank_results(
        self, fused: List[Dict[str, Any]], original_question: str, final_topn: int
    ) -> List[Dict[str, Union[str, float, Dict[str, Any]]]]:
        """Rerank fused results using the reranker."""
        if self.reranker is None:
            return self._format_results(fused, final_topn)

        docs = [c["text"] for c in fused]
        doc_ids = list(range(len(fused)))
        results = self.reranker.rank(
            query=original_question, docs=docs, doc_ids=doc_ids
        )
        top = results.top_k(final_topn)

        final: List[Dict[str, Union[str, float, Dict[str, Any]]]] = []
        for r in top:
            try:
                doc_id = getattr(getattr(r, "document", None), "doc_id", None)
                if (
                    doc_id is not None
                    and isinstance(doc_id, int)
                    and 0 <= doc_id < len(fused)
                ):
                    score_val = getattr(r, "score", None)
                    has_scores = getattr(results, "has_scores", False)
                    score = (
                        float(score_val)
                        if has_scores and score_val is not None
                        else float(fused[doc_id]["rrf"])
                    )
                    final.append(
                        {
                            "id": fused[doc_id]["id"],
                            "text": fused[doc_id]["text"],
                            "score": score,
                            "meta": fused[doc_id]["meta"],
                        }
                    )
            except (AttributeError, TypeError, ValueError) as e:
                logger.warning(f"Failed to process reranker result: {e}")
                continue
        return final

    def _format_results(
        self, fused: List[Dict[str, Any]], final_topn: int
    ) -> List[Dict[str, Union[str, float, Dict[str, Any]]]]:
        """Format fused results without reranking."""
        return [
            {
                "id": item["id"],
                "text": item["text"],
                "score": float(item["rrf"]),
                "meta": item["meta"],
            }
            for item in fused[:final_topn]
        ]

    def retrieve(
        self,
        original_question: str,
        refined_questions: List[str],
        topk_dense: int = 40,
        topk_bm25: int = 40,
        fused_cap: int = 120,
        final_topn: int = 12,
    ) -> List[Dict[str, Union[str, float, Dict[str, Any]]]]:
        """
        Retrieve relevant documents using hybrid approach.

        Args:
            original_question: The original user question
            refined_questions: List of refined/expanded questions
            topk_dense: Number of results from dense search
            topk_bm25: Number of results from BM25 search
            fused_cap: Maximum results after fusion
            final_topn: Final number of results to return

        Returns:
            List of relevant document chunks with scores and metadata
        """
        all_runs: List[List[Dict[str, Any]]] = []
        queries = [original_question] + list(refined_questions)

        for q in queries:
            try:
                runs = self._search_query(q, topk_dense, topk_bm25)
                all_runs.extend(runs)
            except Exception as e:
                logger.error(f"Failed to process query '{q}': {e}")
                continue

        if not all_runs:
            logger.warning("No search results obtained")
            return []

        fused = rrf_fuse(all_runs)[:fused_cap]

        if not fused:
            logger.warning("No fused results obtained")
            return []

        if self.reranker is not None:
            try:
                return self._rerank_results(fused, original_question, final_topn)
            except Exception as e:
                logger.error(f"Reranking failed: {e}. Using fusion scores only.")
                return self._format_results(fused, final_topn)
        else:
            return self._format_results(fused, final_topn)
