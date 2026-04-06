#!/usr/bin/env python3
"""
Build ground truth for Task 2 — Flavor-enhancing Ingredients.

For each dish in the test set:
  - Core ingredients = main_ingredients (from processed/dishes/*.json)
  - Flavor-enhancing candidates = all non-core ingredients that co-appear with core
  - Score each candidate by: mean PMI(candidate, core_ingredient) across core ingredients
  - Ground truth = top-10 candidates with highest mean PMI > 0

Reads:
    data/splits/test_ids.txt
    processed/dishes/*.json
    app/data/cooccurrence/pmi.json
    app/data/knowledge_base/ingredient_knowledge_base.json

Writes:
    evaluation/data/datasets/task2_flavor_gt.jsonl
    evaluation/data/datasets/task2_stats.json

Each JSONL line:
    {
        "dish_id": str,
        "dish_name": str,
        "core_ingredient_ids": [str],
        "flavor_enhancing": [
            {"ingredient_id": str, "name_vi": str, "mean_pmi": float}
        ]   # top-10, sorted by mean_pmi desc
    }

Usage:
    python scripts/build_task2_gt.py
    python scripts/build_task2_gt.py --top-k 10 --min-pmi 0
"""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DISHES_DIR = ROOT / "processed" / "dishes"
SPLITS_DIR = ROOT / "data" / "splits"
OUT_DIR = ROOT / "evaluation" / "data" / "datasets"
PMI_PATH = ROOT / "app" / "data" / "cooccurrence" / "pmi.json"
IKB_PATH = ROOT / "app" / "data" / "knowledge_base" / "ingredient_knowledge_base.json"


def parse_args():
    parser = argparse.ArgumentParser(description="Build ground truth for Task 2.")
    parser.add_argument("--top-k", type=int, default=10,
                        help="Number of flavor-enhancing ingredients per dish (default: 10)")
    parser.add_argument("--min-pmi", type=float, default=0.0,
                        help="Minimum mean PMI to include a candidate (default: 0.0)")
    return parser.parse_args()


def build_ingredient_name_map(ikb):
    """Build {ingredient_id: name_vi} lookup from ingredient KB."""
    id_to_name = {}
    for entry in ikb:
        iid = entry.get("id")
        name = entry.get("name_vi") or entry.get("name_normalized") or ""
        if iid:
            id_to_name[iid] = name
    return id_to_name


