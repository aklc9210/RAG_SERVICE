#!/usr/bin/env python3
"""
Evaluate Task 3 — Related Dishes using human annotation ground truth.

Protocol: Ranking-within-pool (same as Task 2 annotation eval).
  For each query dish, both systems receive the exact ~8 annotated candidates
  and must rank them. Metrics are computed on each system's ranked list
  against the annotation labels.

  This avoids pool-bias issues that plague free-prediction protocols
  when the pool has unbalanced positive rates.

IAA metrics:
  - Raw agreement %
  - Cohen's Kappa

Evaluation metrics (per system):
  - Precision@3, Precision@5
  - NDCG@5  (position-discounted ranking quality)
  - Avg IDF-Jaccard (of predicted candidates — flavor of dish similarity)

Aggregation strategies:
  - conservative: both annotators = 1  → positive
  - lenient:      at least one = 1     → positive

Reads:
    evaluation/annotation/task3_annotation_template.csv   (filled by annotators)
    evaluation/annotation/task3_annotation_answer_key.json
    app/data/cooccurrence/frequency.json
    app/data/cooccurrence/metadata.json
    processed/dishes/*.json

Writes:
    evaluation/outputs/ir_task3_annotation_eval.json

Usage:
    python scripts/eval_task3_annotation.py
    python scripts/eval_task3_annotation.py --csv evaluation/annotation/task3_annotation_template.csv
"""

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DISHES_DIR  = ROOT / "processed" / "dishes"
FREQ_PATH   = ROOT / "app" / "data" / "cooccurrence" / "frequency.json"
META_PATH   = ROOT / "app" / "data" / "cooccurrence" / "metadata.json"
DATASETS_DIR = ROOT / "evaluation" / "data" / "datasets"
OUT_DIR     = ROOT / "evaluation" / "outputs"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="evaluation/annotation/task3_annotation_template.csv")
    parser.add_argument("--key", default="evaluation/annotation/task3_annotation_answer_key.json")
    return parser.parse_args()


# ── Metric helpers ──────────────────────────────────────────────────────────

def cohens_kappa(pairs):
    """pairs: list of (a1_label, a2_label)"""
    n = len(pairs)
    if n == 0:
        return 0.0
    agree = sum(1 for a, b in pairs if a == b)
    p_o = agree / n

    a1_pos = sum(1 for a, b in pairs if a == 1) / n
    a2_pos = sum(1 for a, b in pairs if b == 1) / n
    p_e = (a1_pos * a2_pos) + ((1 - a1_pos) * (1 - a2_pos))
    return (p_o - p_e) / (1 - p_e) if p_e < 1 else 1.0


def precision_at_k(ranked_ids, positive_set, k):
    if not ranked_ids:
        return 0.0
    hits = sum(1 for x in ranked_ids[:k] if x in positive_set)
    return hits / min(k, len(ranked_ids))


def ndcg_at_k(ranked_ids, labels, k):
    """labels: {candidate_id: 0|1}"""
    gains = [labels.get(did, 0) for did in ranked_ids[:k]]
    ideal = sorted(labels.values(), reverse=True)
    dcg   = sum(g / math.log2(i + 2) for i, g in enumerate(gains))
    idcg  = sum(g / math.log2(i + 2) for i, g in enumerate(ideal[:k]))
    return dcg / idcg if idcg > 0 else 0.0


# ── IDF-Jaccard helper ──────────────────────────────────────────────────────

def load_idf():
    if not FREQ_PATH.exists() or not META_PATH.exists():
        return {}
    freq = json.loads(FREQ_PATH.read_text(encoding="utf-8"))
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    N = meta.get("total_dishes", 1)
    return {iid: math.log(N / max(1, count)) for iid, count in freq.items()}


def idf_jaccard(set_a, set_b, idf):
    if not set_a or not set_b:
        return 0.0
    inter = set_a & set_b
    union = set_a | set_b
    w_inter = sum(idf.get(i, 1.0) for i in inter)
    w_union = sum(idf.get(i, 1.0) for i in union)
    return w_inter / w_union if w_union > 0 else 0.0


