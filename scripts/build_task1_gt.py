#!/usr/bin/env python3
"""
Build ground truth for Task 1 — Dish Retrieval.

Generates two types of queries from the test set:
  1. Exact-name queries  : from dish name → ground truth = that dish (score=2)
                           + other dishes in same category (score=1)
  2. Category queries    : from category → ground truth = all dishes in category (score=1)

Reads:
    data/splits/test_ids.txt
    processed/dishes/*.json

Writes:
    evaluation/data/datasets/task1_queries.jsonl
    evaluation/data/datasets/task1_stats.json

Each JSONL line:
    {
        "query_id": str,
        "query": str,
        "query_type": "exact_name" | "category",
        "target_dish_id": str | null,   # only for exact_name
        "category": str | null,         # only for category
        "relevant": {dish_id: score}    # score 2=exact, 1=same-category, 0=irrelevant (omitted)
    }

Usage:
    python scripts/build_task1_gt.py
    python scripts/build_task1_gt.py --max-exact 500 --max-category 50
"""

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DISHES_DIR = ROOT / "processed" / "dishes"
SPLITS_DIR = ROOT / "data" / "splits"
OUT_DIR = ROOT / "evaluation" / "data" / "datasets"

# Vietnamese query templates for exact-name queries
EXACT_TEMPLATES = [
    "Tôi muốn ăn {name}",
    "Cho tôi {name}",
    "Hướng dẫn nấu {name}",
    "Công thức món {name}",
    "{name}",
]

# Category → human-readable Vietnamese query templates
CATEGORY_QUERIES = {
    "mon banh":         ["Cho tôi món bánh", "Tôi muốn ăn bánh", "Các loại bánh ngon"],
    "mon chien":        ["Món chiên giòn ngon", "Tôi muốn ăn món chiên", "Gợi ý món chiên"],
    "mon xao":          ["Tôi muốn ăn món xào", "Món xào nhanh cho bữa cơm", "Gợi ý món xào"],
    "mon canh":         ["Cho tôi món canh", "Tôi muốn nấu canh", "Gợi ý món canh ngon"],
    "mon kho":          ["Món kho đậm đà", "Tôi muốn ăn món kho", "Gợi ý món kho"],
    "mon nuong":        ["Tôi muốn ăn món nướng", "Gợi ý món nướng", "Món nướng thơm ngon"],
    "an vat":           ["Gợi ý món ăn vặt", "Tôi muốn ăn vặt", "Ăn vặt ngon"],
    "thuc uong":        ["Gợi ý thức uống", "Tôi muốn uống gì ngon", "Đồ uống giải khát"],
    "mon goi - salad":  ["Gợi ý món gỏi", "Tôi muốn ăn gỏi", "Salad tươi mát"],
    "mon nuoc":         ["Tôi muốn ăn món nước", "Gợi ý món nước", "Cho tôi món nước ngon"],
    "mon trang mieng":  ["Tráng miệng ngon", "Gợi ý món tráng miệng", "Tôi muốn ăn tráng miệng"],
    "mon lau":          ["Tôi muốn ăn lẩu", "Gợi ý các loại lẩu", "Lẩu ngon hôm nay"],
    "mon hap":          ["Món hấp thanh đạm", "Tôi muốn ăn món hấp", "Gợi ý món hấp"],
    "ngay le tet":      ["Món ăn ngày lễ tết", "Món đặc biệt ngày tết", "Gợi ý món lễ tết"],
    "mon kem":          ["Tôi muốn ăn kem", "Các loại kem ngon", "Gợi ý món kem"],
    "mon tu ga":        ["Món từ gà ngon", "Tôi muốn nấu món gà", "Gợi ý món gà"],
    "mon cuon - tron":  ["Món cuốn ngon", "Gợi ý món cuốn", "Tôi muốn ăn món cuốn"],
    "mon tu bo":        ["Món từ bò ngon", "Tôi muốn ăn món bò", "Gợi ý món bò"],
    "tra sua":          ["Tôi muốn uống trà sữa", "Gợi ý trà sữa", "Các loại trà sữa ngon"],
    "nuoc ep":          ["Nước ép hoa quả tươi", "Tôi muốn uống nước ép", "Gợi ý nước ép"],
    "sinh to":          ["Tôi muốn uống sinh tố", "Gợi ý sinh tố", "Sinh tố ngon bổ dưỡng"],
    "mon kho - mam":    ["Món kho mắm đậm đà", "Gợi ý món mắm", "Tôi muốn ăn món kho mắm"],
    "mon chao":         ["Tôi muốn ăn cháo", "Gợi ý món cháo", "Cháo ngon bổ dưỡng"],
    "mon che":          ["Tôi muốn ăn chè", "Gợi ý các loại chè", "Chè ngọt mát"],
    "mon chay":         ["Món chay thanh tịnh", "Tôi muốn ăn chay", "Gợi ý món chay"],
}


