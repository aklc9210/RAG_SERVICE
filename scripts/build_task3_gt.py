#!/usr/bin/env python3
"""
Build Dish Relatedness scores and ground truth for Task 3 — Related Dishes.

Formula (no region field available):
    Relatedness(A, B) = 0.7 * Jaccard(A, B) + 0.3 * same_category(A, B)

    Jaccard(A, B) = |ingredients_A ∩ ingredients_B| / |ingredients_A ∪ ingredients_B|

For each dish in the test set, compute Relatedness against all OTHER dishes in the test set,
then take top-5 as ground truth.

Reads:
    data/splits/test_ids.txt
    processed/dishes/*.json

Writes:
    evaluation/data/datasets/task3_related_gt.jsonl
    evaluation/data/datasets/task3_stats.json

Each JSONL line:
    {
        "dish_id": str,
        "dish_name": str,
        "category": str,
        "ingredient_ids": [str],
        "related": [
            {"dish_id": str, "dish_name": str, "relatedness": float,
             "jaccard": float, "same_category": bool}
        ]  # top-5, sorted by relatedness desc
    }

Usage:
    python scripts/build_task3_gt.py
    python scripts/build_task3_gt.py --top-k 5 --alpha 0.7 --beta 0.3
"""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DISHES_DIR = ROOT / "processed" / "dishes"
SPLITS_DIR = ROOT / "data" / "splits"
OUT_DIR = ROOT / "evaluation" / "data" / "datasets"


def parse_args():
    parser = argparse.ArgumentParser(description="Build ground truth for Task 3.")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--alpha", type=float, default=0.7, help="Jaccard weight")
    parser.add_argument("--beta", type=float, default=0.3, help="Category weight")
    return parser.parse_args()


def jaccard(set_a, set_b):
    if not set_a or not set_b:
        return 0.0
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union > 0 else 0.0


def main():
    args = parse_args()

    print("=== Building Ground Truth — Task 3 (Related Dishes) ===")
    print(f"alpha={args.alpha}, beta={args.beta}, top_k={args.top_k}")

    test_ids = (SPLITS_DIR / "test_ids.txt").read_text(encoding="utf-8").splitlines()
    test_ids = [x for x in test_ids if x.strip()]
    print(f"Test dishes: {len(test_ids)}")

    # Load all test dishes
    dishes = {}
    for dish_id in test_ids:
        path = DISHES_DIR / f"{dish_id}.json"
        if path.exists():
            d = json.loads(path.read_text(encoding="utf-8"))
            dishes[dish_id] = {
                "name_vi": d.get("name_vi", ""),
                "category": d.get("category", "unknown"),
                "ingredient_ids": set(d.get("ingredient_ids", [])),
            }

    print(f"Loaded: {len(dishes)} dishes")
    print("Computing pairwise relatedness (this may take ~30s)...")

    dish_ids = list(dishes.keys())
    results = []
    n_with_related = 0

    for i, dish_id in enumerate(dish_ids):
        dish_a = dishes[dish_id]
        ing_a = dish_a["ingredient_ids"]
        cat_a = dish_a["category"]

        scored = []
        for other_id in dish_ids:
            if other_id == dish_id:
                continue
            dish_b = dishes[other_id]
            ing_b = dish_b["ingredient_ids"]
            cat_b = dish_b["category"]

            j = jaccard(ing_a, ing_b)
            same_cat = 1 if cat_a == cat_b else 0
            relatedness = args.alpha * j + args.beta * same_cat

            if relatedness > 0:
                scored.append({
                    "dish_id": other_id,
                    "dish_name": dish_b["name_vi"],
                    "relatedness": round(relatedness, 4),
                    "jaccard": round(j, 4),
                    "same_category": bool(same_cat),
                })

        scored.sort(key=lambda x: x["relatedness"], reverse=True)
        top = scored[: args.top_k]

        entry = {
            "dish_id": dish_id,
            "dish_name": dish_a["name_vi"],
            "category": cat_a,
            "ingredient_ids": list(ing_a),
            "related": top,
        }
        results.append(entry)

        if top:
            n_with_related += 1

        if (i + 1) % 500 == 0:
            print(f"  Processed {i + 1}/{len(dish_ids)}...")

    avg_relatedness = 0.0
    total = 0
    for r in results:
        for rel in r["related"]:
            avg_relatedness += rel["relatedness"]
            total += 1
    avg_relatedness = avg_relatedness / total if total > 0 else 0.0

    print(f"\n  Dishes with related : {n_with_related}/{len(results)}")
    print(f"  Avg top-1 relatedness: {avg_relatedness:.4f}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_jsonl = OUT_DIR / "task3_related_gt.jsonl"
    out_stats = OUT_DIR / "task3_stats.json"

    with open(out_jsonl, "w", encoding="utf-8") as f:
        for entry in results:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    stats = {
        "n_test_dishes": len(test_ids),
        "n_processed": len(results),
        "n_with_related": n_with_related,
        "top_k": args.top_k,
        "alpha": args.alpha,
        "beta": args.beta,
        "gamma": 0.0,
        "region_available": False,
        "avg_relatedness_across_top5": round(avg_relatedness, 4),
    }
    out_stats.write_text(json.dumps(stats, indent=2), encoding="utf-8")

    print(f"\nWritten: {out_jsonl}")
    print(f"Written: {out_stats}")
    print("\nDone.")


if __name__ == "__main__":
    main()
