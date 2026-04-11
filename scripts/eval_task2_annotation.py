#!/usr/bin/env python3
"""
Evaluate Task 2 (Flavor-enhancing Ingredients) against human annotation GT.

Protocol: RANKING EVALUATION within annotation pool.
  For each dish, we give the system ALL ~8 annotated candidates and ask it to
  rank them. We then compute P@k and NDCG@k within this controlled candidate set.
  This tests discrimination ability (positive vs negative) rather than free recall.

Reads:
    evaluation/annotation/annotation_template.csv   — annotated candidates (50 dishes)
    evaluation/annotation/annotation_answer_key.json — candidate source (pmi/random)
    app/data/cooccurrence/npmi.json                 — NPMI scores

Systems evaluated:
    BM25          — rank by position in dish ingredient list (earlier = higher)
    RAG+Ontology  — rank by NPMI score + category prior

GT aggregation:
    conservative  — both annotators say 1 → label=1
    lenient       — at least one annotator says 1 → label=1

Outputs:
    evaluation/outputs/ir_task2_annotation_eval.json
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

ANNOTATION_CSV = ROOT / "evaluation" / "annotation" / "annotation_template.csv"
ANSWER_KEY = ROOT / "evaluation" / "annotation" / "annotation_answer_key.json"
NPMI_PATH = ROOT / "app" / "data" / "cooccurrence" / "npmi.json"
OUT_DIR = ROOT / "evaluation" / "outputs"


# ============================================================
# Metric helpers
# ============================================================

def dcg(labels: list, k: int) -> float:
    score = 0.0
    for i, rel in enumerate(labels[:k]):
        score += rel / __import__('math').log2(i + 2)
    return score


def ndcg_at_k(ranked_labels: list, k: int) -> float:
    ideal = sorted(ranked_labels, reverse=True)
    actual = dcg(ranked_labels, k)
    ideal_val = dcg(ideal, k)
    return actual / ideal_val if ideal_val > 0 else 0.0


def precision_at_k(ranked_labels: list, k: int) -> float:
    top = ranked_labels[:k]
    return sum(top) / len(top) if top else 0.0


def cohens_kappa(labels_a: list, labels_b: list) -> float:
    n = len(labels_a)
    if n == 0:
        return 0.0
    po = sum(a == b for a, b in zip(labels_a, labels_b)) / n
    p_a1 = sum(labels_a) / n
    p_b1 = sum(labels_b) / n
    pe = p_a1 * p_b1 + (1 - p_a1) * (1 - p_b1)
    return (po - pe) / (1 - pe) if pe < 1.0 else 1.0


# ============================================================
# Load data
# ============================================================

def load_annotation(path: Path) -> dict:
    """dish_id → {dish_name, category, candidates: [{candidate_id, candidate_name, a1, a2}]}"""
    dishes = {}
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            did = row["dish_id"].strip()
            if did not in dishes:
                dishes[did] = {
                    "dish_name": row["dish_name"].strip(),
                    "category": row["category"].strip(),
                    "candidates": [],
                }
            dishes[did]["candidates"].append({
                "candidate_id": row["candidate_id"].strip(),
                "candidate_name": row["candidate_name"].strip(),
                "a1": row.get("annotator_1", "").strip(),
                "a2": row.get("annotator_2", "").strip(),
            })
    return dishes


def build_label(c: dict, strategy: str) -> int | None:
    """Return 0/1 label for a candidate, or None if data missing."""
    a1, a2 = c["a1"], c["a2"]
    if a1 not in ("0", "1") or a2 not in ("0", "1"):
        return None
    i1, i2 = int(a1), int(a2)
    if strategy == "conservative":
        return 1 if (i1 == 1 and i2 == 1) else 0
    else:  # lenient
        return 1 if (i1 == 1 or i2 == 1) else 0


# ============================================================
# Scoring functions per system
# ============================================================

def score_bm25(candidate_id: str, dish_data: dict) -> float:
    """
    BM25 baseline: rank by position in ingredient list.
    Earlier position = higher score (core ingredients excluded upstream).
    """
    all_ids = dish_data.get("ingredient_ids", [])
    try:
        pos = all_ids.index(candidate_id)
        return 1.0 / (pos + 1)  # inverse position
    except ValueError:
        return 0.0


def score_ontology(candidate_id: str, core_ids: set, npmi: dict,
                   flavor_category_ids: set) -> float:
    """
    RAG+Ontology: mean NPMI with core ingredients + category prior.
    Mirrors get_flavor_enhancing() logic exactly.
    """
    pmi_vals = []
    for cid in core_ids:
        x, y = cid, candidate_id
        v = npmi.get(x, {}).get(y) or npmi.get(y, {}).get(x)
        if v is not None:
            pmi_vals.append(v)
    if not pmi_vals:
        return -999.0
    mean_pmi = sum(pmi_vals) / len(pmi_vals)
    if candidate_id in flavor_category_ids:
        mean_pmi *= 1.15
    return mean_pmi


# ============================================================
# Inter-Annotator Agreement
# ============================================================

def compute_iaa(dishes: dict) -> dict:
    labels_a, labels_b = [], []
    for d in dishes.values():
        for c in d["candidates"]:
            a1, a2 = c["a1"], c["a2"]
            if a1 in ("0", "1") and a2 in ("0", "1"):
                labels_a.append(int(a1))
                labels_b.append(int(a2))
    n = len(labels_a)
    agree = sum(a == b for a, b in zip(labels_a, labels_b))
    kappa = cohens_kappa(labels_a, labels_b)
    return {
        "n_pairs": n,
        "agreement_pct": round(agree / n * 100, 2) if n else 0,
        "cohens_kappa": round(kappa, 4),
        "n_disagreements": n - agree,
    }


# ============================================================
# Main
# ============================================================

def main():
    print("=== Task 2 Annotation-based Evaluation (Ranking Protocol) ===\n")

    dishes = load_annotation(ANNOTATION_CSV)
    n_candidates = sum(len(d["candidates"]) for d in dishes.values())
    print(f"Dishes: {len(dishes)}  |  Candidates: {n_candidates}")

    # IAA
    iaa = compute_iaa(dishes)
    print(f"\nInter-Annotator Agreement:")
    print(f"  Pairs: {iaa['n_pairs']}")
    print(f"  Agreement: {iaa['agreement_pct']}%")
    print(f"  Cohen's Kappa: {iaa['cohens_kappa']}  (≥0.6 = substantial)")
    print(f"  Disagreements: {iaa['n_disagreements']}")

    # Load NPMI + ontology data
    print("\nLoading NPMI + OntologyRetriever...")
    npmi = json.loads(NPMI_PATH.read_text(encoding="utf-8")) if NPMI_PATH.exists() else {}
    from retrieval.ontology_retriever import OntologyRetriever
    ont = OntologyRetriever()
    print(f"  Loaded {len(ont._dishes)} dishes")

    results_by_strategy = {}

    for strategy in ("conservative", "lenient"):
        # Pool stats
        total_pos = sum(
            1 for d in dishes.values() for c in d["candidates"]
            if build_label(c, strategy) == 1
        )
        total_labeled = sum(
            1 for d in dishes.values() for c in d["candidates"]
            if build_label(c, strategy) is not None
        )
        print(f"\n--- Strategy: {strategy} ---")
        print(f"  Positive rate in pool: {total_pos}/{total_labeled} = {total_pos/total_labeled:.3f}")

        sys_metrics = {
            "BM25":          {"p3": [], "p5": [], "ndcg5": [], "avg_npmi": []},
            "RAG+Ontology":  {"p3": [], "p5": [], "ndcg5": [], "avg_npmi": []},
        }

        for did, d in dishes.items():
            candidates = d["candidates"]
            dish_data = ont._dishes.get(did, {})
            core_ids = set(dish_data.get("core_ids", []))

            # Build labeled pool (drop missing)
            pool = []
            for c in candidates:
                label = build_label(c, strategy)
                if label is None:
                    continue
                pool.append({
                    "candidate_id": c["candidate_id"],
                    "candidate_name": c["candidate_name"],
                    "label": label,
                })

            if not pool or sum(x["label"] for x in pool) == 0:
                continue  # no positives → skip

            # Score each candidate under each system
            for entry in pool:
                cid = entry["candidate_id"]
                entry["score_bm25"] = score_bm25(cid, dish_data)
                entry["score_ont"] = score_ontology(
                    cid, core_ids, npmi, ont._flavor_category_ids
                )

            # Rank by score → get label sequence
            ranked_bm25 = sorted(pool, key=lambda x: x["score_bm25"], reverse=True)
            ranked_ont = sorted(pool, key=lambda x: x["score_ont"], reverse=True)

            labels_bm25 = [x["label"] for x in ranked_bm25]
            labels_ont = [x["label"] for x in ranked_ont]

            k_pool = min(5, len(pool))  # can't exceed pool size

            sys_metrics["BM25"]["p3"].append(precision_at_k(labels_bm25, 3))
            sys_metrics["BM25"]["p5"].append(precision_at_k(labels_bm25, k_pool))
            sys_metrics["BM25"]["ndcg5"].append(ndcg_at_k(labels_bm25, k_pool))

            sys_metrics["RAG+Ontology"]["p3"].append(precision_at_k(labels_ont, 3))
            sys_metrics["RAG+Ontology"]["p5"].append(precision_at_k(labels_ont, k_pool))
            sys_metrics["RAG+Ontology"]["ndcg5"].append(ndcg_at_k(labels_ont, k_pool))

            # Avg NPMI of top-5 predictions (RAG+Ontology)
            top5_ont_ids = [x["candidate_id"] for x in ranked_ont[:5]]
            npmi_vals = []
            for cid in top5_ont_ids:
                for core_id in core_ids:
                    v = npmi.get(core_id, {}).get(cid) or npmi.get(cid, {}).get(core_id)
                    if v is not None:
                        npmi_vals.append(v)
            sys_metrics["RAG+Ontology"]["avg_npmi"].append(
                sum(npmi_vals) / len(npmi_vals) if npmi_vals else 0.0
            )

            top5_bm25_ids = [x["candidate_id"] for x in ranked_bm25[:5]]
            npmi_vals_bm25 = []
            for cid in top5_bm25_ids:
                for core_id in core_ids:
                    v = npmi.get(core_id, {}).get(cid) or npmi.get(cid, {}).get(core_id)
                    if v is not None:
                        npmi_vals_bm25.append(v)
            sys_metrics["BM25"]["avg_npmi"].append(
                sum(npmi_vals_bm25) / len(npmi_vals_bm25) if npmi_vals_bm25 else 0.0
            )

        def avg(lst):
            return round(sum(lst) / len(lst), 4) if lst else 0.0

        strategy_result = {}
        n_dishes_eval = len(sys_metrics["BM25"]["p5"])
        print(f"  Dishes evaluated: {n_dishes_eval}")
        print(f"\n  {'System':<20} {'P@3':>8} {'P@5':>8} {'NDCG@5':>10} {'Avg NPMI':>10}")
        print("  " + "-" * 60)

        # Random baseline
        pos_rate = total_pos / total_labeled
        print(f"  {'Random (pool)':<20} {pos_rate:>8.4f} {pos_rate:>8.4f} {'—':>10} {'—':>10}")

        for sys_name, m in sys_metrics.items():
            r = {
                "Precision@3": avg(m["p3"]),
                "Precision@5": avg(m["p5"]),
                "NDCG@5":      avg(m["ndcg5"]),
                "Avg_NPMI":    avg(m["avg_npmi"]),
                "n_dishes":    len(m["p5"]),
            }
            strategy_result[sys_name] = r
            print(f"  {sys_name:<20} {r['Precision@3']:>8} {r['Precision@5']:>8} "
                  f"{r['NDCG@5']:>10} {r['Avg_NPMI']:>10}")

        # Delta vs random baseline
        ont_p5 = strategy_result["RAG+Ontology"]["Precision@5"]
        bm25_p5 = strategy_result["BM25"]["Precision@5"]
        print(f"\n  RAG+Ontology vs Random: {ont_p5 - pos_rate:+.4f} P@5")
        print(f"  RAG+Ontology vs BM25:   {ont_p5 - bm25_p5:+.4f} P@5")

        results_by_strategy[strategy] = strategy_result

    # Save
    output = {
        "protocol": "ranking_within_annotation_pool",
        "iaa": iaa,
        "results": results_by_strategy,
        "note": (
            "For each dish, systems rank the ~8 annotated candidates by their score. "
            "Metrics (P@k, NDCG@k) are computed on this ranked list against annotation labels. "
            "conservative = both annotators agree label=1; "
            "lenient = at least one annotator says label=1."
        ),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "ir_task2_annotation_eval.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"\nResults → {out_path}")
    print("\nDone.")


if __name__ == "__main__":
    main()
