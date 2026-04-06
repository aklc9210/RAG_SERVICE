#!/usr/bin/env python3
"""
Evaluation runner for the IR for Food Domain project.

Runs 3 systems (BM25, RAG-offline, RAG+Ontology) on all 3 tasks and computes:
  Task 1: nDCG@10, MRR@10, Recall@10
  Task 2: Precision@5, F1@5, Avg PMI
  Task 3: Precision@5, Recall@5

Note: This script runs in OFFLINE mode (no Pinecone / Ollama required).
      "RAG-offline" uses BM25 as proxy for dense retrieval scoring to enable
      local evaluation. Replace with live Pinecone results for full RAG evaluation.

Reads:
    data/splits/test_ids.txt
    evaluation/data/datasets/task1_queries.jsonl
    evaluation/data/datasets/task2_flavor_gt.jsonl
    evaluation/data/datasets/task3_related_gt.jsonl

Writes:
    evaluation/outputs/ir_task1_results.json
    evaluation/outputs/ir_task2_results.json
    evaluation/outputs/ir_task3_results.json
    evaluation/outputs/ir_ablation_table.json

Usage:
    python scripts/run_evaluation.py
    python scripts/run_evaluation.py --tasks 1 2 3
    python scripts/run_evaluation.py --tasks 2   # Task 2 only
"""

import argparse
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load .env so PINECONE_API_KEY etc. are available
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

SPLITS_DIR = ROOT / "data" / "splits"
DATASETS_DIR = ROOT / "evaluation" / "data" / "datasets"
OUT_DIR = ROOT / "evaluation" / "outputs"


# ============================================================
# Metric helpers
# ============================================================

def dcg(relevances: list, k: int) -> float:
    score = 0.0
    for i, rel in enumerate(relevances[:k]):
        score += rel / math.log2(i + 2)
    return score


def ndcg_at_k(ranked_ids: list, relevant: dict, k: int) -> float:
    """nDCG@k. relevant = {dish_id: score}"""
    gains = [relevant.get(did, 0) for did in ranked_ids[:k]]
    ideal = sorted(relevant.values(), reverse=True)
    actual_dcg = dcg(gains, k)
    ideal_dcg = dcg(ideal, k)
    return actual_dcg / ideal_dcg if ideal_dcg > 0 else 0.0


def mrr_at_k(ranked_ids: list, relevant: dict, k: int) -> float:
    """MRR@k. Considers score >= 2 as 'directly relevant'."""
    for i, did in enumerate(ranked_ids[:k]):
        if relevant.get(did, 0) >= 2:
            return 1.0 / (i + 1)
    return 0.0


def recall_at_k(ranked_ids: list, relevant: dict, k: int) -> float:
    n_relevant = sum(1 for v in relevant.values() if v > 0)
    if n_relevant == 0:
        return 0.0
    found = sum(1 for did in ranked_ids[:k] if relevant.get(did, 0) > 0)
    return found / n_relevant


def precision_at_k(predicted: list, ground_truth_ids: set, k: int) -> float:
    if not predicted:
        return 0.0
    hits = sum(1 for x in predicted[:k] if x in ground_truth_ids)
    return hits / min(k, len(predicted))


def f1_at_k(predicted: list, ground_truth_ids: set, k: int) -> float:
    p = precision_at_k(predicted, ground_truth_ids, k)
    n_gt = len(ground_truth_ids)
    r = sum(1 for x in predicted[:k] if x in ground_truth_ids) / n_gt if n_gt > 0 else 0.0
    return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


def recall_at_k_set(predicted: list, ground_truth_ids: set, k: int) -> float:
    if not ground_truth_ids:
        return 0.0
    found = sum(1 for x in predicted[:k] if x in ground_truth_ids)
    return found / len(ground_truth_ids)


# ============================================================
# Pinecone RAG retriever builder
# ============================================================

