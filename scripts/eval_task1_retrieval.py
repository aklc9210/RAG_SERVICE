#!/usr/bin/env python3
"""Day 3 — Person A — Task 1: Class-based Retrieval Evaluation.

3 systems compared on class-level queries:
  1. BM25         — keyword matching on dish name + ingredients
  2. Dense        — embedding similarity (multilingual-e5-large)
  3. Ontology+BM25 — BM25 with ontology query expansion

Metrics: Precision@k, NDCG@k, MRR@k for k in {5, 10, 20}

Usage:
    python scripts/eval_task1_retrieval.py
"""
import argparse
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Set

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

QUERIES_PATH = ROOT / "evaluation" / "data" / "task1_class_queries.jsonl"
K_DEFAULT = int(os.getenv("TASK_K", "20"))
OUT_PATH = ROOT / "evaluation" / "outputs" / f"ir_task1_ontology_results_k{K_DEFAULT}.json"


# ── Metrics ──────────────────────────────────────────────────────

def precision_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
    return sum(1 for d in retrieved[:k] if d in relevant) / k if k else 0

def recall_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
    return sum(1 for d in retrieved[:k] if d in relevant) / len(relevant) if relevant else 0

def f1_at_k(p: float, r: float) -> float:
    return 2 * p * r / (p + r) if (p + r) else 0

def average_precision(retrieved: List[str], relevant: Set[str]) -> float:
    hits = 0
    sum_prec = 0.0
    for i, d in enumerate(retrieved):
        if d in relevant:
            hits += 1
            sum_prec += hits / (i + 1)
    return sum_prec / len(relevant) if relevant else 0

def ndcg_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
    dcg = sum((1 / math.log2(i + 2)) for i, d in enumerate(retrieved[:k]) if d in relevant)
    ideal = sum(1 / math.log2(i + 2) for i in range(min(len(relevant), k)))
    return dcg / ideal if ideal else 0


def mrr_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
    for i, d in enumerate(retrieved[:k]):
        if d in relevant:
            return 1.0 / (i + 1)
    return 0.0


# ── System 1: BM25 ──────────────────────────────────────────────

def build_bm25_system():
    from retrieval.bm25_retriever import BM25Retriever
    print("  Building BM25 index...")
    bm25 = BM25Retriever()
    print(f"  Indexed {len(bm25)} dishes")

    def search(query: str, top_k: int) -> List[str]:
        results = bm25.search(query, top_k=top_k)
        return [r["dish_id"] for r in results]

    return search


# ── System 2: Dense (embedding similarity) ───────────────────────

