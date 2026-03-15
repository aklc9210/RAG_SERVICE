"""
Pinecone client wrapper.

Reads PINECONE_API_KEY and PINECONE_INDEX_NAME from the environment.
Uses Pinecone SDK v3+ (pinecone-client >= 3.0).
"""

import os
from typing import Any, Dict, List


class PineconeClient:
    def __init__(self):
        api_key = os.environ.get("PINECONE_API_KEY")
        if not api_key:
            raise ValueError("PINECONE_API_KEY environment variable is not set")

        self.index_name = os.environ.get("PINECONE_INDEX_NAME")
        if not self.index_name:
            raise ValueError("PINECONE_INDEX_NAME environment variable is not set")

        from pinecone import Pinecone

        self._pc = Pinecone(api_key=api_key)
        self._index = self._pc.Index(self.index_name)

    def upsert_batch(self, vectors: List[Dict[str, Any]]) -> Dict:
        """
        Upsert a batch of vectors.

        Each element in `vectors` must be a dict with:
            id       (str)           — deterministic vector identifier
            values   (List[float])  — embedding values
            metadata (dict)         — filterable metadata
        """
        return self._index.upsert(vectors=vectors)

    def describe_index_stats(self) -> Dict:
        return self._index.describe_index_stats()