def build_pinecone_retriever():
    """
    Connect to Pinecone and return a Retriever instance.
    Returns None if PINECONE_API_KEY is not set or connection fails.
    """
    api_key = os.environ.get("PINECONE_API_KEY")
    index_name = os.environ.get("PINECONE_INDEX_NAME", "vn-food-rag")
    if not api_key:
        print("  PINECONE_API_KEY not set — skipping RAG-only system")
        return None
    try:
        from pinecone import Pinecone
        from ingestion.embedding import EmbeddingModel
        from retrieval.retriever import Retriever

        print(f"  Connecting to Pinecone index '{index_name}'...")
        pc = Pinecone(api_key=api_key)
        index = pc.Index(index_name)

        print("  Loading embedding model (multilingual-e5-large)...")
        # Temporarily allow online access to download model if not cached
        _offline = os.environ.pop("HF_HUB_OFFLINE", None)
        _tr_offline = os.environ.pop("TRANSFORMERS_OFFLINE", None)
        try:
            embed = EmbeddingModel()
        finally:
            if _offline is not None:
                os.environ["HF_HUB_OFFLINE"] = _offline
            if _tr_offline is not None:
                os.environ["TRANSFORMERS_OFFLINE"] = _tr_offline

        retriever = Retriever(embedding_model=embed, pinecone_index=index)
        print("  Pinecone retriever ready.")
        return retriever
    except Exception as e:
        print(f"  Failed to build Pinecone retriever: {e}")
        return None


# ============================================================
# Task 1 Evaluation
# ============================================================

def evaluate_task1(bm25, ontology_ret, queries, k=10, pinecone_retriever=None):
    """
    Evaluate Task 1 (Dish Retrieval).
    Systems:
      - BM25            : keyword search
      - RAG-only        : Pinecone dense search (if available)
      - RAG+Ontology    : Pinecone dense search + ontology reranking (if available)
                          Falls back to offline name-based search if no Pinecone.
    """
    system_names = ["BM25"]
    if pinecone_retriever is not None:
        system_names += ["RAG-only", "RAG+Ontology"]
    else:
        system_names += ["RAG+Ontology (offline)"]

    systems = {name: {"ndcg": [], "mrr": [], "recall": []} for name in system_names}

    total = len(queries)
    for qi, q in enumerate(queries):
        relevant = q["relevant"]
        if not relevant:
            continue

        if (qi + 1) % 100 == 0:
            print(f"    {qi + 1}/{total} queries done...")

        # --- BM25 ---
        bm25_results = bm25.search(q["query"], top_k=k)
        bm25_ids = [r["dish_id"] for r in bm25_results]
        systems["BM25"]["ndcg"].append(ndcg_at_k(bm25_ids, relevant, k))
        systems["BM25"]["mrr"].append(mrr_at_k(bm25_ids, relevant, k))
        systems["BM25"]["recall"].append(recall_at_k(bm25_ids, relevant, k))

        if pinecone_retriever is not None:
            # --- RAG-only (Pinecone dense, no ontology) ---
            raw = pinecone_retriever.search_filtered(
                query_text=q["query"], top_k=k, type_filter="dish"
            )
            rag_ids = [r["entity_id"] for r in raw if r.get("entity_id")]
            systems["RAG-only"]["ndcg"].append(ndcg_at_k(rag_ids, relevant, k))
            systems["RAG-only"]["mrr"].append(mrr_at_k(rag_ids, relevant, k))
            systems["RAG-only"]["recall"].append(recall_at_k(rag_ids, relevant, k))

            # --- RAG+Ontology (Pinecone results → ontology reranking) ---
            rag_for_rerank = [{"dish_id": r["entity_id"], "score": r["score"],
                                "dish_name": r.get("name_vi", "")} for r in raw if r.get("entity_id")]
            reranked = ontology_ret.search_dishes(q["query"], top_k=k, rag_results=rag_for_rerank)
            ont_ids = [r["dish_id"] for r in reranked]
            systems["RAG+Ontology"]["ndcg"].append(ndcg_at_k(ont_ids, relevant, k))
            systems["RAG+Ontology"]["mrr"].append(mrr_at_k(ont_ids, relevant, k))
            systems["RAG+Ontology"]["recall"].append(recall_at_k(ont_ids, relevant, k))

        else:
            # Offline fallback
            ont_results = ontology_ret.search_dishes(q["query"], top_k=k)
            ont_ids = [r["dish_id"] for r in ont_results]
            systems["RAG+Ontology (offline)"]["ndcg"].append(ndcg_at_k(ont_ids, relevant, k))
            systems["RAG+Ontology (offline)"]["mrr"].append(mrr_at_k(ont_ids, relevant, k))
            systems["RAG+Ontology (offline)"]["recall"].append(recall_at_k(ont_ids, relevant, k))

    def avg(lst):
        return round(sum(lst) / len(lst), 4) if lst else 0.0

    results = {}
    for sys_name, metrics in systems.items():
        results[sys_name] = {
            f"nDCG@{k}": avg(metrics["ndcg"]),
            f"MRR@{k}": avg(metrics["mrr"]),
            f"Recall@{k}": avg(metrics["recall"]),
            "n_queries": len(metrics["ndcg"]),
        }
    return results