def build_dense_system():
    from ingestion.embedding import EmbeddingModel
    print("  Loading embedding model...")
    em = EmbeddingModel()

    # Build corpus embeddings from processed dishes
    dishes_dir = ROOT / "processed" / "dishes"
    print("  Embedding dish corpus...")
    dish_ids = []
    dish_texts = []
    for f in sorted(dishes_dir.glob("*.json")):
        try:
            d = json.loads(f.read_text("utf-8"))
        except Exception:
            continue
        text = d.get("name_vi", "")
        ings = d.get("main_ingredients", []) + d.get("secondary_ingredients", [])
        if ings:
            text += " " + " ".join(ings[:10])
        dish_ids.append(d["id"])
        dish_texts.append(text)

    print(f"  Embedding {len(dish_ids)} dishes (batch)...")
    import numpy as np
    batch_size = 128
    all_vecs = []
    for i in range(0, len(dish_texts), batch_size):
        batch = dish_texts[i:i + batch_size]
        vecs = em.embed_documents(batch)
        all_vecs.extend(vecs)
        if (i // batch_size) % 10 == 0:
            print(f"    {i}/{len(dish_texts)}")
    corpus_matrix = np.array(all_vecs)  # (N, dim)
    print(f"  Corpus shape: {corpus_matrix.shape}")

    def search(query: str, top_k: int) -> List[str]:
        qvec = np.array(em.embed_query(query))
        scores = (corpus_matrix @ qvec).flatten()
        top_idx = scores.argsort()[::-1][:top_k]
        return [dish_ids[i] for i in top_idx]

    return search


# ── System 3: BM25 + Naive Expansion (synonyms, no ontology) ─────

def build_bm25_expansion_system():
    from retrieval.bm25_retriever import BM25Retriever
    print("  Building BM25 index for naive expansion...")
    bm25 = BM25Retriever()

    # Load ingredient KB for synonym expansion (flat, no hierarchy)
    ikb = json.loads((ROOT / "app" / "data" / "knowledge_base" /
                       "ingredient_knowledge_base.json").read_text("utf-8"))
    # keyword → list of synonyms/related names (flat KB only)
    keyword_to_names = {}
    for e in ikb:
        name = e.get("name_vi", "").lower().strip()
        syns = [s.lower().strip() for s in (e.get("synonyms") or [])]
        if name:
            keyword_to_names[name] = syns + [name]
            for s in syns:
                keyword_to_names.setdefault(s, []).append(name)

    def search(query: str, top_k: int, **kwargs) -> List[str]:
        # Expand query using flat synonym lookup (no hierarchy)
        tokens = query.lower().split()
        expanded_terms = []
        for tok in tokens:
            if tok in keyword_to_names:
                expanded_terms.extend(keyword_to_names[tok][:5])
        expanded_query = query
        if expanded_terms:
            expanded_query = query + " " + " ".join(set(expanded_terms))
        results = bm25.search(expanded_query, top_k=top_k)
        return [r["dish_id"] for r in results]

    return search


# ── System 4: RAG + Ontology (Dense + query expansion + post-filter) ──

def build_rag_ontology_system(dense_search_fn):
    from retrieval.ontology import FoodOntology

    FoodOntology._instance = None
    ont = FoodOntology()
    print("  Loaded ontology for expansion + filtering")

    def search(query: str, top_k: int,
               classes_pos=None, classes_neg=None, method=None) -> List[str]:
        # Expand query with ontology ingredient names
        expanded_terms = []
        for cls in (classes_pos or []):
            for iid in ont.get_descendants(cls)[:30]:
                meta = ont.ing_meta.get(iid)
                if meta:
                    expanded_terms.append(meta.get("name_vi", ""))

        expanded_query = query
        if expanded_terms:
            short_terms = sorted(set(expanded_terms), key=len)[:10]
            expanded_query = query + " " + " ".join(short_terms)

        # Dense retrieval with expanded query
        fetch_k = top_k * 5 if (classes_neg or method) else top_k
        retrieved_ids = dense_search_fn(expanded_query, fetch_k)

        # Post-filter by negative classes and cooking method
        if classes_neg or method:
            neg_ids = set()
            for cls in (classes_neg or []):
                neg_ids |= set(ont.get_descendants(cls))

            filtered = []
            for did in retrieved_ids:
                dish_path = ROOT / "processed" / "dishes" / f"{did}.json"
                if not dish_path.exists():
                    continue
                d = json.loads(dish_path.read_text("utf-8"))
                ings = set(d.get("ingredient_ids", []))

                if neg_ids and (ings & neg_ids):
                    continue
                if method and ont.get_cooking_method(did) != method:
                    continue
                filtered.append(did)
            retrieved_ids = filtered

        return retrieved_ids[:top_k]

    return search


# ── Main evaluation ──────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    args = ap.parse_args()
    K = K_DEFAULT

    # Load queries
    queries = []
    with open(QUERIES_PATH, encoding="utf-8") as f:
        for line in f:
            queries.append(json.loads(line))
    print(f"Loaded {len(queries)} queries")

    # Build systems
    print("\nBuilding systems...")
    systems = {}

    print("[1/4] BM25")
    bm25_fn = build_bm25_system()
    systems["BM25"] = lambda q, k, **kw: bm25_fn(q, k)

    print("[2/4] BM25+Expansion")
    bm25exp_fn = build_bm25_expansion_system()
    systems["BM25+Expansion"] = lambda q, k, **kw: bm25exp_fn(q, k)

    print("[3/4] RAG-only")
    dense_fn = build_dense_system()
    systems["RAG-only"] = lambda q, k, **kw: dense_fn(q, k)

    print("[4/4] RAG+Ontology")
    ont_fn = build_rag_ontology_system(dense_fn)
    systems["RAG+Ontology"] = ont_fn

    # Run evaluation
    print(f"\nEvaluating {len(queries)} queries × {len(systems)} systems @ k={K}...")
    all_results = {}

    for sys_name, search_fn in systems.items():
        print(f"\n  [{sys_name}]")
        metrics_list = []
        t0 = time.time()

        for i, q in enumerate(queries):
            gt = set(q["gt_dish_ids"])
            kwargs = {
                "classes_pos": q.get("classes_positive"),
                "classes_neg": q.get("classes_negative"),
                "method": q.get("cooking_method"),
            }
            try:
                retrieved = search_fn(q["query"], K, **kwargs)
            except Exception as e:
                retrieved = []

            p = precision_at_k(retrieved, gt, K)
            ndcg = ndcg_at_k(retrieved, gt, K)
            mrr = mrr_at_k(retrieved, gt, K)
            metrics_list.append({f"P@{K}": p, f"NDCG@{K}": ndcg, f"MRR@{K}": mrr})

            if (i + 1) % 50 == 0:
                elapsed = time.time() - t0
                print(f"    {i+1}/{len(queries)} ({elapsed:.1f}s)")

        # Aggregate
        agg = {k: round(sum(m[k] for m in metrics_list) / len(metrics_list), 4)
               for k in metrics_list[0]}

        all_results[sys_name] = {"mean_metrics": agg, "n_queries": len(queries)}
        elapsed = time.time() - t0
        print(f"    Done in {elapsed:.1f}s — {agg}")

    # Save
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), "utf-8")
    print(f"\nSaved → {OUT_PATH}")

    # Summary table
    print(f"\n{'System':<20} {'P@'+str(K):<8} {'NDCG@'+str(K):<8} {'MRR@'+str(K):<8}")
    print("-" * 44)
    for sys_name, data in all_results.items():
        m = data["mean_metrics"]
        print(f"{sys_name:<20} {m[f'P@{K}']:<8} {m[f'NDCG@{K}']:<8} {m[f'MRR@{K}']:<8}")


if __name__ == "__main__":
    main()
