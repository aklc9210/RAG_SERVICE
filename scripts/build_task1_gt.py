#!/usr/bin/env python3
"""
Build ground truth for Task 1 — Dish Retrieval.

Generates four types of queries from the test set:
  1. Exact-name queries    : dish name → GT = that dish (score=2) + same category (score=1)
  2. Category queries      : category phrase → GT = all dishes in category (score=1)
  3. Ingredient queries    : "Món có X [và Y]" → GT = dishes containing those ingredients
                             score=2 if ingredient is main, score=1 otherwise
  4. Paraphrase queries    : shortened/first-2-token version of multi-word dish names
                             → GT = same as exact-name for that dish

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
        "query_type": "exact_name" | "category" | "ingredient" | "paraphrase",
        "target_dish_id": str | null,
        "category": str | null,
        "relevant": {dish_id: score}
    }

Usage:
    python scripts/build_task1_gt.py
    python scripts/build_task1_gt.py --max-exact 200 --max-category 75 --max-ingredient 200 --max-paraphrase 100
"""

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DISHES_DIR = ROOT / "processed" / "dishes"
SPLITS_DIR = ROOT / "data" / "splits"
OUT_DIR = ROOT / "evaluation" / "data" / "datasets"

EXACT_TEMPLATES = [
    "Tôi muốn ăn {name}",
    "Cho tôi {name}",
    "Hướng dẫn nấu {name}",
    "Công thức món {name}",
    "{name}",
]

INGREDIENT_TEMPLATES_1 = [
    "Món có {ing1}",
    "Gợi ý món dùng {ing1}",
    "Tôi có {ing1}, nấu món gì",
    "Món nấu với {ing1}",
    "Nấu gì với {ing1}",
]

INGREDIENT_TEMPLATES_2 = [
    "Món có {ing1} và {ing2}",
    "Tôi có {ing1} và {ing2}, nấu món gì",
    "Gợi ý món dùng {ing1} và {ing2}",
    "Nấu gì với {ing1} và {ing2}",
    "Món kết hợp {ing1} với {ing2}",
]

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
    parser.add_argument("--max-exact", type=int, default=200,
                        help="Max exact-name queries (default: 200)")
    parser.add_argument("--max-category", type=int, default=75,
                        help="Max category queries (default: 75, capped at available)")
    parser.add_argument("--max-ingredient", type=int, default=200,
                        help="Max ingredient-based queries (default: 200)")
    parser.add_argument("--max-paraphrase", type=int, default=100,
                        help="Max paraphrase queries from multi-word dish names (default: 100)")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def load_test_dishes(test_ids):
    dishes = {}
    for dish_id in test_ids:
        path = DISHES_DIR / f"{dish_id}.json"
        if path.exists():
            dishes[dish_id] = json.loads(path.read_text(encoding="utf-8"))
    return dishes


def _shorten_name(name: str) -> str:
    """Return first 2 tokens of a Vietnamese dish name if it has 3+ tokens."""
    tokens = name.strip().split()
    if len(tokens) >= 3:
        return " ".join(tokens[:2])
    return ""


