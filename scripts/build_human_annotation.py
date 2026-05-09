#!/usr/bin/env python3
"""Generate human annotation samples for Task 1 and Task 2 to validate LLM/rule-based ground truth.

Task 1 (Class-Based Dish Retrieval):
  - Currently uses rule-based FoodOntology API labels
  - Sample: 50 queries × 10 candidates (5 positive GT, 5 negative) = 500 items
  - Annotators label: relevant (1) or not relevant (0)
  - Purpose: measure agreement between rule-based labels and human judgment

Task 2 (Related-Dish Recommendation, previously Task 3):
  - Currently uses 3-LLM-judge mean score as ground truth
  - Sample: 50 anchors × 6 candidates (stratified by LLM mean score) = 300 items
  - Annotators score: 0/1/2 (same scale as LLM judges)
  - Purpose: measure correlation between LLM-judge mean scores and human scores

Usage:
    python scripts/build_human_annotation.py

Outputs:
    evaluation/annotation/task1_human_annotation.csv
    evaluation/annotation/task2_human_annotation.csv
    evaluation/annotation/README_human_annotation.md
"""
import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DKB = ROOT / "app" / "data" / "knowledge_base" / "dish_knowledge_base.json"
TASK1_QUERIES = ROOT / "evaluation" / "data" / "task1_class_queries.jsonl"
TASK2_JUDGES = ROOT / "evaluation" / "outputs" / "llm_judge_task3_3judges.json"
OUT_DIR = ROOT / "evaluation" / "annotation"

# Sampling parameters
N_TASK1_QUERIES = 50
N_TASK1_POS_PER_Q = 5      # positive candidates per query
N_TASK1_NEG_PER_Q = 5      # negative (random) candidates per query
N_TASK2_ANCHORS = 50
N_TASK2_CANDIDATES = 6     # stratified: 2 per score bucket (low/mid/high)

SEED = 42


def load_dish_kb():
    """Load dish KB, index by id."""
    with open(DKB, "r", encoding="utf-8") as f:
        kb = json.load(f)
    return {d["id"]: d for d in kb}


def ingredient_preview(dish, k=5):
    """Return first k ingredient names as comma-separated string."""
    ings = dish.get("ingredients", [])
    names = [i.get("name_vi", "") for i in ings[:k] if i.get("name_vi")]
    return ", ".join(names)


def build_task1_samples(dish_kb):
    """Sample 50 queries × 10 candidates (5 positive from GT, 5 negative)."""
    random.seed(SEED)

    # Load Task 1 queries
    queries = []
    with open(TASK1_QUERIES, "r", encoding="utf-8") as f:
        for line in f:
            queries.append(json.loads(line))

    # Stratify: pick roughly equal per type
    by_type = {}
    for q in queries:
        by_type.setdefault(q["type"], []).append(q)

    # Sample 12-13 per type (50 total, 4 types)
    per_type = N_TASK1_QUERIES // len(by_type)
    remainder = N_TASK1_QUERIES - per_type * len(by_type)
    sampled_queries = []
    types_sorted = sorted(by_type.keys())
    for i, t in enumerate(types_sorted):
        n = per_type + (1 if i < remainder else 0)
        pool = by_type[t]
        sampled_queries.extend(random.sample(pool, min(n, len(pool))))

    all_dish_ids = list(dish_kb.keys())

    rows = []
    for q in sampled_queries:
        gt_positives = q.get("gt_dish_ids", [])
        # Pick 5 positive candidates
        pos_sample = random.sample(gt_positives, min(N_TASK1_POS_PER_Q, len(gt_positives)))
        # Pick 5 negatives (not in GT)
        gt_set = set(gt_positives)
        neg_pool = [d for d in all_dish_ids if d not in gt_set]
        neg_sample = random.sample(neg_pool, N_TASK1_NEG_PER_Q)

        # Shuffle so annotators don't know which is which
        candidates = [(did, "pos") for did in pos_sample] + [(did, "neg") for did in neg_sample]
        random.shuffle(candidates)

        for cand_id, cand_label in candidates:
            cand = dish_kb.get(cand_id, {})
            rows.append({
                "query_id": q["query_id"],
                "query": q["query"],
                "query_type": q["type"],
                "classes_positive": ",".join(q.get("classes_positive", [])),
                "classes_negative": ",".join(q.get("classes_negative", [])),
                "cooking_method": q.get("cooking_method") or "",
                "candidate_dish_id": cand_id,
                "candidate_dish_name": cand.get("name_vi", ""),
                "candidate_category": cand.get("category", ""),
                "candidate_ingredients_preview": ingredient_preview(cand),
                "rule_label": 1 if cand_label == "pos" else 0,  # hidden answer key
                "annotator_1": "",
                "annotator_2": "",
                "notes": "",
            })
    return rows


