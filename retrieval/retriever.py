"""
Pinecone retrieval layer.

Three modes:
- search_basic    : plain dense search, no filters
- search_filtered : dense search with Pinecone metadata filters
- search_grouped  : dense search, then group results by entity_id (best score wins)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ingestion.embedding import EmbeddingModel


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _match_to_dict(match: Any) -> Dict[str, Any]:
    """Flatten a Pinecone ScoredVector into a plain dict."""
    meta = match.metadata or {}
    return {
        "id": match.id,
        "score": round(float(match.score), 6),
        "entity_id": meta.get("entity_id", ""),
        "type": meta.get("type", ""),
        "doc_type": meta.get("doc_type", ""),
        "name_vi": meta.get("name_vi", ""),
        "name_en": meta.get("name_en", ""),
        "category": meta.get("category", ""),
        "text": meta.get("text", ""),
    }


# ---------------------------------------------------------------------------
# Retriever
# ---------------------------------------------------------------------------


class Retriever:
    """
    Wrapper for Pinecone query operations.

    Parameters
    ----------
    embedding_model : EmbeddingModel
        Shared embedding model (must be the same model used for ingestion).
    pinecone_index : pinecone.Index
        An already-connected Pinecone Index object.
    """

    def __init__(self, embedding_model: EmbeddingModel, pinecone_index: Any) -> None:
        self._embed = embedding_model
        self._index = pinecone_index

    # ------------------------------------------------------------------
    # Internal query helper
    # ------------------------------------------------------------------

    def _query(
        self,
        query_text: str,
        top_k: int,
        filter_: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        vector = self._embed.embed_query(query_text)
        kwargs: Dict[str, Any] = {
            "vector": vector,
            "top_k": top_k,
            "include_metadata": True,
        }
        if filter_:
            kwargs["filter"] = filter_
        response = self._index.query(**kwargs)
        return [_match_to_dict(m) for m in response.matches]

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def search_basic(self, query_text: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """Plain dense vector search — no filters."""
        return self._query(query_text, top_k=top_k)

    def search_filtered(
        self,
        query_text: str,
        top_k: int = 10,
        type_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Dense search with optional type and/or category metadata filters."""
        conditions: List[Dict] = []
        if type_filter:
            conditions.append({"type": {"$eq": type_filter}})
        if category_filter:
            conditions.append({"category": {"$eq": category_filter}})

        filter_: Optional[Dict] = None
        if len(conditions) == 1:
            filter_ = conditions[0]
        elif len(conditions) > 1:
            filter_ = {"$and": conditions}

        return self._query(query_text, top_k=top_k, filter_=filter_)

    def search_grouped(
        self,
        query_text: str,
        top_k: int = 10,
        type_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Dense search (with optional type filter), then group documents by
        entity_id.  Each group keeps the best-scoring doc and collects all
        matched documents under 'matched_docs'.

        The `top_k` parameter here controls how many *entities* are returned.
        We over-fetch (top_k * 4) from Pinecone to ensure enough coverage.
        """
        raw = self.search_filtered(
            query_text,
            top_k=top_k * 4,
            type_filter=type_filter,
        )

        # Group by entity_id
        groups: Dict[str, Dict[str, Any]] = {}
        for match in raw:
            eid = match["entity_id"] or match["id"]
            if eid not in groups:
                groups[eid] = {
                    "entity_id": eid,
                    "type": match["type"],
                    "name_vi": match["name_vi"],
                    "name_en": match["name_en"],
                    "category": match["category"],
                    "best_score": match["score"],
                    "matched_docs": [],
                }
            # Update best score
            if match["score"] > groups[eid]["best_score"]:
                groups[eid]["best_score"] = match["score"]
                groups[eid]["name_vi"] = match["name_vi"] or groups[eid]["name_vi"]
            groups[eid]["matched_docs"].append(
                {
                    "id": match["id"],
                    "doc_type": match["doc_type"],
                    "score": match["score"],
                    "text": match["text"],
                }
            )

        # Sort groups by best_score descending, return top_k entities
        sorted_groups = sorted(
            groups.values(), key=lambda g: g["best_score"], reverse=True
        )
        return sorted_groups[:top_k]