def get_flavor_enhancing(dish, pmi, id_to_name, top_k, min_pmi):
    """
    For a single dish, compute mean PMI of each non-core ingredient vs all core ingredients.
    Returns sorted list of {ingredient_id, name_vi, mean_pmi}.
    """
    core_ids = set()

    # Use ingredient_ids aligned with main_ingredients (first N ids = main_ingredients)
    main = dish.get("main_ingredients", [])
    all_ids = dish.get("ingredient_ids", [])
    all_names_vi = dish.get("ingredient_names_vi", [])

    # Build name→id map for this dish
    name_to_id = {}
    for idx, name in enumerate(all_names_vi):
        if idx < len(all_ids):
            name_to_id[name.lower().strip()] = all_ids[idx]

    # Resolve core ingredient IDs from main_ingredients names
    for name in main:
        iid = name_to_id.get(name.lower().strip())
        if iid:
            core_ids.add(iid)

    # Fallback: if no core resolved, use first half of ingredient_ids
    if not core_ids and all_ids:
        core_ids = set(all_ids[: max(1, len(all_ids) // 2)])

    if not core_ids:
        return []

    # Non-core candidate ingredients (all ingredient_ids minus core)
    non_core_ids = set(all_ids) - core_ids

    # Score each non-core ingredient by mean PMI with core
    scored = []
    for candidate_id in non_core_ids:
        pmi_scores = []
        for core_id in core_ids:
            # PMI matrix is not symmetric — check both directions
            score = None
            if core_id in pmi and candidate_id in pmi[core_id]:
                score = pmi[core_id][candidate_id]
            elif candidate_id in pmi and core_id in pmi[candidate_id]:
                score = pmi[candidate_id][core_id]
            if score is not None:
                pmi_scores.append(score)

        if not pmi_scores:
            continue

        mean_pmi = sum(pmi_scores) / len(pmi_scores)
        if mean_pmi < min_pmi:
            continue

        scored.append({
            "ingredient_id": candidate_id,
            "name_vi": id_to_name.get(candidate_id, ""),
            "mean_pmi": round(mean_pmi, 4),
        })

    # Sort by mean PMI descending, return top-k
    scored.sort(key=lambda x: x["mean_pmi"], reverse=True)
    return scored[:top_k]


def main():
    args = parse_args()

    print("=== Building Ground Truth — Task 2 (Flavor-enhancing Ingredients) ===")
    print(f"Top-K   : {args.top_k}")
    print(f"Min PMI : {args.min_pmi}")

    # Load data
    test_ids = (SPLITS_DIR / "test_ids.txt").read_text(encoding="utf-8").splitlines()
    test_ids = [x for x in test_ids if x.strip()]

    print(f"\nLoading PMI ({PMI_PATH.name})...")
    pmi = json.loads(PMI_PATH.read_text(encoding="utf-8"))
    print(f"  PMI entries: {len(pmi)}")

    print(f"Loading ingredient KB...")
    ikb = json.loads(IKB_PATH.read_text(encoding="utf-8"))
    id_to_name = build_ingredient_name_map(ikb)
    print(f"  Ingredient name map: {len(id_to_name)}")

    # Process each test dish
    results = []
    n_skipped = 0
    n_with_flavor = 0
    total_flavor = 0

    for dish_id in test_ids:
        path = DISHES_DIR / f"{dish_id}.json"
        if not path.exists():
            n_skipped += 1
            continue

        dish = json.loads(path.read_text(encoding="utf-8"))
        flavor = get_flavor_enhancing(dish, pmi, id_to_name, args.top_k, args.min_pmi)

        # Resolve core IDs for output
        main = dish.get("main_ingredients", [])
        all_ids = dish.get("ingredient_ids", [])
        all_names = dish.get("ingredient_names_vi", [])
        name_to_id = {}
        for idx, name in enumerate(all_names):
            if idx < len(all_ids):
                name_to_id[name.lower().strip()] = all_ids[idx]
        core_ids = [name_to_id[n.lower().strip()] for n in main if n.lower().strip() in name_to_id]

        entry = {
            "dish_id": dish_id,
            "dish_name": dish.get("name_vi", ""),
            "category": dish.get("category", ""),
            "core_ingredient_ids": core_ids,
            "core_ingredient_names": main,
            "flavor_enhancing": flavor,
        }
        results.append(entry)

        if flavor:
            n_with_flavor += 1
            total_flavor += len(flavor)

    print(f"\n  Dishes processed    : {len(results)}")
    print(f"  Skipped (no file)   : {n_skipped}")
    print(f"  With flavor results : {n_with_flavor}")
    print(f"  Avg flavor per dish : {total_flavor / max(n_with_flavor, 1):.1f}")

    # Write output
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_jsonl = OUT_DIR / "task2_flavor_gt.jsonl"
    out_stats = OUT_DIR / "task2_stats.json"

    with open(out_jsonl, "w", encoding="utf-8") as f:
        for entry in results:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    stats = {
        "n_test_dishes": len(test_ids),
        "n_processed": len(results),
        "n_with_flavor": n_with_flavor,
        "n_without_flavor": len(results) - n_with_flavor,
        "avg_flavor_per_dish": round(total_flavor / max(n_with_flavor, 1), 2),
        "top_k": args.top_k,
        "min_pmi": args.min_pmi,
    }
    out_stats.write_text(json.dumps(stats, indent=2), encoding="utf-8")

    print(f"\nWritten: {out_jsonl}")
    print(f"Written: {out_stats}")
    print("\nDone.")


if __name__ == "__main__":
    main()
