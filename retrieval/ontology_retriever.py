# retrieval/ontology_retriever.py
"""
RAG + Ontology retriever.

Wraps the existing dense Retriever (Pinecone) and augments its output with:

  Task 1 — Dish retrieval with ontology reranking:
    score_final(d) = λ * rag_score(d) + (1-λ) * relatedness(query_dish, d)
    where relatedness is computed from shared ingredients + category.

  Task 2 — Flavor-enhancing ingredients via NPMI + category prior:
    Given a dish, return non-core ingredients ranked by mean NPMI with core ingredients.
    Ingredients in the "seasonings" category get a small prior boost (more likely flavor-enhancing).

  Task 3 — Related dishes via Dish Relatedness:
    Relatedness(A, B) = α * IDF-weighted-Jaccard(A, B) + β * same_category(A, B)
    IDF weight: w(i) = log(N / df(i)) — rare shared ingredients count more than common ones (e.g. muối)

All dish data is loaded from processed/dishes/*.json (no Pinecone needed for ontology parts).

Usage:
    from retrieval.ontology_retriever import OntologyRetriever
    ret = OntologyRetriever()

    # Task 1
    results = ret.search_dishes("phở bò", top_k=10)

    # Task 2
    flavor = ret.get_flavor_enhancing("dish0001", top_k=10)

    # Task 3
    related = ret.get_related_dishes("dish0001", top_k=5)
"""

import json
import math
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

ROOT = Path(__file__).resolve().parent.parent
DISHES_DIR = ROOT / "processed" / "dishes"
NPMI_PATH = ROOT / "app" / "data" / "cooccurrence" / "npmi.json"
PMI_PATH = ROOT / "app" / "data" / "cooccurrence" / "pmi.json"   # fallback if npmi.json absent
FREQ_PATH = ROOT / "app" / "data" / "cooccurrence" / "frequency.json"
META_PATH = ROOT / "app" / "data" / "cooccurrence" / "metadata.json"
IKB_PATH = ROOT / "app" / "data" / "knowledge_base" / "ingredient_knowledge_base.json"

# Ingredient categories considered flavor-enhancing by nature
_FLAVOR_CATEGORIES = {"seasonings"}


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union > 0 else 0.0


def _idf_jaccard(a: Set[str], b: Set[str], idf: Dict[str, float]) -> float:
    """
    IDF-weighted Jaccard similarity.
    Rare shared ingredients (high IDF) contribute more than common ones (e.g. muối, nước mắm).
    """
    if not a or not b:
        return 0.0
    inter = a & b
    union = a | b
    w_inter = sum(idf.get(i, 1.0) for i in inter)
    w_union = sum(idf.get(i, 1.0) for i in union)
    return w_inter / w_union if w_union > 0 else 0.0


