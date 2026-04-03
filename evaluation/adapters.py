from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Set, Tuple

from app.pipeline import ShoppingCartPipeline
from app.services.conflict_service import ConflictDetectionService
from app.services.ontology_service import OntologyService


class DishPipelineAdapter(Protocol):
    def run_text(self, user_input: str) -> Dict[str, Any]:
        ...


class ConflictAdapter(Protocol):
    def detect_conflicts(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        ...


class ReplacementAdapter(Protocol):
    def suggest_replacements(self, target_id: str, exclude_ids: Set[str], max_suggestions: int) -> List[Dict[str, Any]]:
        ...


@dataclass
class LiveRAGAdapter(DishPipelineAdapter, ConflictAdapter, ReplacementAdapter):
    pipeline: ShoppingCartPipeline
    conflict_service: ConflictDetectionService
    ontology_service: OntologyService
    _trace_state: Dict[str, Any] = field(default_factory=dict)
    _trace_hooked: bool = False

    @classmethod
    def build_default(cls) -> "LiveRAGAdapter":
        return cls(
            pipeline=ShoppingCartPipeline(),
            conflict_service=ConflictDetectionService(),
            ontology_service=OntologyService(),
        )

    def run_text(self, user_input: str) -> Dict[str, Any]:
        self._ensure_trace_hook()
        self._trace_state["last_retrieval"] = {"query": "", "top_k_docs": []}
        return self.pipeline.process(user_input)

    def get_last_retrieval_trace(self) -> Dict[str, Any]:
        trace = self._trace_state.get("last_retrieval") or {}
        return {
            "query": trace.get("query", ""),
            "top_k_docs": trace.get("top_k_docs", []),
        }

    def _ensure_trace_hook(self) -> None:
        if self._trace_hooked:
            return

        self.pipeline.kb_service._ensure_init()
        retriever = self.pipeline.kb_service._retriever
        original = retriever.search_filtered

        def wrapped_search_filtered(*args, **kwargs):
            query_text = kwargs.get("query_text")
            if query_text is None and len(args) > 0:
                query_text = args[0]
            results = original(*args, **kwargs)
            self._trace_state["last_retrieval"] = {
                "query": query_text or "",
                "top_k_docs": results,
            }
            return results

        retriever.search_filtered = wrapped_search_filtered
        self._trace_hooked = True

    def detect_conflicts(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized_items: List[Dict[str, Any]] = []
        for item in items or []:
            ingredient_id = item.get("ingredient_id")
            name_vi = item.get("name_vi") or item.get("vietnamese_name") or item.get("name")

            # Layer B id/mixed cases may provide only ingredient_id; enrich with ontology name.
            if not name_vi and ingredient_id:
                ontology_ing = self.ontology_service.ingredients.get(str(ingredient_id)) or {}
                name_vi = ontology_ing.get("name_vi")

            normalized_items.append(
                {
                    "ingredient_id": ingredient_id,
                    "name_vi": name_vi,
                }
            )

        return self.conflict_service.check_conflicts("", normalized_items)

    def suggest_replacements(self, target_id: str, exclude_ids: Set[str], max_suggestions: int) -> List[Dict[str, Any]]:
        return self.ontology_service.get_replacement_suggestions(
            conflicting_ingredient_id=target_id,
            max_suggestions=max_suggestions,
            exclude_ids=exclude_ids,
        )


def parse_dish_name(response: Dict[str, Any]) -> str:
    dish = response.get("dish") or {}
    return (dish.get("vietnamese_name") or dish.get("name") or "").strip()


def parse_cart_ids(response: Dict[str, Any]) -> Set[str]:
    cart = response.get("cart") or {}
    items = cart.get("items") or []
    return {it.get("ingredient_id") for it in items if it.get("ingredient_id")}


def parse_conflict_pairs(conflict_rows: List[Dict[str, Any]], name_to_id: Dict[str, str]) -> Set[Tuple[str, str]]:
    pairs: Set[Tuple[str, str]] = set()
    for row in conflict_rows or []:
        left = row.get("conflicting_item_1") or []
        right = row.get("conflicting_item_2") or []
        left_ids = {name_to_id.get(str(name).strip().lower()) for name in left}
        right_ids = {name_to_id.get(str(name).strip().lower()) for name in right}
        for a in left_ids:
            for b in right_ids:
                if a and b and a != b:
                    pairs.add(tuple(sorted((a, b))))
    return pairs