def parse_args():
    parser = argparse.ArgumentParser(description="Build ground truth for Task 1.")
    parser.add_argument("--max-exact", type=int, default=600,
                        help="Max exact-name queries (default: 600)")
    parser.add_argument("--max-category", type=int, default=75,
                        help="Max category queries per category (default: 75, capped at available)")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def load_test_dishes(test_ids):
    dishes = {}
    for dish_id in test_ids:
        path = DISHES_DIR / f"{dish_id}.json"
        if path.exists():
            dishes[dish_id] = json.loads(path.read_text(encoding="utf-8"))
    return dishes


def main():
    args = parse_args()
    rng = random.Random(args.seed)

    print("=== Building Ground Truth — Task 1 (Dish Retrieval) ===")

    # Load splits
    test_ids = (SPLITS_DIR / "test_ids.txt").read_text(encoding="utf-8").splitlines()
    test_ids = [x for x in test_ids if x.strip()]
    print(f"Test dishes: {len(test_ids)}")

    dishes = load_test_dishes(test_ids)
    print(f"Loaded: {len(dishes)} dishes")

    # Build category index over test set
    category_index = {}   # category → [dish_id]
    for dish_id, dish in dishes.items():
        cat = dish.get("category", "unknown")
        category_index.setdefault(cat, []).append(dish_id)

    queries = []
    query_counter = 0

    # ----------------------------------------------------------------
    # 1. Exact-name queries
    # ----------------------------------------------------------------
    sampled_dishes = rng.sample(list(dishes.keys()), min(args.max_exact, len(dishes)))

    for dish_id in sampled_dishes:
        dish = dishes[dish_id]
        name = dish.get("name_vi", "").strip()
        if not name:
            continue

        template = rng.choice(EXACT_TEMPLATES)
        query_text = template.format(name=name)
        cat = dish.get("category", "unknown")

        relevant = {dish_id: 2}
        # All other dishes in same category get score=1
        for other_id in category_index.get(cat, []):
            if other_id != dish_id:
                relevant[other_id] = 1

        queries.append({
            "query_id": f"q{query_counter:04d}",
            "query": query_text,
            "query_type": "exact_name",
            "target_dish_id": dish_id,
            "category": cat,
            "relevant": relevant,
        })
        query_counter += 1

    print(f"  Exact-name queries : {sum(1 for q in queries if q['query_type'] == 'exact_name')}")

    # ----------------------------------------------------------------
    # 2. Category queries
    # ----------------------------------------------------------------
    for cat, dish_ids_in_cat in sorted(category_index.items()):
        templates = CATEGORY_QUERIES.get(cat)
        if not templates:
            continue

        for query_text in templates:
            relevant = {did: 1 for did in dish_ids_in_cat}
            queries.append({
                "query_id": f"q{query_counter:04d}",
                "query": query_text,
                "query_type": "category",
                "target_dish_id": None,
                "category": cat,
                "relevant": relevant,
            })
            query_counter += 1

    print(f"  Category queries   : {sum(1 for q in queries if q['query_type'] == 'category')}")
    print(f"  Total queries      : {len(queries)}")

    # ----------------------------------------------------------------
    # Write output
    # ----------------------------------------------------------------
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_jsonl = OUT_DIR / "task1_queries.jsonl"
    out_stats = OUT_DIR / "task1_stats.json"

    with open(out_jsonl, "w", encoding="utf-8") as f:
        for q in queries:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

    stats = {
        "total_queries": len(queries),
        "exact_name_queries": sum(1 for q in queries if q["query_type"] == "exact_name"),
        "category_queries": sum(1 for q in queries if q["query_type"] == "category"),
        "n_test_dishes": len(test_ids),
        "n_categories": len(category_index),
        "seed": args.seed,
    }
    out_stats.write_text(json.dumps(stats, indent=2), encoding="utf-8")

    print(f"\nWritten: {out_jsonl}")
    print(f"Written: {out_stats}")
    print("\nDone.")


if __name__ == "__main__":
    main()