def main():
    args = parse_args()
    rng = random.Random(args.seed)

    print("=== Building Ground Truth — Task 1 (Dish Retrieval) ===")

    test_ids = (SPLITS_DIR / "test_ids.txt").read_text(encoding="utf-8").splitlines()
    test_ids = [x for x in test_ids if x.strip()]
    print(f"Test dishes: {len(test_ids)}")

    dishes = load_test_dishes(test_ids)
    print(f"Loaded: {len(dishes)} dishes")

    # Build category index
    category_index = {}
    for dish_id, dish in dishes.items():
        cat = dish.get("category", "unknown")
        category_index.setdefault(cat, []).append(dish_id)

    # Build ingredient → dish_ids index (ingredient name → set of dish_ids)
    # Also track whether ingredient is a main ingredient per dish
    ing_name_to_dishes: dict = {}   # norm_ing_name → {dish_id: score}
    for dish_id, dish in dishes.items():
        main_names = {n.lower().strip() for n in dish.get("main_ingredients", [])}
        for ing_name in dish.get("ingredient_names_vi", []):
            norm = ing_name.lower().strip()
            if not norm:
                continue
            if norm not in ing_name_to_dishes:
                ing_name_to_dishes[norm] = {}
            score = 2 if norm in main_names else 1
            # Keep max score if dish appears via multiple ingredients
            ing_name_to_dishes[norm][dish_id] = max(
                ing_name_to_dishes[norm].get(dish_id, 0), score
            )

    # Filter: only ingredients appearing in 3–200 dishes (not too rare, not too generic like muối)
    useful_ingredients = {
        name: dish_map
        for name, dish_map in ing_name_to_dishes.items()
        if 3 <= len(dish_map) <= 200
    }
    print(f"Useful ingredients for queries: {len(useful_ingredients)}")

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

    # ----------------------------------------------------------------
    # 3. Ingredient-based queries
    # ----------------------------------------------------------------
    ing_names_pool = list(useful_ingredients.keys())
    rng.shuffle(ing_names_pool)

    ingredient_query_count = 0
    used_singles: set = set()
    used_pairs: set = set()

    # Single-ingredient queries (half of budget)
    single_budget = args.max_ingredient // 2
    for ing_name in ing_names_pool:
        if ingredient_query_count >= single_budget:
            break
        if ing_name in used_singles:
            continue
        dish_map = useful_ingredients[ing_name]
        template = rng.choice(INGREDIENT_TEMPLATES_1)
        query_text = template.format(ing1=ing_name)
        queries.append({
            "query_id": f"q{query_counter:04d}",
            "query": query_text,
            "query_type": "ingredient",
            "target_dish_id": None,
            "category": None,
            "relevant": dict(dish_map),
        })
        query_counter += 1
        ingredient_query_count += 1
        used_singles.add(ing_name)

    # Two-ingredient queries (remaining budget)
    pair_budget = args.max_ingredient - ingredient_query_count
    ing_names_list = list(used_singles)
    rng.shuffle(ing_names_list)
    for i in range(len(ing_names_list)):
        if ingredient_query_count - single_budget >= pair_budget:
            break
        ing1 = ing_names_list[i]
        for j in range(i + 1, len(ing_names_list)):
            pair_key = (ing1, ing_names_list[j])
            if pair_key in used_pairs:
                continue
            ing2 = ing_names_list[j]
            # GT = dishes containing BOTH ingredients
            dishes1 = set(useful_ingredients[ing1].keys())
            dishes2 = set(useful_ingredients[ing2].keys())
            both = dishes1 & dishes2
            if len(both) < 2:
                continue
            relevant = {}
            for did in both:
                s1 = useful_ingredients[ing1].get(did, 1)
                s2 = useful_ingredients[ing2].get(did, 1)
                relevant[did] = max(s1, s2)
            template = rng.choice(INGREDIENT_TEMPLATES_2)
            query_text = template.format(ing1=ing1, ing2=ing2)
            queries.append({
                "query_id": f"q{query_counter:04d}",
                "query": query_text,
                "query_type": "ingredient",
                "target_dish_id": None,
                "category": None,
                "relevant": relevant,
            })
            query_counter += 1
            ingredient_query_count += 1
            used_pairs.add(pair_key)
            if ingredient_query_count - single_budget >= pair_budget:
                break

    print(f"  Ingredient queries : {sum(1 for q in queries if q['query_type'] == 'ingredient')}")

    # ----------------------------------------------------------------
    # 4. Paraphrase queries (shortened dish names)
    # ----------------------------------------------------------------
    paraphrase_candidates = []
    for dish_id, dish in dishes.items():
        name = dish.get("name_vi", "").strip()
        short = _shorten_name(name)
        if not short or short.lower() == name.lower():
            continue
        # Avoid duplicates: same short form maps to multiple dishes → ambiguous, skip
        paraphrase_candidates.append((dish_id, dish, name, short))

    # Deduplicate by short form: if multiple dishes share the same shortened name,
    # keep the one with most same-category siblings (richer GT)
    short_to_candidates: dict = {}
    for dish_id, dish, name, short in paraphrase_candidates:
        short_to_candidates.setdefault(short.lower(), []).append((dish_id, dish, name, short))

    paraphrase_pool = []
    for _, candidates in short_to_candidates.items():
        if len(candidates) == 1:
            paraphrase_pool.append(candidates[0])
        # If multiple dishes share the same short form, it's a valid ambiguous query:
        # GT = all those dishes (score=2) + their same-category dishes (score=1)
        else:
            paraphrase_pool.append(("_multi_", candidates, None, candidates[0][3]))

    rng.shuffle(paraphrase_pool)

    para_count = 0
    for item in paraphrase_pool:
        if para_count >= args.max_paraphrase:
            break
        if item[0] == "_multi_":
            _, candidates, _, short = item
            relevant = {}
            for dish_id, dish, _, _ in candidates:
                relevant[dish_id] = 2
                cat = dish.get("category", "unknown")
                for other_id in category_index.get(cat, []):
                    if other_id not in relevant:
                        relevant[other_id] = 1
            queries.append({
                "query_id": f"q{query_counter:04d}",
                "query": short,
                "query_type": "paraphrase",
                "target_dish_id": None,
                "category": None,
                "relevant": relevant,
            })
        else:
            dish_id, dish, name, short = item
            cat = dish.get("category", "unknown")
            relevant = {dish_id: 2}
            for other_id in category_index.get(cat, []):
                if other_id != dish_id:
                    relevant[other_id] = 1
            queries.append({
                "query_id": f"q{query_counter:04d}",
                "query": short,
                "query_type": "paraphrase",
                "target_dish_id": dish_id,
                "category": cat,
                "relevant": relevant,
            })
        query_counter += 1
        para_count += 1

    print(f"  Paraphrase queries : {sum(1 for q in queries if q['query_type'] == 'paraphrase')}")
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

    n_by_type = {}
    for q in queries:
        n_by_type[q["query_type"]] = n_by_type.get(q["query_type"], 0) + 1

    stats = {
        "total_queries": len(queries),
        "by_type": n_by_type,
        "n_test_dishes": len(test_ids),
        "n_categories": len(category_index),
        "n_useful_ingredients": len(useful_ingredients),
        "seed": args.seed,
    }
    out_stats.write_text(json.dumps(stats, indent=2), encoding="utf-8")

    print(f"\nWritten: {out_jsonl}")
    print(f"Written: {out_stats}")
    print("\nDone.")


if __name__ == "__main__":
    main()