# ============================================================
# Task 2 Evaluation
# ============================================================

def _rag_only_flavor(dish_name, dish_id, core_ids, pinecone_retriever, ont_dishes, k=5):
    """
    RAG-only flavor suggestion: query Pinecone with dish name, collect ingredients
    from retrieved similar dishes (excluding self and core), rank by frequency.
    Returns list of ingredient_ids (top-k).
    """
    core_set = set(core_ids)
    raw = pinecone_retriever.search_filtered(
        query_text=dish_name, top_k=15, type_filter="dish"
    )
    # Collect ingredient counts from retrieved dishes (excluding self)
    freq: dict = {}
    for match in raw:
        eid = match.get("entity_id", "")
        if eid == dish_id or not eid:
            continue
        for iid in ont_dishes.get(eid, {}).get("ingredient_ids", []):
            if iid not in core_set:
                freq[iid] = freq.get(iid, 0) + 1
    ranked = sorted(freq, key=lambda x: freq[x], reverse=True)
    return ranked[:k]


def evaluate_task2(bm25, ontology_ret, gt_entries, k=5, pinecone_retriever=None):
    """
    Evaluate Task 2 (Flavor-enhancing Ingredients).

    BM25 system: returns all ingredients of a dish ranked by term frequency
                 (simulates a naive RAG that just lists all ingredients from docs).
    RAG-only: queries Pinecone for similar dishes, aggregates ingredients by frequency.
    RAG+Ontology: uses PMI-based ranking.
    """
    from retrieval.bm25_retriever import _normalize

    systems = {
        "BM25": {"precision": [], "f1": [], "avg_pmi": []},
        "RAG+Ontology": {"precision": [], "f1": [], "avg_pmi": []},
    }
    if pinecone_retriever is not None:
        systems["RAG-only"] = {"precision": [], "f1": [], "avg_pmi": []}

    # Load PMI for avg-PMI metric
    pmi_path = ROOT / "app" / "data" / "cooccurrence" / "pmi.json"
    pmi = json.loads(pmi_path.read_text(encoding="utf-8")) if pmi_path.exists() else {}

    def get_pmi(x, y):
        if x in pmi and y in pmi[x]:
            return pmi[x][y]
        if y in pmi and x in pmi[y]:
            return pmi[y][x]
        return None

    for entry in gt_entries:
        dish_id = entry["dish_id"]
        gt_flavor_ids = {f["ingredient_id"] for f in entry["flavor_enhancing"]}
        if not gt_flavor_ids:
            continue

        core_ids = entry.get("core_ingredient_ids", [])
        all_ids = entry.get("ingredient_ids", ontology_ret._dishes.get(dish_id, {}).get("ingredient_ids", []))

        # --- BM25 "system": returns NON-CORE ingredients in arbitrary order
        # (simulates RAG returning all ingredients from document, minus core)
        non_core = [iid for iid in all_ids if iid not in set(core_ids)]
        bm25_pred = non_core[:k]

        p_bm25 = precision_at_k(bm25_pred, gt_flavor_ids, k)
        f_bm25 = f1_at_k(bm25_pred, gt_flavor_ids, k)
        pmi_bm25 = []
        for iid in bm25_pred:
            for cid in core_ids:
                v = get_pmi(cid, iid)
                if v is not None:
                    pmi_bm25.append(v)
        avg_pmi_bm25 = sum(pmi_bm25) / len(pmi_bm25) if pmi_bm25 else 0.0

        systems["BM25"]["precision"].append(p_bm25)
        systems["BM25"]["f1"].append(f_bm25)
        systems["BM25"]["avg_pmi"].append(avg_pmi_bm25)

        # --- RAG-only: Pinecone similar dishes → ingredient frequency ranking
        if pinecone_retriever is not None:
            rag_pred_ids = _rag_only_flavor(
                entry["dish_name"], dish_id, core_ids,
                pinecone_retriever, ontology_ret._dishes, k=k
            )
            p_rag = precision_at_k(rag_pred_ids, gt_flavor_ids, k)
            f_rag = f1_at_k(rag_pred_ids, gt_flavor_ids, k)
            pmi_rag = []
            for iid in rag_pred_ids:
                for cid in core_ids:
                    v = get_pmi(cid, iid)
                    if v is not None:
                        pmi_rag.append(v)
            avg_pmi_rag = sum(pmi_rag) / len(pmi_rag) if pmi_rag else 0.0
            systems["RAG-only"]["precision"].append(p_rag)
            systems["RAG-only"]["f1"].append(f_rag)
            systems["RAG-only"]["avg_pmi"].append(avg_pmi_rag)

        # --- RAG+Ontology: PMI-ranked
        ont_pred = ontology_ret.get_flavor_enhancing(dish_id, top_k=k)
        ont_pred_ids = [f["ingredient_id"] for f in ont_pred]

        p_ont = precision_at_k(ont_pred_ids, gt_flavor_ids, k)
        f_ont = f1_at_k(ont_pred_ids, gt_flavor_ids, k)
        pmi_ont = [f["mean_pmi"] for f in ont_pred if f["mean_pmi"] is not None]
        avg_pmi_ont = sum(pmi_ont) / len(pmi_ont) if pmi_ont else 0.0

        systems["RAG+Ontology"]["precision"].append(p_ont)
        systems["RAG+Ontology"]["f1"].append(f_ont)
        systems["RAG+Ontology"]["avg_pmi"].append(avg_pmi_ont)

    def avg(lst):
        return round(sum(lst) / len(lst), 4) if lst else 0.0

    results = {}
    for sys_name, metrics in systems.items():
        results[sys_name] = {
            f"Precision@{k}": avg(metrics["precision"]),
            f"F1@{k}": avg(metrics["f1"]),
            "Avg_PMI": avg(metrics["avg_pmi"]),
            "n_dishes": len(metrics["precision"]),
        }
    return results


