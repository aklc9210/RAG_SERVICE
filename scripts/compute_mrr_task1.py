#!/usr/bin/env python3
"""Compute MRR@20 for Task 1 (reuses eval_task1_retrieval systems)."""
import json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

QUERIES_PATH = ROOT / "evaluation" / "data" / "task1_class_queries.jsonl"
K = 20

def mrr_at_k(retrieved, relevant, k):
    for i, d in enumerate(retrieved[:k]):
        if d in relevant:
            return 1.0 / (i + 1)
    return 0.0

def main():
    queries = [json.loads(l) for l in open(QUERIES_PATH)]
    print(f"Loaded {len(queries)} queries")

    from scripts.eval_task1_retrieval import (
        build_bm25_system, build_bm25_expansion_system,
        build_dense_system, build_rag_ontology_system
    )

    print("\nBuilding systems...")
    print("[1/4] BM25")
    bm25_fn = build_bm25_system()
    print("[2/4] BM25+Expansion")
    bm25exp_fn = build_bm25_expansion_system()
    print("[3/4] Dense")
    dense_fn = build_dense_system()
    print("[4/4] Dense+Ontology")
    ont_fn = build_rag_ontology_system(dense_fn)

    systems = {
        "BM25": lambda q, k, **kw: bm25_fn(q, k),
        "BM25+Expansion": lambda q, k, **kw: bm25exp_fn(q, k),
        "Dense": lambda q, k, **kw: dense_fn(q, k),
        "Dense+Ontology": ont_fn,
    }

    print(f"\nComputing MRR@{K}...")
    for sys_name, search_fn in systems.items():
        mrr_scores = []
        t0 = time.time()
        for q in queries:
            gt = set(q["gt_dish_ids"])
            kwargs = {
                "classes_pos": q.get("classes_positive"),
                "classes_neg": q.get("classes_negative"),
                "method": q.get("cooking_method"),
            }
            try:
                retrieved = search_fn(q["query"], K, **kwargs)
            except:
                retrieved = []
            mrr_scores.append(mrr_at_k(retrieved, gt, K))
        avg_mrr = sum(mrr_scores) / len(mrr_scores)
        print(f"  {sys_name:<20} MRR@{K} = {avg_mrr:.4f}  ({time.time()-t0:.1f}s)")

if __name__ == "__main__":
    main()
