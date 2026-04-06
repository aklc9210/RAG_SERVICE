# retrieval/bm25_retriever.py
"""
BM25 baseline retriever for Vietnamese food dishes.

Indexes dish name + ingredient names as a single text document per dish.
Uses simple Vietnamese tokenization (whitespace split after basic normalization).

Usage:
    from retrieval.bm25_retriever import BM25Retriever
    retriever = BM25Retriever()               # builds index from all dishes
    results = retriever.search("phở bò", top_k=10)
    # → [{"dish_id": str, "score": float, "dish_name": str, "category": str}, ...]
"""

import json
import re
import unicodedata
from pathlib import Path
from typing import List, Dict, Any, Optional

ROOT = Path(__file__).resolve().parent.parent
DISHES_DIR = ROOT / "processed" / "dishes"
SPLITS_DIR = ROOT / "data" / "splits"


def _normalize(text: str) -> str:
    """Lowercase + unicode normalize + remove punctuation."""
    text = unicodedata.normalize("NFC", text).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokenize(text: str) -> List[str]:
    return _normalize(text).split()


def _build_doc(dish: dict) -> str:
    """Build a single text document for BM25 indexing from a dish record."""
    parts = []

    name_vi = dish.get("name_vi", "")
    if name_vi:
        # Repeat name 3× to boost name-match relevance
        parts.extend([name_vi] * 3)

    category = dish.get("category", "")
    if category:
        parts.append(category.replace("-", " "))

    for field in ("main_ingredients", "secondary_ingredients", "seasonings"):
        for name in dish.get(field) or []:
            parts.append(name)

    return " ".join(parts)


class BM25Retriever:
    """
    BM25 retriever over all processed dishes.

    Parameters
    ----------
    dish_ids : list[str] | None
        If provided, only index these dish IDs. Otherwise indexes all dishes.
    """

    def __init__(self, dish_ids: Optional[List[str]] = None) -> None:
        from rank_bm25 import BM25Okapi

        if dish_ids is None:
            dish_files = sorted(DISHES_DIR.glob("*.json"))
        else:
            dish_files = [DISHES_DIR / f"{did}.json" for did in dish_ids]
            dish_files = [f for f in dish_files if f.exists()]

        self._ids: List[str] = []
        self._names: List[str] = []
        self._categories: List[str] = []
        tokenized_corpus: List[List[str]] = []

        for path in dish_files:
            try:
                dish = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            doc = _build_doc(dish)
            tokenized_corpus.append(_tokenize(doc))
            self._ids.append(dish["id"])
            self._names.append(dish.get("name_vi", ""))
            self._categories.append(dish.get("category", ""))

        self._bm25 = BM25Okapi(tokenized_corpus)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Search for dishes matching the query.

        Returns list of dicts sorted by BM25 score descending:
            [{"dish_id": str, "score": float, "dish_name": str, "category": str}]
        """
        tokens = _tokenize(query)
        if not tokens:
            return []

        scores = self._bm25.get_scores(tokens)

        # Build ranked list
        indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in indexed[:top_k]:
            if score <= 0:
                break
            results.append({
                "dish_id": self._ids[idx],
                "score": round(float(score), 6),
                "dish_name": self._names[idx],
                "category": self._categories[idx],
            })
        return results

    def __len__(self) -> int:
        return len(self._ids)