class OntologyRetriever:
    """
    Ontology-augmented retriever.

    Parameters
    ----------
    dish_ids : list[str] | None
        Subset of dish IDs to load. If None, loads all dishes.
    alpha : float
        Jaccard weight in Dish Relatedness (default 0.7).
    beta : float
        Category weight in Dish Relatedness (default 0.3).
    rag_lambda : float
        Weight for RAG score in Task 1 reranking (default 0.6).
        ontology weight = 1 - rag_lambda.
    """

    def __init__(
        self,
        dish_ids: Optional[List[str]] = None,
        alpha: float = 0.7,
        beta: float = 0.3,
        rag_lambda: float = 0.85,
    ) -> None:
        self.alpha = alpha
        self.beta = beta
        self.rag_lambda = rag_lambda

        self._dishes: Dict[str, Dict[str, Any]] = {}
        self._name_to_ids: Dict[str, List[str]] = {}  # normalized name → [dish_id]

        self._load_dishes(dish_ids)
        self._pmi: Dict[str, Dict[str, float]] = self._load_npmi_or_pmi()
        self._idf: Dict[str, float] = self._load_idf()
        self._id_to_name_vi: Dict[str, str] = self._load_ingredient_names()
        self._flavor_category_ids: Set[str] = self._load_flavor_category_ids()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search_dishes(
        self,
        query: str,
        top_k: int = 10,
        rag_results: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Task 1: Retrieve relevant dishes for a query.

        If rag_results is provided (list of {"dish_id", "score"} from dense retrieval),
        reranks them using Dish Relatedness with the best-matching dish in rag_results.

        If rag_results is None, falls back to name-matching only (for offline evaluation).
        """
        query_norm = _normalize(query)

        if rag_results:
            return self._rerank(query_norm, rag_results, top_k)

        # Offline fallback: simple name-based scoring (for evaluation without Pinecone)
        return self._offline_search(query_norm, top_k)

    def get_flavor_enhancing(
        self,
        dish_id: str,
        top_k: int = 10,
        min_pmi: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Task 2: Return flavor-enhancing ingredients for a dish.

        Returns non-core ingredients ranked by mean PMI with core ingredients.
        [{"ingredient_id": str, "name_vi": str, "mean_pmi": float}]
        """
        dish = self._dishes.get(dish_id)
        if not dish:
            return []

        core_ids = set(dish["core_ids"])
        all_ids = set(dish["ingredient_ids"])
        non_core_ids = all_ids - core_ids

        scored = []
        for cand_id in non_core_ids:
            pmi_vals = []
            for core_id in core_ids:
                v = self._get_pmi(core_id, cand_id)
                if v is not None:
                    pmi_vals.append(v)
            if not pmi_vals:
                continue
            mean_pmi = sum(pmi_vals) / len(pmi_vals)
            if mean_pmi < min_pmi:
                continue
            # Category prior: seasonings are more likely to be flavor-enhancing
            if cand_id in self._flavor_category_ids:
                mean_pmi *= 1.15
            scored.append({
                "ingredient_id": cand_id,
                "name_vi": self._id_to_name_vi.get(cand_id, ""),
                "mean_pmi": round(mean_pmi, 4),
            })

        scored.sort(key=lambda x: x["mean_pmi"], reverse=True)
        return scored[:top_k]

    def get_related_dishes(
        self,
        dish_id: str,
        top_k: int = 5,
        candidate_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Task 3: Return related dishes for a given dish using Dish Relatedness.

        [{"dish_id": str, "dish_name": str, "relatedness": float,
          "jaccard": float, "same_category": bool}]
        """
        dish_a = self._dishes.get(dish_id)
        if not dish_a:
            return []

        ing_a = dish_a["ingredient_ids_set"]
        cat_a = dish_a["category"]

        pool = candidate_ids if candidate_ids is not None else list(self._dishes.keys())

        scored = []
        for other_id in pool:
            if other_id == dish_id:
                continue
            dish_b = self._dishes.get(other_id)
            if not dish_b:
                continue

            j = _idf_jaccard(ing_a, dish_b["ingredient_ids_set"], self._idf)
            same_cat = 1 if cat_a == dish_b["category"] else 0
            relatedness = self.alpha * j + self.beta * same_cat

            if relatedness > 0:
                scored.append({
                    "dish_id": other_id,
                    "dish_name": dish_b["name_vi"],
                    "relatedness": round(relatedness, 4),
                    "jaccard": round(j, 4),
                    "same_category": bool(same_cat),
                })

        scored.sort(key=lambda x: x["relatedness"], reverse=True)
        return scored[:top_k]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_dishes(self, dish_ids: Optional[List[str]]) -> None:
        if dish_ids is not None:
            paths = [DISHES_DIR / f"{did}.json" for did in dish_ids]
        else:
            paths = sorted(DISHES_DIR.glob("*.json"))

        for path in paths:
            if not path.exists():
                continue
            try:
                d = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue

            did = d["id"]
            all_ids = d.get("ingredient_ids", [])
            main = d.get("main_ingredients", [])
            all_names_vi = d.get("ingredient_names_vi", [])

            name_to_id = {}
            for idx, name in enumerate(all_names_vi):
                if idx < len(all_ids):
                    name_to_id[name.lower().strip()] = all_ids[idx]

            core_ids = [name_to_id[n.lower().strip()] for n in main if n.lower().strip() in name_to_id]
            if not core_ids and all_ids:
                core_ids = all_ids[: max(1, len(all_ids) // 2)]

            self._dishes[did] = {
                "name_vi": d.get("name_vi", ""),
                "category": d.get("category", "unknown"),
                "ingredient_ids": all_ids,
                "ingredient_ids_set": set(all_ids),
                "core_ids": core_ids,
                "name_normalized": _normalize(d.get("name_vi", "")),
            }

            name_norm = _normalize(d.get("name_vi", ""))
            if name_norm:
                self._name_to_ids.setdefault(name_norm, []).append(did)

    def _load_npmi_or_pmi(self) -> Dict[str, Dict[str, float]]:
        """Load NPMI if available (preferred), fall back to PMI."""
        if NPMI_PATH.exists():
            return json.loads(NPMI_PATH.read_text(encoding="utf-8"))
        if PMI_PATH.exists():
            return json.loads(PMI_PATH.read_text(encoding="utf-8"))
        return {}

    def _load_idf(self) -> Dict[str, float]:
        """
        Compute IDF weights from ingredient frequency data.
        idf(i) = log(N / df(i))  where df = number of dishes containing ingredient i.
        """
        if not FREQ_PATH.exists() or not META_PATH.exists():
            return {}
        freq = json.loads(FREQ_PATH.read_text(encoding="utf-8"))
        meta = json.loads(META_PATH.read_text(encoding="utf-8"))
        N = meta.get("total_dishes", 1)
        return {iid: math.log(N / max(1, count)) for iid, count in freq.items()}

    def _load_flavor_category_ids(self) -> Set[str]:
        """Return set of ingredient_ids whose category is in _FLAVOR_CATEGORIES."""
        if not IKB_PATH.exists():
            return set()
        ikb = json.loads(IKB_PATH.read_text(encoding="utf-8"))
        return {e["id"] for e in ikb if e.get("category") in _FLAVOR_CATEGORIES and e.get("id")}

    def _load_ingredient_names(self) -> Dict[str, str]:
        if not IKB_PATH.exists():
            return {}
        ikb = json.loads(IKB_PATH.read_text(encoding="utf-8"))
        return {e["id"]: e.get("name_vi", "") for e in ikb if e.get("id")}

    def _get_pmi(self, x: str, y: str) -> Optional[float]:
        if x in self._pmi and y in self._pmi[x]:
            return self._pmi[x][y]
        if y in self._pmi and x in self._pmi[y]:
            return self._pmi[y][x]
        return None

    def _is_exact_name_query(self, query_norm: str, rag_results: List[Dict[str, Any]]) -> bool:
        """
        Detect if query is an exact-name match.
        True if: top RAG hit's name contains the query (or vice versa),
        AND score gap between #1 and #2 is large (>15%).
        """
        if not rag_results:
            return False
        top_did = rag_results[0]["dish_id"]
        top_name = self._dishes.get(top_did, {}).get("name_normalized", "")
        # Check name overlap
        query_tokens = set(query_norm.split())
        name_tokens = set(top_name.split())
        if not query_tokens or not name_tokens:
            return False
        overlap = len(query_tokens & name_tokens) / len(query_tokens)
        # Check score gap
        if len(rag_results) >= 2 and rag_results[0]["score"] > 0:
            gap = (rag_results[0]["score"] - rag_results[1]["score"]) / rag_results[0]["score"]
        else:
            gap = 1.0
        return overlap >= 0.5 and gap >= 0.15

    def _rerank(
        self,
        query_norm: str,
        rag_results: List[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """
        Adaptive rerank: skip reranking for exact-name queries, apply ontology
        reranking only for category/exploratory queries.

        Ontology strategy (when applied):
          1. Category voting: dominant category among top RAG hits gets bonus.
          2. Ingredient overlap: Jaccard with top-3 RAG hits' ingredient pool.

        final_score = rag_lambda * rag_score_norm + (1 - rag_lambda) * ontology_score
        """
        if not rag_results:
            return []

        # Adaptive: skip reranking for exact-name queries
        if self._is_exact_name_query(query_norm, rag_results):
            return [
                {
                    "dish_id": r["dish_id"],
                    "dish_name": r.get("dish_name", self._dishes.get(r["dish_id"], {}).get("name_vi", "")),
                    "score": r["score"],
                    "rag_score": r["score"],
                    "ontology_score": 0.0,
                    "category": self._dishes.get(r["dish_id"], {}).get("category", ""),
                }
                for r in rag_results[:top_k]
            ]

        # --- Category/exploratory query: apply ontology reranking ---
        scores = [r["score"] for r in rag_results]
        max_score = max(scores) or 1.0
        rag_lambda = self.rag_lambda

        # --- Category voting: pick the most common category in top-5 RAG hits ---
        top5_ids = [r["dish_id"] for r in rag_results[:5]]
        cat_votes: Dict[str, int] = {}
        for did in top5_ids:
            cat = self._dishes.get(did, {}).get("category", "")
            if cat:
                cat_votes[cat] = cat_votes.get(cat, 0) + 1
        dominant_cat = max(cat_votes, key=cat_votes.get) if cat_votes else ""

        # --- Majority-anchor ingredient pool: union of top-3 ingredient sets ---
        top3_ids = [r["dish_id"] for r in rag_results[:3]]
        anchor_ingredients: Set[str] = set()
        for did in top3_ids:
            anchor_ingredients |= self._dishes.get(did, {}).get("ingredient_ids_set", set())

        reranked = []
        for r in rag_results:
            rag_score_norm = r["score"] / max_score
            did = r["dish_id"]
            dish = self._dishes.get(did, {})

            # Category match score
            cat_score = 1.0 if (dominant_cat and dish.get("category") == dominant_cat) else 0.0

            # Jaccard with majority-anchor ingredient pool
            cand_ing = dish.get("ingredient_ids_set", set())
            if anchor_ingredients and cand_ing:
                jaccard_score = len(cand_ing & anchor_ingredients) / len(cand_ing | anchor_ingredients)
            else:
                jaccard_score = 0.0

            ont_score = 0.5 * cat_score + 0.5 * jaccard_score
            final = rag_lambda * rag_score_norm + (1 - rag_lambda) * ont_score

            reranked.append({
                "dish_id": did,
                "dish_name": r.get("dish_name", dish.get("name_vi", "")),
                "score": round(final, 6),
                "rag_score": round(rag_score_norm, 6),
                "ontology_score": round(ont_score, 6),
                "category": dish.get("category", ""),
            })

        reranked.sort(key=lambda x: x["score"], reverse=True)
        return reranked[:top_k]

    def _offline_search(self, query_norm: str, top_k: int) -> List[Dict[str, Any]]:
        """
        Offline name-based search (no Pinecone) for evaluation.
        Scores dishes by token overlap with query.
        """
        query_tokens = set(query_norm.split())
        if not query_tokens:
            return []

        scored = []
        for did, dish in self._dishes.items():
            name_tokens = set(dish["name_normalized"].split())
            cat_tokens = set(_normalize(dish["category"]).split())
            overlap = len(query_tokens & (name_tokens | cat_tokens))
            if overlap > 0:
                scored.append({
                    "dish_id": did,
                    "dish_name": dish["name_vi"],
                    "score": round(overlap / len(query_tokens), 4),
                    "category": dish["category"],
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]
