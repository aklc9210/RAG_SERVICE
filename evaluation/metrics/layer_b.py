from __future__ import annotations

from typing import Any, Dict, Iterable, List, Set, Tuple

from ..contracts import ConflictCase
from .common import prf1_from_pairs


def build_gt_pairs(case: ConflictCase) -> Set[Tuple[str, str]]:
    out: Set[Tuple[str, str]] = set()
    for pair in case.expected.conflict_pairs:
        out.add(tuple(sorted((pair.a_id, pair.b_id))))
    return out


def compute_layer_b_case_metrics(case: ConflictCase, pred_pairs: Set[Tuple[str, str]]) -> Dict[str, Any]:
    gt_pairs = build_gt_pairs(case)
    score = prf1_from_pairs(gt_pairs, pred_pairs)
    return {
        "case_id": case.case_id,
        "format": case.input_ingredients.format,
        "tags": ",".join(case.tags),
        "gt_conflicts": len(gt_pairs),
        "pred_conflicts": len(pred_pairs),
        "precision": score["precision"],
        "recall": score["recall"],
        "f1": score["f1"],
        "error": None,
    }


def summarize_layer_b(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    data: List[Dict[str, Any]] = list(rows)
    if not data:
        return {"n_cases": 0}

    mean_f1 = sum(float(r.get("f1", 0.0)) for r in data) / len(data)
    by_format: Dict[str, List[float]] = {}
    for row in data:
        fmt = str(row.get("format", "unknown"))
        by_format.setdefault(fmt, []).append(float(row.get("f1", 0.0)))

    return {
        "n_cases": len(data),
        "macro_f1": mean_f1,
        "f1_by_format": {k: (sum(v) / len(v) if v else 0.0) for k, v in by_format.items()},
    }
