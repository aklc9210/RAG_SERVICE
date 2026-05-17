#!/usr/bin/env python3
"""Generate 200 additional annotation pairs for Task 3 human validation.

Samples from task3_diverse_judged.json, excluding the 300 pairs already
in task2_human_annotation.csv. Uses stratified sampling across LLM score
ranges to ensure diversity (same strategy as original 300).

Output: evaluation/annotation/task3_annotation_extra_200.csv
"""
import csv
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── Load existing 300 annotated pairs ────────────────────────────

EXISTING_CSV = ROOT / "evaluation" / "annotation" / "task2_human_annotation.csv"
existing_pairs = set()
with open(EXISTING_CSV, encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        pair_key = (row["anchor_dish_id"], row["candidate_dish_id"])
        existing_pairs.add(pair_key)

print(f"Existing annotated pairs: {len(existing_pairs)}")

# ── Load all judged pairs ────────────────────────────────────────

JUDGE_PATH = ROOT / "evaluation" / "outputs" / "task3_diverse_judged.json"
judges_data = json.loads(JUDGE_PATH.read_text("utf-8"))

# Filter out existing pairs and pairs with None scores
available_pairs = []
for item in judges_data["results"]:
    if item["mean_score"] is None:
        continue
    pair_key = (item["anchor_id"], item["candidate_id"])
    if pair_key in existing_pairs:
        continue
    available_pairs.append(item)

print(f"Available pairs (not yet annotated): {len(available_pairs)}")

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

# ── Stratified sampling: ensure score diversity ──────────────────
# Bins: [0, 0.5), [0.5, 1.0), [1.0, 1.5), [1.5, 2.0]
# This ensures we get pairs across the full relatedness spectrum

bins = {
    "low_0_0.5": [],      # clearly unrelated
    "mid_0.5_1.0": [],    # borderline
    "high_1.0_1.5": [],   # somewhat related
    "very_high_1.5_2.0": []  # very related
}

for item in available_pairs:
    score = item["mean_score"]
    if score < 0.5:
        bins["low_0_0.5"].append(item)
    elif score < 1.0:
        bins["mid_0.5_1.0"].append(item)
    elif score < 1.5:
        bins["high_1.0_1.5"].append(item)
    else:
        bins["very_high_1.5_2.0"].append(item)

print("\nScore distribution of available pairs:")
for bin_name, items in bins.items():
    print(f"  {bin_name}: {len(items)}")

# Target: 200 pairs, distributed proportionally (same ratio as available)
total_available = len(available_pairs)
TARGET = 200

random.seed(42)
selected = []

for bin_name, items in bins.items():
    # Proportional allocation
    n_select = max(1, round(TARGET * len(items) / total_available))
    n_select = min(n_select, len(items))
    sampled = random.sample(items, n_select)
    selected.extend(sampled)
    print(f"  Selected from {bin_name}: {n_select}")

# If we have more than 200, trim; if less, add more from largest bin
if len(selected) > TARGET:
    random.shuffle(selected)
    selected = selected[:TARGET]
elif len(selected) < TARGET:
    # Add more from the pool
    selected_keys = {(s["anchor_id"], s["candidate_id"]) for s in selected}
    remaining = [p for p in available_pairs
                 if (p["anchor_id"], p["candidate_id"]) not in selected_keys]
    extra = random.sample(remaining, TARGET - len(selected))
    selected.extend(extra)

print(f"\nTotal selected: {len(selected)}")

# Shuffle for annotation (avoid annotator bias from ordering)
random.shuffle(selected)

# ── Write CSV ────────────────────────────────────────────────────

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

    for item in selected:
        a_name, a_cat, a_preview = get_dish_info(item["anchor_id"])
        c_name, c_cat, c_preview = get_dish_info(item["candidate_id"])

        writer.writerow([
            item["anchor_id"], a_name, a_cat, a_preview,
            item["candidate_id"], c_name, c_cat, c_preview,
            round(item["mean_score"], 3),
            "", "", ""  # empty for annotators to fill
        ])

print(f"\n✓ Saved {len(selected)} pairs → {OUTPUT_CSV}")
print(f"\nScore distribution of selected pairs:")
score_counts = {"0-0.5": 0, "0.5-1.0": 0, "1.0-1.5": 0, "1.5-2.0": 0}
for item in selected:
    s = item["mean_score"]
    if s < 0.5:
        score_counts["0-0.5"] += 1
    elif s < 1.0:
        score_counts["0.5-1.0"] += 1
    elif s < 1.5:
        score_counts["1.0-1.5"] += 1
    else:
        score_counts["1.5-2.0"] += 1
for k, v in score_counts.items():
    print(f"  LLM score {k}: {v} pairs ({v/len(selected)*100:.0f}%)")