def build_task2_samples(dish_kb):
    """Sample 50 anchors × 6 candidates stratified by LLM-judge mean score."""
    random.seed(SEED)

    with open(TASK2_JUDGES, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Group items by anchor
    by_anchor = {}
    for item in data["items"]:
        by_anchor.setdefault(item["query_dish_id"], []).append(item)

    # Sample 50 anchors
    anchor_ids = list(by_anchor.keys())
    sampled_anchors = random.sample(anchor_ids, min(N_TASK2_ANCHORS, len(anchor_ids)))

    rows = []
    for aid in sampled_anchors:
        items = by_anchor[aid]
        # Stratify by new_mean_3j: low (<0.67), mid (0.67–1.33), high (>=1.33)
        low = [it for it in items if it["new_mean_3j"] < 0.67]
        mid = [it for it in items if 0.67 <= it["new_mean_3j"] < 1.34]
        high = [it for it in items if it["new_mean_3j"] >= 1.34]

        # 2 from each bucket, fallback to mid if a bucket empty
        picked = []
        for bucket in [low, mid, high]:
            n_pick = min(2, len(bucket))
            if n_pick > 0:
                picked.extend(random.sample(bucket, n_pick))
        # Fill up to N_TASK2_CANDIDATES if short
        remaining_pool = [it for it in items if it not in picked]
        while len(picked) < N_TASK2_CANDIDATES and remaining_pool:
            picked.append(random.choice(remaining_pool))
            remaining_pool = [it for it in items if it not in picked]

        anchor = dish_kb.get(aid, {})
        for it in picked:
            cand = dish_kb.get(it["candidate_dish_id"], {})
            rows.append({
                "anchor_dish_id": aid,
                "anchor_dish_name": anchor.get("name_vi", ""),
                "anchor_category": anchor.get("category", ""),
                "anchor_ingredients_preview": ingredient_preview(anchor),
                "candidate_dish_id": it["candidate_dish_id"],
                "candidate_dish_name": cand.get("name_vi", ""),
                "candidate_category": cand.get("category", ""),
                "candidate_ingredients_preview": ingredient_preview(cand),
                "llm_mean_score": round(it["new_mean_3j"], 3),  # hidden answer key
                "annotator_1": "",
                "annotator_2": "",
                "notes": "",
            })
    return rows


def write_csv(rows, path, fieldnames):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def write_readme(task1_n, task2_n):
    content = f"""# Hướng dẫn gán nhãn — Human Annotation Validation

Mục đích: **Xác nhận chất lượng ground truth** cho Task 1 (rule-based labels) và Task 2 (LLM-judge labels) bằng con người. Kết quả dùng để báo cáo agreement giữa human và hệ thống tự động trong paper.

---

## Task 1 — Class-Based Dish Retrieval

**File:** `task1_human_annotation.csv`  ({task1_n} dòng, ~2 annotators × {task1_n} = {task1_n*2} judgements)
**Thời gian ước tính:** 40–60 phút / annotator

### Câu hỏi gán nhãn

Với mỗi dòng: **Món `{{candidate_dish_name}}` có khớp với truy vấn `{{query}}` không?**

- `1` = Có khớp (món chứa đúng nhóm nguyên liệu / phương pháp nấu được yêu cầu)
- `0` = Không khớp

### Cột tham khảo

- `query`: truy vấn người dùng (VD: "món nấm ngon", "các món không hải sản")
- `query_type`: single_class / multi_class / negation / cooking_method
- `classes_positive`: nhóm nguyên liệu phải có (VD: Mushroom)
- `classes_negative`: nhóm nguyên liệu không được có (VD: Seafood)
- `cooking_method`: phương pháp nấu bắt buộc (nếu có)
- `candidate_dish_name`, `candidate_ingredients_preview`: thông tin món ứng viên

### Điền vào cột `annotator_1` (annotator 1) hoặc `annotator_2` (annotator 2)

### Ví dụ

| Query | Candidate | Label | Lý do |
|---|---|---|---|
| món nấm ngon | Nấm đùi gà xào tỏi | **1** | Có nấm (nhóm Mushroom) |
| món nấm ngon | Phở bò | **0** | Không có nấm |
| món không hải sản | Thịt kho tàu | **1** | Không chứa hải sản |
| món không hải sản | Canh chua cá | **0** | Có cá (Seafood) — vi phạm negation |
| món xào | Rau muống xào tỏi | **1** | Đúng phương pháp xào |
| món xào | Canh bí đỏ | **0** | Phương pháp nấu (canh), không phải xào |

---

## Task 2 — Related-Dish Recommendation (trước đây là Task 3)

**File:** `task2_human_annotation.csv`  ({task2_n} dòng, ~2 annotators × {task2_n} = {task2_n*2} judgements)
**Thời gian ước tính:** 30–45 phút / annotator

### Câu hỏi gán nhãn

Với mỗi dòng: **Món `{{candidate_dish_name}}` liên quan đến món `{{anchor_dish_name}}` ở mức nào?**

- `0` = Không liên quan — khác nguyên liệu chính, khác phong cách nấu
- `1` = Liên quan — có điểm chung về nguyên liệu hoặc phong cách
- `2` = Rất liên quan — nhiều nguyên liệu chung, cùng phong cách, có thể thay thế nhau

(Thang điểm này giống với LLM judges dùng trong paper để có thể so sánh trực tiếp.)

### Ví dụ

| Anchor | Candidate | Score | Lý do |
|---|---|---|---|
| Lẩu gà nước dừa | Lẩu gà lá giang | **2** | Cùng là lẩu gà, nhiều nguyên liệu chung |
| Lẩu gà nước dừa | Gà hầm sả | **1** | Cùng dùng gà+sả, nhưng khác kiểu nấu (lẩu vs hầm) |
| Lẩu gà nước dừa | Bún bò Huế | **0** | Khác nguyên liệu chính, khác phong cách |
| Phở bò | Bún bò Huế | **1** | Cùng dùng bò, cùng món nước, nhưng gia vị khác |
| Phở bò | Phở bò tái nạm | **2** | Gần như cùng món |
| Phở bò | Bánh mì | **0** | Khác hoàn toàn |

### Điền vào cột `annotator_1` hoặc `annotator_2`

---

## Quy trình & Nguyên tắc

1. **Hai annotators làm độc lập**, không trao đổi cho đến khi xong cả 2 files
2. **Không nhìn cột `rule_label` / `llm_mean_score`** — đó là answer key ẩn, dùng để so sánh sau
3. Nếu không chắc, viết lý do vào cột `notes`
4. **Không được dùng công cụ bên ngoài** (Google, ChatGPT) — chỉ dựa trên kiến thức ẩm thực Việt Nam của bạn

## Output sau khi gán nhãn

Sau khi cả 2 annotators hoàn thành, sẽ chạy script thống kê để tính:

- **Human-vs-system agreement** (% trùng khớp nhãn)
- **Cohen's kappa** giữa 2 annotators (độ tin cậy internal)
- **Spearman correlation** giữa human score và LLM-judge mean (Task 2)
- **Precision/Recall** của rule-based labels so với human (Task 1)

Kết quả sẽ được thêm vào Section 5.3 (Evaluation Protocol) của paper để tăng độ thuyết phục.
"""
    with open(OUT_DIR / "README_human_annotation.md", "w", encoding="utf-8") as f:
        f.write(content)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Loading dish KB from {DKB.name} ...")
    dish_kb = load_dish_kb()
    print(f"  {len(dish_kb)} dishes")

    print("Building Task 1 samples (class-based retrieval) ...")
    task1_rows = build_task1_samples(dish_kb)
    task1_fields = [
        "query_id", "query", "query_type",
        "classes_positive", "classes_negative", "cooking_method",
        "candidate_dish_id", "candidate_dish_name", "candidate_category",
        "candidate_ingredients_preview",
        "rule_label",  # hidden answer key
        "annotator_1", "annotator_2", "notes",
    ]
    task1_path = OUT_DIR / "task1_human_annotation.csv"
    write_csv(task1_rows, task1_path, task1_fields)
    print(f"  wrote {len(task1_rows)} rows → {task1_path.name}")

    print("Building Task 2 samples (related-dish recommendation) ...")
    task2_rows = build_task2_samples(dish_kb)
    task2_fields = [
        "anchor_dish_id", "anchor_dish_name", "anchor_category",
        "anchor_ingredients_preview",
        "candidate_dish_id", "candidate_dish_name", "candidate_category",
        "candidate_ingredients_preview",
        "llm_mean_score",  # hidden answer key
        "annotator_1", "annotator_2", "notes",
    ]
    task2_path = OUT_DIR / "task2_human_annotation.csv"
    write_csv(task2_rows, task2_path, task2_fields)
    print(f"  wrote {len(task2_rows)} rows → {task2_path.name}")

    print("Writing README ...")
    write_readme(len(task1_rows), len(task2_rows))
    print(f"  wrote README_human_annotation.md")

    print("\nDone. Files in:", OUT_DIR)


if __name__ == "__main__":
    main()
