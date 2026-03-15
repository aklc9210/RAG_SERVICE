from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Set


def compute_layer_c_case_metrics(
    case_id: str,
    target_id: str,
    target_category: Optional[str],
    exclude_ids: Set[str],
    max_suggestions: int,
    suggestion_ids: List[str],
    id_to_category: Dict[str, Optional[str]],
) -> Dict[str, Any]:
    picked = suggestion_ids[:max_suggestions]
    seen: Set[str] = set()

    checks: List[Dict[str, Any]] = []
    for sid in picked:
        same_category = bool(target_category and id_to_category.get(sid) == target_category)
        not_excluded = sid not in exclude_ids
        unique = sid not in seen
        seen.add(sid)
        checks.append(
            {
                "suggestion_id": sid,
                "same_category": same_category,
                "not_excluded": not_excluded,
                "unique": unique,
                "valid": same_category and not_excluded and unique,
            }
        )

    count = len(checks)
    valid_count = sum(1 for item in checks if item["valid"])

    return {
        "case_id": case_id,
        "target_replace_id": target_id,
        "target_category": target_category,
        "n_suggestions": len(picked),
        "cap_ok": int(len(picked) <= max_suggestions),
        "overall_valid_rate": (valid_count / count) if count else 0.0,
        "coverage": int(valid_count > 0),
        "category_match_rate": (sum(1 for item in checks if item["same_category"]) / count) if count else 0.0,
        "exclusion_compliance_rate": (sum(1 for item in checks if item["not_excluded"]) / count) if count else 0.0,
        "uniqueness_rate": (sum(1 for item in checks if item["unique"]) / count) if count else 0.0,
        "error": None,
    }


def summarize_layer_c(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    data: List[Dict[str, Any]] = list(rows)
    if not data:
        return {"n_cases": 0}

    def _mean(key: str) -> float:
        vals = [float(r.get(key, 0.0)) for r in data]
        return sum(vals) / len(vals) if vals else 0.0

    return {
        "n_cases": len(data),
        "overall_valid_rate_mean": _mean("overall_valid_rate"),
        "coverage_rate": _mean("coverage"),
        "category_match_rate": _mean("category_match_rate"),
        "exclusion_compliance_rate": _mean("exclusion_compliance_rate"),
        "uniqueness_rate": _mean("uniqueness_rate"),
    }
