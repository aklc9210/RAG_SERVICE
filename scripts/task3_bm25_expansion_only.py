#!/usr/bin/env python3
"""Task 3: BM25+Expansion system evaluation ONLY.

Runs BM25+Expansion (flat synonym expansion) on the same anchor/candidate pairs
used in task3_ablation_cv.py, computes P@5, NDCG@5, MRR@5, and merges the result
into the existing task3_ablation_cv_results.json.

This avoids re-running the full ablation + Dense embedding pipeline.

Usage:
    python scripts/task3_bm25_expansion_only.py
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ── Paths ────────────────────────────────────────────────────────

GT_PATH = ROOT / "evaluation" / "data" / "datasets" / "task3_related_gt.jsonl"
JUDGE_PATH = ROOT / "evaluation" / "outputs" / "task3_diverse_judged.json"
RESULTS_PATH = ROOT / "evaluation" / "outputs" / "task3_ablation_cv_results.json"

# ── Load judge pairs (same as main script) ───────────────────────

dish_meta = {}
with open(GT_PATH, encoding="utf-8") as f:
    for line in f:
        e = json.loads(line)
        dish_meta[e["dish_id"]] = e["ingredient_ids"]

judges = json.loads(JUDGE_PATH.read_text("utf-8"))
judge_pairs = [(it["anchor_id"], it["candidate_id"], it["mean_score"])
               for it in judges["results"]
               if it["mean_score"] is not None
               and it["anchor_id"] in dish_meta and it["candidate_id"] in dish_meta]
print(f"Loaded {len(judge_pairs)} valid judge pairs")

from collections import defaultdict
anchor_groups = defaultdict(list)
for a, b, score in judge_pairs:
    anchor_groups[a].append((b, score))
anchors = list(anchor_groups.keys())
print(f"Unique anchors: {len(anchors)}")

# ── Load dish KB ─────────────────────────────────────────────────

_dish_kb = {d["id"]: d for d in json.loads(
    (ROOT / "app" / "data" / "knowledge_base" / "dish_knowledge_base.json").read_text("utf-8")
)}

# ── Load ingredient KB for synonym expansion ─────────────────────

print("Loading ingredient KB for synonym expansion...")
_ikb = json.loads((ROOT / "app" / "data" / "knowledge_base" /
                   "ingredient_knowledge_base.json").read_text("utf-8"))

# Build keyword → synonyms map (flat, no hierarchy — same as Task 1)
_keyword_to_names = {}
for entry in _ikb:
    name = entry.get("name_vi", "").lower().strip()
    syns = [s.lower().strip() for s in (entry.get("synonyms") or [])]
    if name:
        _keyword_to_names[name] = syns + [name]
        for s in syns:
            _keyword_to_names.setdefault(s, []).append(name)

print(f"  Synonym map: {len(_keyword_to_names)} keywords")

# ── Build BM25 index ─────────────────────────────────────────────

from retrieval.bm25_retriever import BM25Retriever

print("Building BM25 index...")
bm25 = BM25Retriever()
print(f"  Indexed {len(bm25)} dishes")

# ── BM25+Expansion: search with expanded queries ────────────────

POSITIVE_THRESHOLD = 1.0

print("\nRunning BM25+Expansion on 200 anchors...")
bm25_exp_rankings = {}
for i, anchor in enumerate(anchors):
    d = _dish_kb.get(anchor, {})
    name = d.get("name_vi", "")

    # Build expanded query: dish name + ingredient names + their synonyms
    query_parts = [name]
    for ing in d.get("ingredients", []):
        ing_name = ing.get("name_vi", "").lower().strip()
        if ing_name:
            query_parts.append(ing_name)
            # Add synonyms (max 3 per ingredient to avoid noise)
            syns = _keyword_to_names.get(ing_name, [])
            query_parts.extend(syns[:3])

    expanded_query = " ".join(query_parts)
    res = bm25.search(expanded_query, top_k=200)
    bm25_exp_rankings[anchor] = {r["dish_id"]: 1.0 / (idx + 1) for idx, r in enumerate(res)}

    if (i + 1) % 50 == 0:
        print(f"  Progress: {i+1}/{len(anchors)}")

print("Done.")

# ── Compute metrics ──────────────────────────────────────────────

def system_metrics(rankings):
    p5_list, ndcg5_list, mrr5_list = [], [], []
    for anchor in anchors:
        candidates = anchor_groups[anchor]
        r = rankings.get(anchor, {})
        sorted_cands = sorted(candidates, key=lambda x: r.get(x[0], 0), reverse=True)
        top5 = sorted_cands[:5]
        rels = [1 if gt >= POSITIVE_THRESHOLD else 0 for _, gt in top5]

        # P@5
        p5_list.append(sum(rels) / 5)

        # NDCG@5
        dcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(rels))
        n_pos = sum(1 for _, gt in sorted_cands if gt >= POSITIVE_THRESHOLD)
        ideal = sum(1 / math.log2(i + 2) for i in range(min(n_pos, 5)))
        ndcg5_list.append(dcg / ideal if ideal > 0 else 0.0)

        # MRR@5
        mrr = 0.0
        for i, rel in enumerate(rels):
            if rel:
                mrr = 1.0 / (i + 1)
                break
        mrr5_list.append(mrr)

    return {
        "P@5": float(np.mean(p5_list)),
        "NDCG@5": float(np.mean(ndcg5_list)),
        "MRR@5": float(np.mean(mrr5_list)),
    }


bm25_exp_m = system_metrics(bm25_exp_rankings)

# ── Print results ────────────────────────────────────────────────

print(f"\n{'='*50}")
print("BM25+Expansion Results (Task 3)")
print(f"{'='*50}")
print(f"  P@5:    {bm25_exp_m['P@5']:.4f}")
print(f"  NDCG@5: {bm25_exp_m['NDCG@5']:.4f}")
print(f"  MRR@5:  {bm25_exp_m['MRR@5']:.4f}")

# Compare with existing results
if RESULTS_PATH.exists():
    existing = json.loads(RESULTS_PATH.read_text("utf-8"))
    sc = existing.get("system_comparison", {})
    print(f"\n{'System':<18} {'P@5':<8} {'NDCG@5':<8} {'MRR@5':<8}")
    print("-" * 42)
    for sys_name in ["BM25", "BM25+Expansion", "Dense", "Dense+Ontology"]:
        if sys_name == "BM25+Expansion":
            m = bm25_exp_m
        elif sys_name in sc:
            m = sc[sys_name]
        else:
            continue
        print(f"{sys_name:<18} {m['P@5']:.4f}  {m['NDCG@5']:.4f}  {m['MRR@5']:.4f}")

# ── Merge into existing results JSON ────────────────────────────

if RESULTS_PATH.exists():
    existing = json.loads(RESULTS_PATH.read_text("utf-8"))
    existing["system_comparison"]["BM25+Expansion"] = bm25_exp_m
    RESULTS_PATH.write_text(json.dumps(existing, indent=2, ensure_ascii=False), "utf-8")
    print(f"\n✓ Merged BM25+Expansion into {RESULTS_PATH}")
else:
    print(f"\n⚠ Results file not found at {RESULTS_PATH}")
    print("  Run task3_ablation_cv.py first, or save standalone:")
    standalone = {"BM25+Expansion": bm25_exp_m}
    out = ROOT / "evaluation" / "outputs" / "task3_bm25_expansion_results.json"
    out.write_text(json.dumps(standalone, indent=2, ensure_ascii=False), "utf-8")
    print(f"  Saved → {out}")
