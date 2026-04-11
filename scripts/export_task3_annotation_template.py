#!/usr/bin/env python3
"""
Export annotation template for Task 3 — Related Dishes.

Design: Blind annotation to avoid bias.
  For each sampled dish A, build a pool of ~8 candidate dishes:
    - ~5 "ontology-top" candidates  (high IDF-Jaccard with A) — likely positives
    - ~3 "hard-negative" candidates (same category, low ingredient overlap) — likely negatives
  Candidates are SHUFFLED — annotator cannot tell which source they came from.

  Annotator question:
    "Món [candidate_dish_name] có LIÊN QUAN đến món [dish_name] không?"
    1 = Có (related)   0 = Không (not related)

This lets us:
  1. Build an independent GT free from the IDF-Jaccard circular bias.
  2. Measure IAA (Cohen's Kappa) between the two annotators.
  3. Use ranking-within-pool protocol (same as Task 2) for P@k / NDCG@k.

Reads:
    data/splits/test_ids.txt
    processed/dishes/*.json
    evaluation/data/datasets/task3_related_gt.jsonl
    app/data/cooccurrence/frequency.json
    app/data/cooccurrence/metadata.json

Writes:
    evaluation/annotation/task3_annotation_template.csv   — for annotators
    evaluation/annotation/task3_annotation_answer_key.json — internal (source labels)
    evaluation/annotation/README_task3_annotation.md

Usage:
    python scripts/export_task3_annotation_template.py
    python scripts/export_task3_annotation_template.py --n-dishes 50 --n-top 5 --n-hard 3 --seed 42
"""

import argparse
import csv
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DISHES_DIR  = ROOT / "processed" / "dishes"
SPLITS_DIR  = ROOT / "data" / "splits"
DATASETS_DIR = ROOT / "evaluation" / "data" / "datasets"
FREQ_PATH   = ROOT / "app" / "data" / "cooccurrence" / "frequency.json"
META_PATH   = ROOT / "app" / "data" / "cooccurrence" / "metadata.json"
OUT_DIR     = ROOT / "evaluation" / "annotation"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-dishes", type=int, default=50,
                        help="Number of query dishes to sample (default 50)")
    parser.add_argument("--n-top", type=int, default=5,
                        help="Ontology-top candidate dishes per query (default 5)")
    parser.add_argument("--n-hard", type=int, default=3,
                        help="Hard-negative candidate dishes per query (default 3)")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def load_idf():
    if not FREQ_PATH.exists() or not META_PATH.exists():
        return {}
    freq = json.loads(FREQ_PATH.read_text(encoding="utf-8"))
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    N = meta.get("total_dishes", 1)
    return {iid: math.log(N / max(1, count)) for iid, count in freq.items()}


def idf_jaccard(set_a, set_b, idf):
    if not set_a or not set_b:
        return 0.0
    inter = set_a & set_b
    union = set_a | set_b
    w_inter = sum(idf.get(i, 1.0) for i in inter)
    w_union = sum(idf.get(i, 1.0) for i in union)
    return w_inter / w_union if w_union > 0 else 0.0


