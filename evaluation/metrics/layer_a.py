from __future__ import annotations

from typing import Any, Dict, Iterable, List, Set

from ..contracts import DishQueryCase
from .common import normalize_text, prf1_from_sets


def compute_layer_a_case_metrics(case: DishQueryCase, response: Dict[str, Any]) -> Dict[str, Any]:
    gt_name = case.expected.dish_name_vi
    gt_ids: Set[str] = set(case.expected.gt_ingredient_ids)
    gt_core: Set[str] = set(case.expected.gt_core_ingredient_ids)

    dish_name = (response.get("dish") or {}).get("vietnamese_name") or (response.get("dish") or {}).get("name") or ""
    pred_ids = {
        item.get("ingredient_id")
        for item in ((response.get("cart") or {}).get("items") or [])
        if item.get("ingredient_id")
    }

    all_score = prf1_from_sets(gt_ids, pred_ids)
    core_score = prf1_from_sets(gt_core, pred_ids)

    excluded_ids = set(case.expected.excluded.ingredient_ids)
    extra_ids = set(case.expected.extra.ingredient_ids)

    return {
        "case_id": case.case_id,
        "split": case.split,
        "tags": ",".join(case.tags),
        "dish_ok": int(normalize_text(dish_name) == normalize_text(gt_name)),
        "precision_all": all_score["precision"],
        "recall_all": all_score["recall"],
        "f1_all": all_score["f1"],
        "precision_core": core_score["precision"],
        "recall_core": core_score["recall"],
        "f1_core": core_score["f1"],
        "excluded_ok": None if not excluded_ids else int(len(excluded_ids & pred_ids) == 0),
        "extra_ok": None if not extra_ids else int(extra_ids.issubset(pred_ids)),
        "gt_count": len(gt_ids),
        "pred_count": len(pred_ids),
        "error": None,
    }


def summarize_layer_a(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    data: List[Dict[str, Any]] = list(rows)
    if not data:
        return {"n_cases": 0}

    def _mean(key: str) -> float:
        vals = [float(r[key]) for r in data if r.get(key) is not None]
        return sum(vals) / len(vals) if vals else 0.0

    return {
        "n_cases": len(data),
        "dish_accuracy": _mean("dish_ok"),
        "macro_f1_all": _mean("f1_all"),
        "macro_f1_core": _mean("f1_core"),
        "excluded_ok_rate": _mean("excluded_ok"),
        "extra_ok_rate": _mean("extra_ok"),
        "error_rate": _mean("error"),
    }
