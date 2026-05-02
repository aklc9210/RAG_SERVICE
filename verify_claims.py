#!/usr/bin/env python3
"""Verify paper claims against actual data."""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "evaluation" / "data"
OUT = ROOT / "evaluation" / "outputs"

def p(claim, actual, match=None):
    if match is None:
        match = str(claim) == str(actual)
    tag = "MATCH" if match else "MISMATCH"
    print(f"CLAIM: {claim} | ACTUAL: {actual} | {tag}")

print("=" * 80)
print("1. TASK 1: 200 queries, 50 each of 4 types")
print("=" * 80)
t1 = [json.loads(l) for l in open(DATA / "task1_class_queries.jsonl")]
p("200 total queries", f"{len(t1)} total queries", len(t1) == 200)
tc = Counter(r["type"] for r in t1)
for t in ["single_class", "multi_class", "negation", "cooking_method"]:
    p(f"50 {t}", f"{tc.get(t, 0)} {t}", tc.get(t, 0) == 50)

print()
print("=" * 80)
print("2. TASK 1 GT sizes by type")
print("=" * 80)
for t, claimed in [("single_class", "~1500"), ("multi_class", "~350"),
                    ("negation", "~1200"), ("cooking_method", "~150")]:
    sizes = [r["gt_count"] for r in t1 if r["type"] == t]
    avg = sum(sizes) / len(sizes) if sizes else 0
    p(f"{t} avg GT ~{claimed}", f"{t} avg GT = {avg:.1f}")

print()
print("=" * 80)
print("3. TASK 2: 100 test cases")
print("=" * 80)
t2 = [json.loads(l) for l in open(DATA / "datasets" / "task2_substitution_gt.jsonl")]
p("100 test cases", f"{len(t2)} test cases", len(t2) == 100)

print()
print("=" * 80)
print("4. TASK 3: 200 anchor dishes, 21,480 scored pairs")
print("=" * 80)
t3 = [json.loads(l) for l in open(DATA / "datasets" / "task3_related_gt.jsonl")]
p("200 anchor dishes (from paper claim)", f"{len(t3)} anchor dishes")
total_pairs = sum(len(d.get("related", [])) for d in t3)
p("21,480 scored pairs", f"{total_pairs} scored pairs", total_pairs == 21480)

print()
print("=" * 80)
print("5. TASK 3: 2,148 dishes in table caption")
print("=" * 80)
stats3 = json.load(open(DATA / "datasets" / "task3_stats.json"))
p("2,148 dishes", f"{stats3['n_test_dishes']} dishes", stats3["n_test_dishes"] == 2148)

print()
print("=" * 80)
print("6. EXPERIMENT RESULTS - Task 1 Ontology (class queries)")
print("=" * 80)
ont_res = json.load(open(OUT / "ir_task1_ontology_results.json"))
for sys_name, metrics in ont_res.items():
    mm = metrics["mean_metrics"]
    print(f"  {sys_name}: P@20={mm['P@20']:.4f}, NDCG@20={mm['NDCG@20']:.4f}, n={metrics['n_queries']}")
    p(f"{sys_name} n_queries=200", f"{metrics['n_queries']}", metrics["n_queries"] == 200)

print()
print("--- Task 1 General (530 queries) ---")
t1_res = json.load(open(OUT / "ir_task1_results.json"))
for sys_name, metrics in t1_res.items():
    print(f"  {sys_name}: nDCG@10={metrics['nDCG@10']}, MRR@10={metrics['MRR@10']}, n={metrics['n_queries']}")

print()
print("--- Task 2 Substitution ---")
t2_res = json.load(open(OUT / "ir_task2_substitution_results.json"))
summary = t2_res.get("summary", {})
for cls_name, cls_data in summary.items():
    print(f"  {cls_name}: mean_score={cls_data.get('mean_score', 'N/A')}, accept_rate={cls_data.get('accept_rate', 'N/A')}")

print()
print("--- Task 3 IR ---")
t3_res = json.load(open(OUT / "ir_task3_results.json"))
for sys_name, metrics in t3_res.items():
    print(f"  {sys_name}: P@5={metrics.get('Precision@5', 'N/A')}, NDCG@5={metrics.get('NDCG@5', 'N/A')}, n={metrics['n_dishes']}")
    p(f"{sys_name} n_dishes=2148", f"{metrics['n_dishes']}", metrics["n_dishes"] == 2148)