# ============================================================
# Task 3 Evaluation
# ============================================================

def evaluate_task3(bm25, ontology_ret, gt_entries, k=5):
    """
    Evaluate Task 3 (Related Dishes).

    BM25 system: returns dishes ranked by BM25 score against the dish name.
    RAG+Ontology: uses Dish Relatedness (Jaccard + Category).
    """
    systems = {
        "BM25": {"precision": [], "recall": []},
        "RAG+Ontology": {"precision": [], "recall": []},
    }

    for entry in gt_entries:
        dish_id = entry["dish_id"]
        dish_name = entry["dish_name"]
        gt_related_ids = {r["dish_id"] for r in entry["related"]}
        if not gt_related_ids:
            continue

        # --- BM25: search using dish name, exclude self
        bm25_results = bm25.search(dish_name, top_k=k + 1)
        bm25_ids = [r["dish_id"] for r in bm25_results if r["dish_id"] != dish_id][:k]

        systems["BM25"]["precision"].append(precision_at_k(bm25_ids, gt_related_ids, k))
        systems["BM25"]["recall"].append(recall_at_k_set(bm25_ids, gt_related_ids, k))

        # --- RAG+Ontology: Dish Relatedness
        ont_results = ontology_ret.get_related_dishes(dish_id, top_k=k)
        ont_ids = [r["dish_id"] for r in ont_results]

        systems["RAG+Ontology"]["precision"].append(precision_at_k(ont_ids, gt_related_ids, k))
        systems["RAG+Ontology"]["recall"].append(recall_at_k_set(ont_ids, gt_related_ids, k))

    def avg(lst):
        return round(sum(lst) / len(lst), 4) if lst else 0.0

    results = {}
    for sys_name, metrics in systems.items():
        results[sys_name] = {
            f"Precision@{k}": avg(metrics["precision"]),
            f"Recall@{k}": avg(metrics["recall"]),
            "n_dishes": len(metrics["precision"]),
        }
    return results


# ============================================================
# Main
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(description="Run IR evaluation.")
    parser.add_argument("--tasks", nargs="+", type=int, default=[1, 2, 3],
                        help="Tasks to evaluate (default: 1 2 3)")
    return parser.parse_args()


