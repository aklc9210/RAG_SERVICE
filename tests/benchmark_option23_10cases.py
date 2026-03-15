"""
Benchmark for optimization option 2 + 3:
- Option 2: Keep heavy retriever/embedding objects warm
- Option 3: Keep Ollama model alive via keep_alive

Runs 10 cases where query dish name exactly matches ground truth dish name.
Outputs:
- progress with tqdm
- per-case metrics and retrieval outputs
- aggregate summary
- saved JSON report under processed/reports/

Run:
    python tests/benchmark_option23_10cases.py
"""

import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from statistics import mean

from dotenv import load_dotenv
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
SERVICE_ROOT = Path(__file__).resolve().parent.parent
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

load_dotenv(SERVICE_ROOT / ".env")

from app.pipeline import ShoppingCartPipeline  # noqa: E402


def norm_text(text: str) -> str:
    text = (text or "").strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_name_set(items):
    aliases = {
        "muoi": "muoi hat nem",
        "hat nem": "muoi hat nem",
    }
    out = set()
    for name in items:
        n = norm_text(name)
        if not n:
            continue
        out.add(aliases.get(n, n))
    return out


def f1_from_sets(pred_set, gt_set):
    tp = len(pred_set & gt_set)
    fp = len(pred_set - gt_set)
    fn = len(gt_set - pred_set)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "pred_count": len(pred_set),
        "gt_count": len(gt_set),
    }


def load_ground_truth_cases(limit=10):
    kb_path = SERVICE_ROOT / "app" / "data" / "knowledge_base" / "dish_knowledge_base.json"
    with open(kb_path, "r", encoding="utf-8") as fh:
        dishes = json.load(fh)

    # Use exact-name queries from KB so input dish name matches ground truth.
    # Select deterministic first `limit` dishes with >= 6 ingredients for meaningful F1.
    selected = []
    for dish in dishes:
        name_vi = (dish.get("name_vi") or "").strip()
        ingredients = dish.get("ingredients") or []
        if not name_vi:
            continue
        if len(ingredients) < 6:
            continue

        gt_ings = [
            ing.get("name_vi", "")
            for ing in ingredients
            if isinstance(ing, dict) and ing.get("name_vi")
        ]
        if len(gt_ings) < 6:
            continue

        selected.append(
            {
                "dish_id": dish.get("id"),
                "dish_name": name_vi,
                "ground_truth_ingredients": gt_ings,
            }
        )
        if len(selected) >= limit:
            break

    return selected


def main():
    cases = load_ground_truth_cases(limit=10)
    if len(cases) < 10:
        raise RuntimeError(f"Not enough benchmark cases found. Got {len(cases)}")

    report = {
        "meta": {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "optimization": "option2_keep_warm_objects + option3_ollama_keep_alive",
            "model": os.getenv("OLLAMA_TEXT_MODEL"),
            "ollama_keep_alive": os.getenv("OLLAMA_KEEP_ALIVE"),
            "reuse_shared_retriever": os.getenv("REUSE_SHARED_RETRIEVER"),
            "recipe_top_k": os.getenv("RECIPE_TOP_K"),
            "recipe_context_chars": os.getenv("RECIPE_CONTEXT_CHARS"),
            "extract_max_tokens": os.getenv("EXTRACT_MAX_TOKENS"),
            "recipe_max_tokens": os.getenv("RECIPE_MAX_TOKENS"),
            "case_count": len(cases),
        },
        "cases": [],
        "summary": {},
    }

    # Single pipeline instance for the whole benchmark to keep objects warm.
    pipeline = ShoppingCartPipeline()

    # Force KB service init once, then wrap retrieval for capture.
    pipeline.kb_service._ensure_init()

    captured = {"query": "", "results": []}
    original_search = pipeline.kb_service._retriever.search_filtered

    def wrapped_search_filtered(*args, **kwargs):
        query_text = kwargs.get("query_text")
        if query_text is None and len(args) > 0:
            query_text = args[0]
        results = original_search(*args, **kwargs)
        captured["query"] = query_text or ""
        captured["results"] = results
        return results

    pipeline.kb_service._retriever.search_filtered = wrapped_search_filtered

    per_case_time = []
    per_case_f1 = []

    for case in tqdm(cases, desc="Benchmark 10 cases", unit="case"):
        dish_name = case["dish_name"]
        gt_list = case["ground_truth_ingredients"]

        captured["query"] = ""
        captured["results"] = []

        t0 = time.perf_counter()
        response = pipeline.process(dish_name)
        elapsed = time.perf_counter() - t0

        cart_items = ((response or {}).get("cart") or {}).get("items") or []
        pred_list = [
            item.get("vietnamese_name", "")
            for item in cart_items
            if isinstance(item, dict)
        ]

        pred_set = normalize_name_set(pred_list)
        gt_set = normalize_name_set(gt_list)
        metrics = f1_from_sets(pred_set, gt_set)

        per_case_time.append(elapsed)
        per_case_f1.append(metrics["f1"])

        report["cases"].append(
            {
                "dish_id": case["dish_id"],
                "dish_name": dish_name,
                "elapsed_s": round(elapsed, 2),
                "status": (response or {}).get("status"),
                "error": (response or {}).get("error"),
                "metrics": metrics,
                "ground_truth_ingredients": gt_list,
                "retrieved_ingredients": pred_list,
                "retrieval_output": {
                    "query": captured["query"],
                    "top_k_docs": captured["results"],
                },
            }
        )

    report["summary"] = {
        "avg_elapsed_s": round(mean(per_case_time), 2),
        "min_elapsed_s": round(min(per_case_time), 2),
        "max_elapsed_s": round(max(per_case_time), 2),
        "avg_f1": round(mean(per_case_f1), 4),
        "min_f1": round(min(per_case_f1), 4),
        "max_f1": round(max(per_case_f1), 4),
    }

    out_dir = SERVICE_ROOT / "processed" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"benchmark_option23_10cases_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    print("\nBenchmark completed")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"Saved report: {out_path}")


if __name__ == "__main__":
    main()
