#!/usr/bin/env python3
"""
Export annotation template for Task 2 — Flavor-enhancing Ingredients.

Design: Blind annotation to avoid bias.
  - For each dish: 5 PMI-selected candidates + 5 random non-core candidates (shuffled)
  - Annotator does NOT know which are PMI-selected vs random
  - This allows honest precision measurement of PMI

Reads:
    data/splits/test_ids.txt
    processed/dishes/*.json
    evaluation/data/datasets/task2_flavor_gt.jsonl
    app/data/knowledge_base/ingredient_knowledge_base.json

Writes:
    evaluation/annotation/annotation_template.csv     — for annotators (no PMI scores)
    evaluation/annotation/annotation_answer_key.json  — internal key (PMI source labels)

Usage:
    python scripts/export_annotation_template.py
    python scripts/export_annotation_template.py --n-dishes 50 --seed 42
"""

import argparse
import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DISHES_DIR = ROOT / "processed" / "dishes"
SPLITS_DIR = ROOT / "data" / "splits"
DATASETS_DIR = ROOT / "evaluation" / "data" / "datasets"
IKB_PATH = ROOT / "app" / "data" / "knowledge_base" / "ingredient_knowledge_base.json"
OUT_DIR = ROOT / "evaluation" / "annotation"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-dishes", type=int, default=50)
    parser.add_argument("--n-pmi", type=int, default=5, help="PMI candidates per dish")
    parser.add_argument("--n-random", type=int, default=5, help="Random candidates per dish")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main():
    args = parse_args()
    rng = random.Random(args.seed)

    print("=== Export Annotation Template ===")

    # Load ingredient name map
    ikb = json.loads(IKB_PATH.read_text(encoding="utf-8"))
    id_to_name = {e["id"]: e.get("name_vi", "") for e in ikb if e.get("id")}

    # Load task2 ground truth (PMI-based)
    gt_by_dish = {}
    for line in (DATASETS_DIR / "task2_flavor_gt.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            entry = json.loads(line)
            gt_by_dish[entry["dish_id"]] = entry

    # Filter: only dishes with at least n_pmi PMI candidates
    eligible = [
        did for did, entry in gt_by_dish.items()
        if len(entry.get("flavor_enhancing", [])) >= args.n_pmi
    ]
    print(f"Eligible dishes (≥{args.n_pmi} PMI candidates): {len(eligible)}")

    sampled = rng.sample(eligible, min(args.n_dishes, len(eligible)))
    print(f"Sampled: {len(sampled)} dishes")

    rows = []          # CSV rows for annotators
    answer_key = []    # Internal: which are PMI vs random

    for dish_id in sampled:
        entry = gt_by_dish[dish_id]
        dish_path = DISHES_DIR / f"{dish_id}.json"
        dish = json.loads(dish_path.read_text(encoding="utf-8"))

        dish_name = entry["dish_name"]
        category = entry.get("category", "")
        core_names = ", ".join(entry.get("core_ingredient_names", []))
        all_ids = set(dish.get("ingredient_ids", []))
        core_ids = set(entry.get("core_ingredient_ids", []))

        # PMI candidates — take top n_pmi
        pmi_candidates = entry["flavor_enhancing"][: args.n_pmi]
        pmi_ids = {c["ingredient_id"] for c in pmi_candidates}

        # Random candidates — non-core, not in PMI candidates
        non_core_pool = [
            iid for iid in all_ids
            if iid not in core_ids and iid not in pmi_ids
        ]
        random_candidates = rng.sample(
            non_core_pool, min(args.n_random, len(non_core_pool))
        )

        # Build candidate list with source label (hidden from annotator)
        candidates = []
        for c in pmi_candidates:
            candidates.append({
                "ingredient_id": c["ingredient_id"],
                "name_vi": c["name_vi"] or id_to_name.get(c["ingredient_id"], ""),
                "mean_pmi": c["mean_pmi"],
                "source": "pmi",
            })
        for iid in random_candidates:
            candidates.append({
                "ingredient_id": iid,
                "name_vi": id_to_name.get(iid, ""),
                "mean_pmi": None,
                "source": "random",
            })

        # Shuffle so annotator can't tell PMI vs random
        rng.shuffle(candidates)

        for cand in candidates:
            rows.append({
                "dish_id": dish_id,
                "dish_name": dish_name,
                "category": category,
                "core_ingredients": core_names,
                "candidate_id": cand["ingredient_id"],
                "candidate_name": cand["name_vi"],
                "annotator_1": "",   # to be filled
                "annotator_2": "",   # to be filled
                "notes": "",
            })
            answer_key.append({
                "dish_id": dish_id,
                "candidate_id": cand["ingredient_id"],
                "candidate_name": cand["name_vi"],
                "source": cand["source"],
                "mean_pmi": cand["mean_pmi"],
            })

    # Write CSV
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUT_DIR / "annotation_template.csv"
    key_path = OUT_DIR / "annotation_answer_key.json"
    readme_path = OUT_DIR / "README_annotation.md"

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "dish_id", "dish_name", "category", "core_ingredients",
            "candidate_id", "candidate_name",
            "annotator_1", "annotator_2", "notes"
        ])
        writer.writeheader()
        writer.writerows(rows)

    with open(key_path, "w", encoding="utf-8") as f:
        json.dump(answer_key, f, ensure_ascii=False, indent=2)

    # Write annotation guide
    readme_path.write_text(
        """# Annotation Guide — Flavor-enhancing Ingredients

## Nhiệm vụ

Với mỗi dòng trong file `annotation_template.csv`, đánh giá:

> **Nguyên liệu [candidate_name] có làm TĂNG HƯƠNG VỊ của món [dish_name] không?**

Điền vào cột `annotator_1` (hoặc `annotator_2`):
- `1` = Có — nguyên liệu này thực sự bổ sung/tăng hương vị cho món
- `0` = Không — nguyên liệu này không liên quan hoặc không phù hợp

## Hướng dẫn chi tiết

**Flavor-enhancing** là những nguyên liệu:
- Thêm vào để tăng mùi thơm, vị đặc trưng (ví dụ: thì là với cá, quế với phở)
- Thường là gia vị phụ, rau thơm, nước chấm kèm
- KHÔNG phải thành phần chính đã có trong cột `core_ingredients`

**Ví dụ:**
- Món: Phở bò | Core: thịt bò, bánh phở, hành | Candidate: quế → **1** (tăng hương vị đặc trưng)
- Món: Phở bò | Core: thịt bò, bánh phở, hành | Candidate: đường → **0** (không thêm hương vị)
- Món: Cá kho | Core: cá, nước mắm | Candidate: gừng → **1** (khử tanh, tăng hương)
- Món: Cá kho | Core: cá, nước mắm | Candidate: bột mì → **0** (không liên quan)

## Lưu ý

- Không cần tra cứu công thức — đánh giá theo hiểu biết ẩm thực thực tế
- Nếu không chắc, để trống cột `notes` để ghi lý do
- Mỗi dish_id có thể xuất hiện nhiều lần (nhiều candidate khác nhau)
- Hai annotator làm ĐỘC LẬP, không trao đổi kết quả cho đến khi xong

## File

- `annotation_template.csv` — file cần điền
- Gửi lại file sau khi hoàn thành
""",
        encoding="utf-8"
    )

    n_dishes = len(sampled)
    n_rows = len(rows)
    n_pmi_total = sum(1 for k in answer_key if k["source"] == "pmi")
    n_random_total = sum(1 for k in answer_key if k["source"] == "random")

    print(f"\n  Dishes sampled    : {n_dishes}")
    print(f"  Total judgements  : {n_rows} ({n_pmi_total} PMI + {n_random_total} random, shuffled)")
    print(f"  Per annotator     : {n_rows} judgements (~{n_rows // 50} min estimated)")
    print(f"\nWritten:")
    print(f"  {csv_path}       ← send to annotators")
    print(f"  {key_path}  ← keep internal (has PMI labels)")
    print(f"  {readme_path}")
    print("\nDone.")


if __name__ == "__main__":
    main()