def main():
    args = parse_args()

    print("=== IR Evaluation Runner ===")
    print(f"Tasks: {args.tasks}")

    # Load retrievers
    print("\nLoading BM25 retriever...")
    from retrieval.bm25_retriever import BM25Retriever
    bm25 = BM25Retriever()
    print(f"  Indexed {len(bm25)} dishes")

    print("Loading OntologyRetriever...")
    from retrieval.ontology_retriever import OntologyRetriever
    ont = OntologyRetriever()
    print(f"  Loaded {len(ont._dishes)} dishes")

    # Try to connect to Pinecone
    print("\nConnecting to Pinecone...")
    pinecone_ret = build_pinecone_retriever()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_results = {}

    # Task 1
    if 1 in args.tasks:
        print("\n--- Task 1: Dish Retrieval ---")
        queries = [json.loads(l) for l in (DATASETS_DIR / "task1_queries.jsonl").read_text().splitlines() if l]
        print(f"  Queries: {len(queries)}")
        t1 = evaluate_task1(bm25, ont, queries, k=10, pinecone_retriever=pinecone_ret)
        for sys_name, metrics in t1.items():
            print(f"  [{sys_name}] nDCG@10={metrics['nDCG@10']}  MRR@10={metrics['MRR@10']}  Recall@10={metrics['Recall@10']}")
        (OUT_DIR / "ir_task1_results.json").write_text(json.dumps(t1, indent=2))
        all_results["task1"] = t1

    # Task 2
    if 2 in args.tasks:
        print("\n--- Task 2: Flavor-enhancing Ingredients ---")
        gt = [json.loads(l) for l in (DATASETS_DIR / "task2_flavor_gt.jsonl").read_text().splitlines() if l]
        # Attach ingredient_ids from OntologyRetriever for BM25 evaluation
        for entry in gt:
            dish_data = ont._dishes.get(entry["dish_id"], {})
            entry["ingredient_ids"] = dish_data.get("ingredient_ids", [])
        print(f"  Dishes: {len(gt)}")
        t2 = evaluate_task2(bm25, ont, gt, k=5, pinecone_retriever=pinecone_ret)
        for sys_name, metrics in t2.items():
            print(f"  [{sys_name}] P@5={metrics['Precision@5']}  F1@5={metrics['F1@5']}  Avg_PMI={metrics['Avg_PMI']}")
        (OUT_DIR / "ir_task2_results.json").write_text(json.dumps(t2, indent=2))
        all_results["task2"] = t2

    # Task 3
    if 3 in args.tasks:
        print("\n--- Task 3: Related Dishes ---")
        gt = [json.loads(l) for l in (DATASETS_DIR / "task3_related_gt.jsonl").read_text().splitlines() if l]
        print(f"  Dishes: {len(gt)}")
        t3 = evaluate_task3(bm25, ont, gt, k=5)
        for sys_name, metrics in t3.items():
            print(f"  [{sys_name}] P@5={metrics['Precision@5']}  Recall@5={metrics['Recall@5']}")
        (OUT_DIR / "ir_task3_results.json").write_text(json.dumps(t3, indent=2))
        all_results["task3"] = t3

    # Ablation table
    if len(all_results) > 0:
        (OUT_DIR / "ir_ablation_table.json").write_text(json.dumps(all_results, indent=2))
        print(f"\nAblation table → {OUT_DIR / 'ir_ablation_table.json'}")

    print("\n=== Summary ===")
    _print_ablation_table(all_results)
    print("\nDone.")


def _print_ablation_table(all_results):
    if "task1" in all_results:
        print("\nTask 1 — Dish Retrieval")
        print(f"{'System':<30} {'nDCG@10':>10} {'MRR@10':>10} {'Recall@10':>12}")
        print("-" * 65)
        for sys_name, m in all_results["task1"].items():
            print(f"{sys_name:<30} {m['nDCG@10']:>10} {m['MRR@10']:>10} {m['Recall@10']:>12}")

    if "task2" in all_results:
        print("\nTask 2 — Flavor-enhancing Ingredients")
        print(f"{'System':<20} {'P@5':>10} {'F1@5':>10} {'Avg PMI':>12}")
        print("-" * 55)
        for sys_name, m in all_results["task2"].items():
            print(f"{sys_name:<20} {m['Precision@5']:>10} {m['F1@5']:>10} {m['Avg_PMI']:>12}")

    if "task3" in all_results:
        print("\nTask 3 — Related Dishes")
        print(f"{'System':<20} {'P@5':>10} {'Recall@5':>12}")
        print("-" * 45)
        for sys_name, m in all_results["task3"].items():
            print(f"{sys_name:<20} {m['Precision@5']:>10} {m['Recall@5']:>12}")


if __name__ == "__main__":
    main()