# ── Load annotation CSV ─────────────────────────────────────────────────────

def load_annotation_csv(csv_path):
    import csv
    rows = []
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                a1 = int(row["annotator_1"])
                a2 = int(row["annotator_2"])
            except (ValueError, KeyError):
                continue  # skip unfilled rows
            rows.append({
                "query_dish_id":    row["query_dish_id"],
                "query_dish_name":  row["query_dish_name"],
                "candidate_dish_id":   row["candidate_dish_id"],
                "candidate_dish_name": row["candidate_dish_name"],
                "annotator_1": a1,
                "annotator_2": a2,
            })
    return rows


# ── Ranking systems ─────────────────────────────────────────────────────────

def rank_bm25(query_name, candidates, bm25):
    """BM25: search by query dish name, rank candidates by BM25 score."""
    results = bm25.search(query_name, top_k=50)
    score_map = {r["dish_id"]: r["score"] for r in results}
    return sorted(candidates, key=lambda c: score_map.get(c, 0.0), reverse=True)


def rank_ontology(query_id, candidates, ontology_ret):
    """RAG+Ontology: rank by IDF-Jaccard + category relatedness."""
    results = ontology_ret.get_related_dishes(query_id, top_k=100)
    score_map = {r["dish_id"]: r["relatedness"] for r in results}
    return sorted(candidates, key=lambda c: score_map.get(c, 0.0), reverse=True)


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()
    csv_path = ROOT / args.csv
    key_path = ROOT / args.key

    print("=== Task 3 Annotation Evaluation ===")

    if not csv_path.exists():
        print(f"ERROR: annotation CSV not found: {csv_path}")
        print("Run: python scripts/export_task3_annotation_template.py")
        return

    rows = load_annotation_csv(csv_path)
    if not rows:
        print("ERROR: No completed annotations found. Both annotator_1 and annotator_2 columns must be filled.")
        return

    print(f"Loaded {len(rows)} annotation pairs")

    # ── IAA ──────────────────────────────────────────────────────────────────
    pairs = [(r["annotator_1"], r["annotator_2"]) for r in rows]
    agree = sum(1 for a, b in pairs if a == b)
    kappa = cohens_kappa(pairs)
    n_disagree = len(pairs) - agree

    print(f"\nIAA:")
    print(f"  Total pairs     : {len(pairs)}")
    print(f"  Agreement       : {agree / len(pairs) * 100:.2f}%")
    print(f"  Cohen's Kappa   : {kappa:.4f}")
    print(f"  Disagreements   : {n_disagree}")

    if kappa < 0.4:
        print("  ⚠ Kappa < 0.4 — annotation quality is low. Review guidelines before using GT.")
    elif kappa < 0.6:
        print("  ⚠ Kappa 0.4–0.6 — moderate agreement. Use with caution.")
    else:
        print("  ✓ Kappa ≥ 0.6 — substantial agreement. GT is usable.")

    # ── Group by query dish ───────────────────────────────────────────────────
    by_query = defaultdict(list)
    for r in rows:
        by_query[r["query_dish_id"]].append(r)
    print(f"\nQuery dishes with completed annotations: {len(by_query)}")

    # ── Load retrievers ───────────────────────────────────────────────────────
    print("\nLoading retrievers...")
    from retrieval.bm25_retriever import BM25Retriever
    from retrieval.ontology_retriever import OntologyRetriever
    bm25 = BM25Retriever()
    ont  = OntologyRetriever()
    print(f"  BM25: {len(bm25)} dishes  |  Ontology: {len(ont._dishes)} dishes")

    idf = load_idf()

    # ── Load dish ingredient sets for Avg IDF-Jaccard metric ─────────────────
    dish_ing = {}
    for did, dish in ont._dishes.items():
        dish_ing[did] = dish.get("ingredient_ids_set", set())

    # ── Evaluate ─────────────────────────────────────────────────────────────
    strategies = {
        "conservative": lambda a1, a2: 1 if (a1 == 1 and a2 == 1) else 0,
        "lenient":      lambda a1, a2: 1 if (a1 == 1 or  a2 == 1) else 0,
    }

    system_names = ["BM25", "RAG+Ontology"]
    k_vals = [3, 5]

    eval_results = {}

    for strategy_name, merge_fn in strategies.items():
        metrics = {s: {"p3": [], "p5": [], "ndcg5": [], "avg_idfj": []}
                   for s in system_names}

        for query_id, qrows in by_query.items():
            candidates = [r["candidate_dish_id"] for r in qrows]
            labels = {r["candidate_dish_id"]: merge_fn(r["annotator_1"], r["annotator_2"])
                      for r in qrows}
            positive_set = {cid for cid, lbl in labels.items() if lbl == 1}

            if not positive_set:
                continue

            query_name = qrows[0]["query_dish_name"]

            for sys_name in system_names:
                if sys_name == "BM25":
                    ranked = rank_bm25(query_name, candidates, bm25)
                else:
                    ranked = rank_ontology(query_id, candidates, ont)

                metrics[sys_name]["p3"].append(precision_at_k(ranked, positive_set, 3))
                metrics[sys_name]["p5"].append(precision_at_k(ranked, positive_set, 5))
                metrics[sys_name]["ndcg5"].append(ndcg_at_k(ranked, labels, 5))

                # Avg IDF-Jaccard of top-5 predicted candidates with query
                query_ing = dish_ing.get(query_id, set())
                top5_idfj = []
                for cid in ranked[:5]:
                    cand_ing = dish_ing.get(cid, set())
                    top5_idfj.append(idf_jaccard(query_ing, cand_ing, idf))
                avg_idfj = sum(top5_idfj) / len(top5_idfj) if top5_idfj else 0.0
                metrics[sys_name]["avg_idfj"].append(avg_idfj)

        def avg(lst):
            return round(sum(lst) / len(lst), 4) if lst else 0.0

        eval_results[strategy_name] = {
            sys_name: {
                "Precision@3": avg(m["p3"]),
                "Precision@5": avg(m["p5"]),
                "NDCG@5":      avg(m["ndcg5"]),
                "Avg_IDF_Jaccard": avg(m["avg_idfj"]),
                "n_dishes":    len(m["p5"]),
            }
            for sys_name, m in metrics.items()
        }

    # ── Print results ─────────────────────────────────────────────────────────
    for strat, res in eval_results.items():
        label = "conservative (both agree=1)" if strat == "conservative" else "lenient (≥1 agrees=1)"
        pos_count = sum(
            1 for r in rows
            if strategies[strat](r["annotator_1"], r["annotator_2"]) == 1
        )
        print(f"\n── {label}  ({pos_count}/{len(rows)} = {pos_count/len(rows)*100:.0f}% positive) ──")
        print(f"{'System':<20} {'P@3':>8} {'P@5':>8} {'NDCG@5':>8} {'Avg IDF-J':>10}")
        print("-" * 60)
        for sys_name, m in res.items():
            print(f"{sys_name:<20} {m['Precision@3']:>8} {m['Precision@5']:>8} "
                  f"{m['NDCG@5']:>8} {m['Avg_IDF_Jaccard']:>10}")

    # ── Save ─────────────────────────────────────────────────────────────────
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = {
        "protocol": "ranking_within_annotation_pool",
        "iaa": {
            "n_pairs": len(pairs),
            "agreement_pct": round(agree / len(pairs) * 100, 2),
            "cohens_kappa": round(kappa, 4),
            "n_disagreements": n_disagree,
        },
        "results": eval_results,
        "note": (
            "For each query dish, systems rank the ~8 annotated candidates by score. "
            "Metrics computed against annotation labels. "
            "conservative = both annotators label=1; lenient = ≥1 annotator label=1."
        ),
    }
    out_path = OUT_DIR / "ir_task3_annotation_eval.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved → {out_path}")
    print("\nDone.")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT))
    main()
