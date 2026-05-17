#!/usr/bin/env python3
"""Generate additional annotation pairs for Task 3 human validation.

Follows the SAME structure as the original 300-pair annotation:
  - Each anchor has exactly 6 candidates
  - Candidates are selected to cover diverse score ranges (same as original)
  - Anchors are stratified across dish categories

Original: 50 anchors × 6 candidates = 300 pairs
New:      34 anchors × 6 candidates = 204 pairs
Total:    84 anchors × 6 candidates = 504 pairs (≈500 target)

Output: evaluation/annotation/task3_annotation_extra_200.csv
"""
import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── Load existing annotated anchors (to exclude) ─────────────────

EXISTING_CSV = ROOT / "evaluation" / "annotation" / "task2_human_annotation.csv"
existing_anchors = set()
with open(EXISTING_CSV, encoding="utf-8") as f:
    for row in csv.DictReader(f):
        existing_anchors.add(row["anchor_dish_id"])

print(f"Existing annotated anchors: {len(existing_anchors)}")

# ── Load all judged pairs ────────────────────────────────────────

JUDGE_PATH = ROOT / "evaluation" / "outputs" / "task3_diverse_judged.json"
judges_data = json.loads(JUDGE_PATH.read_text("utf-8"))

# Group by anchor
anchor_candidates = defaultdict(list)
for item in judges_data["results"]:
    if item["mean_score"] is None:
        continue
    anchor_candidates[item["anchor_id"]].append(item)

# Filter: only anchors NOT already annotated, with >=6 candidates
available_anchors = {a: items for a, items in anchor_candidates.items()
                     if a not in existing_anchors and len(items) >= 6}

print(f"Available anchors (not yet annotated, >=6 candidates): {len(available_anchors)}")

# ── Load dish KB for metadata ────────────────────────────────────

DISH_KB_PATH = ROOT / "app" / "data" / "knowledge_base" / "dish_knowledge_base.json"
dish_kb = {d["id"]: d for d in json.loads(DISH_KB_PATH.read_text("utf-8"))}

def get_dish_info(dish_id):
    d = dish_kb.get(dish_id, {})
    name = d.get("name_vi", dish_id)
    category = d.get("category", "")
    ings = d.get("ingredients", [])
    preview = ", ".join(i.get("name_vi", "") for i in ings[:5])
    return name, category, preview

# ── Stratified anchor selection (by category) ────────────────────

# Group available anchors by category
cat_to_anchors = defaultdict(list)
for aid in available_anchors:
    cat = dish_kb.get(aid, {}).get("category", "unknown")
    cat_to_anchors[cat].append(aid)

print(f"\nCategories with available anchors: {len(cat_to_anchors)}")
for cat, aids in sorted(cat_to_anchors.items(), key=lambda x: -len(x[1])):
    print(f"  {cat}: {len(aids)} anchors")

# Select 34 anchors, stratified across categories
TARGET_ANCHORS = 34
random.seed(42)

selected_anchors = []
# Round-robin across categories
cats = sorted(cat_to_anchors.keys(), key=lambda c: -len(cat_to_anchors[c]))
cat_pools = {c: list(aids) for c, aids in cat_to_anchors.items()}
for pool in cat_pools.values():
    random.shuffle(pool)

idx = 0
while len(selected_anchors) < TARGET_ANCHORS:
    cat = cats[idx % len(cats)]
    if cat_pools[cat]:
        selected_anchors.append(cat_pools[cat].pop())
    idx += 1
    # Safety: if all pools exhausted
    if all(len(p) == 0 for p in cat_pools.values()):
        break

print(f"\nSelected {len(selected_anchors)} anchors")

# ── For each anchor, select 6 diverse candidates ────────────────
# Strategy (same as original 300):
#   - 2 from high LLM score (>=1.5) — easy positives
#   - 2 from medium LLM score (0.5-1.5) — borderline
#   - 2 from low LLM score (<0.5) — negatives
# If a bin doesn't have enough, fill from the next available bin

def select_6_candidates(anchor_id):
    """Select 6 diverse candidates for an anchor."""
    items = available_anchors[anchor_id]
    
    high = [it for it in items if it["mean_score"] >= 1.5]
    mid = [it for it in items if 0.5 <= it["mean_score"] < 1.5]
    low = [it for it in items if it["mean_score"] < 0.5]
    
    random.shuffle(high)
    random.shuffle(mid)
    random.shuffle(low)
    
    selected = []
    # Target: 2 high, 2 mid, 2 low
    selected.extend(high[:2])
    selected.extend(mid[:2])
    selected.extend(low[:2])
    
    # If not enough in some bin, fill from others
    if len(selected) < 6:
        remaining = [it for it in items if it not in selected]
        random.shuffle(remaining)
        selected.extend(remaining[:6 - len(selected)])
    
    return selected[:6]

# ── Build final pairs ────────────────────────────────────────────

all_pairs = []
for anchor_id in selected_anchors:
    candidates = select_6_candidates(anchor_id)
    all_pairs.extend(candidates)

print(f"Total pairs: {len(all_pairs)}")

# Verify score distribution
score_dist = {"high (>=1.5)": 0, "mid (0.5-1.5)": 0, "low (<0.5)": 0}
for item in all_pairs:
    s = item["mean_score"]
    if s >= 1.5:
        score_dist["high (>=1.5)"] += 1
    elif s >= 0.5:
        score_dist["mid (0.5-1.5)"] += 1
    else:
        score_dist["low (<0.5)"] += 1

print(f"\nScore distribution:")
for k, v in score_dist.items():
    print(f"  {k}: {v} ({v/len(all_pairs)*100:.0f}%)")

# ── Write CSV (grouped by anchor, 6 per anchor) ─────────────────

OUTPUT_CSV = ROOT / "evaluation" / "annotation" / "task3_annotation_extra_200.csv"

with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "anchor_dish_id", "anchor_dish_name", "anchor_category",
        "anchor_ingredients_preview",
        "candidate_dish_id", "candidate_dish_name", "candidate_category",
        "candidate_ingredients_preview",
        "llm_mean_score", "annotator_1", "annotator_2", "notes"
    ])

    for item in all_pairs:
        a_name, a_cat, a_preview = get_dish_info(item["anchor_id"])
        c_name, c_cat, c_preview = get_dish_info(item["candidate_id"])

        writer.writerow([
            item["anchor_id"], a_name, a_cat, a_preview,
            item["candidate_id"], c_name, c_cat, c_preview,
            round(item["mean_score"], 3),
            "", "", ""
        ])

print(f"\n✓ Saved {len(all_pairs)} pairs ({len(selected_anchors)} anchors × 6) → {OUTPUT_CSV}")

# Verify grouping
import csv as csv2
with open(OUTPUT_CSV, encoding="utf-8") as f:
    reader = csv2.DictReader(f)
    from collections import Counter
    anchor_counts = Counter(r["anchor_dish_id"] for r in reader)
    assert all(v == 6 for v in anchor_counts.values()), "Not all anchors have 6 candidates!"
    print(f"✓ Verified: all {len(anchor_counts)} anchors have exactly 6 candidates")