def main():
    args = parse_args()
    rng = random.Random(args.seed)

    print("=== Export Annotation Template — Task 3: Related Dishes ===")

    # Load IDF weights
    idf = load_idf()
    print(f"IDF entries: {len(idf)}")

    # Load test dish IDs
    test_ids = [x for x in (SPLITS_DIR / "test_ids.txt").read_text().splitlines() if x.strip()]
    print(f"Test dishes: {len(test_ids)}")

    # Load dish data
    dishes = {}
    for did in test_ids:
        p = DISHES_DIR / f"{did}.json"
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        dishes[did] = {
            "name_vi": d.get("name_vi", ""),
            "category": d.get("category", "unknown"),
            "ingredient_ids": set(d.get("ingredient_ids", [])),
            "ingredient_names": d.get("ingredient_names_vi", []),
        }
    print(f"Loaded: {len(dishes)} dishes")

    # Load task3 GT (for top-related candidates)
    gt_by_dish = {}
    for line in (DATASETS_DIR / "task3_related_gt.jsonl").read_text().splitlines():
        if line.strip():
            e = json.loads(line)
            gt_by_dish[e["dish_id"]] = e

    # Sample query dishes — need at least n_top related in GT
    eligible = [did for did in test_ids
                if did in gt_by_dish and len(gt_by_dish[did]["related"]) >= args.n_top
                and did in dishes]
    sampled_queries = rng.sample(eligible, min(args.n_dishes, len(eligible)))
    print(f"Sampled query dishes: {len(sampled_queries)}")

    rows = []
    answer_key = []

    for query_id in sampled_queries:
        query = dishes[query_id]
        gt_entry = gt_by_dish[query_id]

        # ── Ontology-top candidates (top n_top from GT)
        top_related = gt_entry["related"][: args.n_top]
        top_ids = {r["dish_id"] for r in top_related}

        # ── Hard negatives: same category, but low IDF-Jaccard with query
        # Pick from dishes that share category but have low ingredient overlap
        same_cat_pool = [
            did for did, d in dishes.items()
            if did != query_id
            and d["category"] == query["category"]
            and did not in top_ids
        ]
        # Score them by IDF-Jaccard (ascending = low overlap = harder negative)
        same_cat_scored = []
        for did in same_cat_pool:
            j = idf_jaccard(query["ingredient_ids"], dishes[did]["ingredient_ids"], idf)
            same_cat_scored.append((did, j))
        same_cat_scored.sort(key=lambda x: x[1])  # lowest overlap first

        # Pick n_hard from the bottom quarter (genuinely hard negatives)
        pool_size = max(args.n_hard * 4, 20)
        hard_pool = [did for did, _ in same_cat_scored[:pool_size]]
        if len(hard_pool) < args.n_hard:
            # Fall back to random from test set (different category)
            random_pool = [did for did in test_ids
                           if did != query_id and did not in top_ids
                           and did in dishes]
            hard_pool += rng.sample(random_pool, min(args.n_hard, len(random_pool)))
        hard_negatives = rng.sample(hard_pool, min(args.n_hard, len(hard_pool)))

        # ── Build candidate list
        candidates = []
        for r in top_related:
            cid = r["dish_id"]
            if cid not in dishes:
                continue
            candidates.append({
                "candidate_id": cid,
                "candidate_name": dishes[cid]["name_vi"],
                "candidate_category": dishes[cid]["category"],
                "candidate_ingredients_preview": ", ".join(dishes[cid]["ingredient_names"][:5]),
                "source": "ontology_top",
                "relatedness_score": r["relatedness"],
            })
        for cid in hard_negatives:
            candidates.append({
                "candidate_id": cid,
                "candidate_name": dishes[cid]["name_vi"],
                "candidate_category": dishes[cid]["category"],
                "candidate_ingredients_preview": ", ".join(dishes[cid]["ingredient_names"][:5]),
                "source": "hard_negative",
                "relatedness_score": None,
            })

        # Shuffle so annotator can't tell which source
        rng.shuffle(candidates)

        for cand in candidates:
            rows.append({
                "query_dish_id":    query_id,
                "query_dish_name":  query["name_vi"],
                "query_category":   query["category"],
                "query_ingredients_preview": ", ".join(query["ingredient_names"][:5]),
                "candidate_dish_id":   cand["candidate_id"],
                "candidate_dish_name": cand["candidate_name"],
                "candidate_category":  cand["candidate_category"],
                "candidate_ingredients_preview": cand["candidate_ingredients_preview"],
                "annotator_1": "",
                "annotator_2": "",
                "notes": "",
            })
            answer_key.append({
                "query_dish_id":    query_id,
                "candidate_dish_id":   cand["candidate_id"],
                "candidate_dish_name": cand["candidate_name"],
                "source": cand["source"],
                "relatedness_score": cand["relatedness_score"],
            })

    # Write CSV
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path  = OUT_DIR / "task3_annotation_template.csv"
    key_path  = OUT_DIR / "task3_annotation_answer_key.json"
    readme_path = OUT_DIR / "README_task3_annotation.md"

    fieldnames = [
        "query_dish_id", "query_dish_name", "query_category",
        "query_ingredients_preview",
        "candidate_dish_id", "candidate_dish_name", "candidate_category",
        "candidate_ingredients_preview",
        "annotator_1", "annotator_2", "notes",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    with open(key_path, "w", encoding="utf-8") as f:
        json.dump(answer_key, f, ensure_ascii=False, indent=2)

    # Write annotation guide
    n_total = len(rows)
    est_min = n_total // 60  # ~1 judgement per second
    readme_path.write_text(
        f"""# Annotation Guide — Task 3: Related Dishes

## Nhiệm vụ

Với mỗi dòng trong file `task3_annotation_template.csv`, đánh giá:

> **Món [{"{candidate_dish_name}"}] có LIÊN QUAN đến món [{"{query_dish_name}"}] không?**

Điền vào cột `annotator_1` (hoặc `annotator_2`):
- `1` = Có — hai món này liên quan (nguyên liệu tương tự, cùng phong cách, có thể thay thế nhau)
- `0` = Không — hai món không liên quan hoặc rất khác nhau

## Hướng dẫn chi tiết

**Hai món LIÊN QUAN khi:**
- Dùng nhiều nguyên liệu chính giống nhau (VD: gà + sả + nước dừa)
- Cùng phong cách chế biến (VD: cả hai đều là lẩu/canh/kho)
- Có thể thay thế cho nhau trong một bữa ăn

**Hai món KHÔNG LIÊN QUAN khi:**
- Nguyên liệu chính hoàn toàn khác
- Phong cách ẩm thực khác nhau (VD: một món miền Bắc, một món Tây)
- Không có điểm chung về nguyên liệu hoặc cách nấu

## Ví dụ

| Query | Candidate | Label | Lý do |
|---|---|---|---|
| Lẩu gà nước dừa | Lẩu gà lá giang | **1** | Cùng là lẩu gà, nhiều nguyên liệu chung |
| Lẩu gà nước dừa | Gà hầm sả | **1** | Cùng dùng gà + sả, phong cách gần |
| Lẩu gà nước dừa | Bún bò Huế | **0** | Khác nguyên liệu chính (bò vs gà), khác phong cách |
| Phở bò | Bún bò Huế | **1** | Cùng dùng bò, cùng là món nước |
| Phở bò | Bánh mì | **0** | Khác hoàn toàn |

## Cột `query_ingredients_preview` và `candidate_ingredients_preview`

Cột này hiển thị 5 nguyên liệu đầu tiên của món — giúp bạn đánh giá nhanh mức độ tương đồng.
Không cần phải biết công thức đầy đủ.

## Lưu ý

- Hai annotator làm **ĐỘC LẬP**, không trao đổi kết quả cho đến khi xong
- Nếu không chắc, ghi lý do vào cột `notes`
- Ước tính: {n_total} judgements · ~{est_min}–{est_min + 10} phút

## Files

- `task3_annotation_template.csv` — file cần điền
- Gửi lại file sau khi hoàn thành
""",
        encoding="utf-8"
    )

    n_dishes = len(sampled_queries)
    n_top_total  = sum(1 for k in answer_key if k["source"] == "ontology_top")
    n_hard_total = sum(1 for k in answer_key if k["source"] == "hard_negative")

    print(f"\n  Query dishes sampled : {n_dishes}")
    print(f"  Total judgements     : {n_total}  ({n_top_total} ontology-top + {n_hard_total} hard-neg, shuffled)")
    print(f"  Per annotator        : {n_total} judgements (~{est_min}–{est_min + 10} min)")
    print(f"\nWritten:")
    print(f"  {csv_path}")
    print(f"  {key_path}")
    print(f"  {readme_path}")
    print("\nDone.")


if __name__ == "__main__":
    main()