print()
print("--- Task 3 LLM Judge (3 judges) ---")
judge3 = json.load(open(OUT / "llm_judge_task3_3judges.json"))
p("1600 judged pairs", f"{judge3['n_items']} judged pairs", judge3["n_items"] == 1600)
print(f"  Judges: {judge3['judges']}")
print(f"  Mean score: {judge3['mean_score']}")

print()
print("--- Task 3 LLM Judge Summary (4 judges) ---")
judge_sum = json.load(open(OUT / "llm_judge_task3_summary.json"))
for model, data in judge_sum.get("models", {}).items():
    print(f"  {model}: mean={data['mean_score']}, n={data['n_valid']}")

print()
print("=" * 80)
print("7. LEAF CLASSES: 24 used vs 38/39 in hierarchy")
print("=" * 80)
# Count from build_task1_class_queries.py VI dict
vi_classes = ["Seafood", "Meat", "Poultry", "Offal", "Egg", "CuredMeat",
              "PlantProtein", "Vegetable", "Herb", "RootVeg", "Mushroom",
              "FreshFruit", "DriedFruit", "SaltyUmami", "Spicy", "SourSeasoning",
              "SweetSeasoning", "Aromatic", "Grain", "Noodle", "Flour", "Bread",
              "Milk", "Cheese"]
p("24 leaf classes in VI dict", f"{len(vi_classes)} leaf classes in VI dict", len(vi_classes) == 24)

# Check actual classes used in queries
used = set()
for r in t1:
    used.update(r.get("classes_positive", []))
    used.update(r.get("classes_negative", []))
p("24 classes actually used in queries", f"{len(used)} classes used in queries")

print()
print("=" * 80)
print("8. COOKING METHODS: 10 for query generation")
print("=" * 80)
methods = ["Fry", "StirFry", "Boil", "Stew", "Grill", "Steam", "Hotpot", "Bake", "Mix", "NoodleSoup"]
p("10 cooking methods", f"{len(methods)} cooking methods", len(methods) == 10)

print()
print("=" * 80)
print("9. DISH CATEGORIES: 25 for Task 3 stratification")
print("=" * 80)
cats = set(d.get("category", "") for d in t3)
p("25 dish categories", f"{len(cats)} dish categories")
print(f"  Categories: {sorted(cats)}")

# Also check from task1_stats
stats1 = json.load(open(DATA / "datasets" / "task1_stats.json"))
p("25 categories (from task1_stats)", f"{stats1.get('n_categories', 'N/A')} categories",
  stats1.get("n_categories") == 25)

print()
print("=" * 80)
print("10. TASK 2 CONSTRAINT DISTRIBUTION: 47%/23%/19%/11%")
print("=" * 80)
constraint_counts = Counter()
for case in t2:
    constraints = case.get("constraints", case.get("constraint_type", ""))
    if isinstance(constraints, list):
        key = ",".join(sorted(constraints)) if constraints else "none"
    else:
        key = constraints if constraints else "none"
    constraint_counts[key] += 1

total = len(t2)
print(f"  Total cases: {total}")
for k, v in constraint_counts.most_common():
    pct = v / total * 100
    print(f"  {k}: {v} ({pct:.0f}%)")

# Check claimed distribution
claimed = {"none": 47, "no_seafood": 23, "vegetarian": 19, "low_sodium": 11}
for k, cpct in claimed.items():
    actual_count = constraint_counts.get(k, 0)
    actual_pct = actual_count / total * 100 if total else 0
    p(f"{k} = {cpct}%", f"{k} = {actual_pct:.0f}% ({actual_count}/{total})",
      abs(actual_pct - cpct) < 2)

print()
print("=" * 80)
print("ADDITIONAL: Task 3 anchor count vs 200 claim")
print("=" * 80)
# Count unique query dishes in LLM judge data
judge_items = judge3["items"]
unique_anchors = set(item["query_dish_id"] for item in judge_items)
p("200 anchor dishes (LLM judge)", f"{len(unique_anchors)} unique query dishes in judge data")

# Task 3 related GT: each dish has 10 related
related_counts = [len(d.get("related", [])) for d in t3]
avg_related = sum(related_counts) / len(related_counts) if related_counts else 0
print(f"  Avg related per dish: {avg_related:.1f}")
print(f"  Total dishes in task3_related_gt: {len(t3)}")
print(f"  Total pairs: {len(t3)} * {avg_related:.0f} = {total_pairs}")

# Verify 21480 = 2148 * 10
p("21,480 = 2,148 * 10", f"{len(t3)} * {avg_related:.0f} = {total_pairs}",
  total_pairs == 21480)
