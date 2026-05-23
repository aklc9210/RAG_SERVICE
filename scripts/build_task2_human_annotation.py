#!/usr/bin/env python3
"""Generate human annotation template: 25 anchors × 20 candidates = 500 pairs.

Selects 25 anchors via stratified sampling across categories from the
LLM-judged data (which already has 20 diverse candidates per anchor).

Usage:
    python3 scripts/build_task2_human_annotation.py
"""
import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

JUDGE_PATH = ROOT / "evaluation" / "outputs" / "task3_diverse_judged.json"
DKB_PATH = ROOT / "app" / "data" / "knowledge_base" / "dish_knowledge_base.json"
OUT_PATH = ROOT / "evaluation" / "annotation" / "task2_human_annotation_v2.csv"

N_ANCHORS = 25

def main():
    random.seed(42)
    judges = json.loads(JUDGE_PATH.read_text("utf-8"))
    dish_kb = {d["id"]: d for d in json.loads(DKB_PATH.read_text("utf-8"))}

    # Group by anchor
    anchor_cands = defaultdict(list)
    for r in judges["results"]:
        anchor_cands[r["anchor_id"]].append(r)

    # Stratified sampling: pick anchors across categories
    cat_anchors = defaultdict(list)
    for a in anchor_cands:
        cat = dish_kb.get(a, {}).get("category", "unknown")
        cat_anchors[cat].append(a)

    # Sort categories by size, round-robin pick
    selected = []
    cats = sorted(cat_anchors.keys(), key=lambda c: -len(cat_anchors[c]))
    for cat in cats:
        random.shuffle(cat_anchors[cat])

    idx = 0
    while len(selected) < N_ANCHORS:
        cat = cats[idx % len(cats)]
        if cat_anchors[cat]:
            selected.append(cat_anchors[cat].pop(0))
        idx += 1
        if idx > N_ANCHORS * 10:
            break

    print(f"Selected {len(selected)} anchors from {len(set(dish_kb.get(a, {}).get('category') for a in selected))} categories")

    # Build CSV rows
    rows = []
    for anchor_id in selected:
        a_dish = dish_kb.get(anchor_id, {})
        a_ings = [i.get("name_vi", "") for i in a_dish.get("ingredients", [])[:5]]
        for r in anchor_cands[anchor_id]:
            c_id = r["candidate_id"]
            c_dish = dish_kb.get(c_id, {})
            c_ings = [i.get("name_vi", "") for i in c_dish.get("ingredients", [])[:5]]
            rows.append({
                "anchor_dish_id": anchor_id,
                "anchor_dish_name": a_dish.get("name_vi", ""),
                "anchor_category": a_dish.get("category", ""),
                "anchor_ingredients_preview": ", ".join(a_ings),
                "candidate_dish_id": c_id,
                "candidate_dish_name": c_dish.get("name_vi", ""),
                "candidate_category": c_dish.get("category", ""),
                "candidate_ingredients_preview": ", ".join(c_ings),
                "llm_mean_score": r.get("mean_score", ""),
                "annotator_1": "",
                "annotator_2": "",
                "notes": "",
            })

    # Write
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} pairs ({len(selected)} anchors × {len(rows)//len(selected)} candidates)")
    print(f"→ {OUT_PATH}")


if __name__ == "__main__":
    main()
