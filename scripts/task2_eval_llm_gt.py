#!/usr/bin/env python3
"""Task 2: Evaluate systems using LLM-judge mean score as ground truth.

Replaces human annotations (annotator_1, annotator_2) with llm_mean_score
from task2_human_annotation_v2.csv.

Evaluates 4 systems: BM25, BM25+Expansion, Dense, Dense+Ontology.
Reports P@K, NDCG@K, MRR@K.

GT: llm_mean_score column from annotation CSV, positive threshold >= 1.0.

Usage:
    python3 scripts/task2_eval_llm_gt.py           # K=5 (default)
    TASK_K=10 python3 scripts/task2_eval_llm_gt.py
    TASK_K=20 python3 scripts/task2_eval_llm_gt.py
"""
import csv
import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from retrieval.ontology import FoodOntology

# ── Paths ────────────────────────────────────────────────────────
HUMAN_FILE = ROOT / "evaluation" / "annotation" / "task2_human_annotation_v2.csv"
GT_PATH = ROOT / "evaluation" / "data" / "datasets" / "task3_related_gt.jsonl"

K = int(os.getenv("TASK_K", "5"))
POSITIVE_THRESHOLD = 1.0

LEGACY_WEIGHTS_PATH = ROOT / "evaluation" / "outputs" / "task3_ablation_cv_results_5comp.json"
DEFAULT_WEIGHTS_PATH = ROOT / "evaluation" / "outputs" / f"task3_ablation_cv_results_k{K}.json"
WEIGHTS_PATH = Path(os.getenv("WEIGHTS_PATH")) if os.getenv("WEIGHTS_PATH") else (
    LEGACY_WEIGHTS_PATH if K == 5 and LEGACY_WEIGHTS_PATH.exists() else DEFAULT_WEIGHTS_PATH
)

OUTPUT_PATH = ROOT / "evaluation" / "outputs" / f"task2_llm_eval_results_k{K}.json"

# ── Load LLM-judge pairs ─────────────────────────────────────────

def load_llm_pairs():
    """Load pairs using llm_mean_score as ground truth (ignoring human columns)."""
    rows = []
    with open(HUMAN_FILE, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    anchor_groups = defaultdict(list)
    skipped = 0
    for r in rows:
        llm_score_str = r.get("llm_mean_score", "").strip()
        if not llm_score_str:
            skipped += 1
            continue
        try:
            llm_score = float(llm_score_str)
        except ValueError:
            skipped += 1
            continue
        anchor_groups[r["anchor_dish_id"]].append((r["candidate_dish_id"], llm_score))

    n_pairs = sum(len(v) for v in anchor_groups.values())
    print(f"Loaded {n_pairs} pairs from {len(anchor_groups)} anchors (LLM GT, skipped={skipped})")
    return anchor_groups


# ── Load optimized weights ───────────────────────────────────────

def load_weights():
    data = json.loads(WEIGHTS_PATH.read_text("utf-8"))
    w = data["best_weights"]
    weights = np.array([w["alpha"], w["beta"], w["gamma"], w["delta"], w["epsilon"]])
    print(f"Loaded weights from {WEIGHTS_PATH.name}: {weights.round(4)}")
    return weights


# ── Component computation (same as ablation script) ──────────────

ont = FoodOntology()
_dish_kb = {d["id"]: d for d in json.loads(
    (ROOT / "app" / "data" / "knowledge_base" / "dish_knowledge_base.json").read_text("utf-8"))}

dish_meta = {}
with open(GT_PATH, encoding="utf-8") as f:
    for line in f:
        e = json.loads(line)
        dish_meta[e["dish_id"]] = e["ingredient_ids"]

SEMANTIC_PATH = ROOT / "app" / "config" / "ingredient_semantic_matrices_v2.json"
sem_matrices = {}
if SEMANTIC_PATH.exists():
    data = json.loads(SEMANTIC_PATH.read_text("utf-8"))
    for section in ["vegetables", "proteins", "binders", "seasonings"]:
        for ing, sims in data.get(section, {}).items():
            sem_matrices[ing] = sims


def get_ingredient_weights(dish_id):
    dish = _dish_kb.get(dish_id, {})
    return {ing.get("ingredient_id"): {3: 3.0, 2: 1.5}.get(ing.get("importance", 1), 0.5)
            for ing in dish.get("ingredients", [])}


def compute_components(dish_a, dish_b):
    ings_a = dish_meta.get(dish_a, [])
    ings_b = dish_meta.get(dish_b, [])
    if not ings_a or not ings_b:
        return np.zeros(5)
    w_a = get_ingredient_weights(dish_a)
    w_b = get_ingredient_weights(dish_b)

    set_a, set_b = set(ings_a), set(ings_b)
    shared = set_a & set_b
    union = set_a | set_b
    if union:
        w_shared = sum(max(w_a.get(i, 0.5), w_b.get(i, 0.5)) for i in shared)
        w_union = sum(max(w_a.get(i, 0.5), w_b.get(i, 0.5)) for i in union)
        jaccard = w_shared / w_union if w_union else 0.0
    else:
        jaccard = 0.0

    class_overlap = _weighted_class_overlap(ings_a, ings_b, w_a, w_b)
    method_match = ont.cooking_method_match(dish_a, dish_b)

    sims = []
    for a in ings_a:
        if a in sem_matrices:
            for b in ings_b:
                if b in sem_matrices[a]:
                    sims.append(sem_matrices[a][b])
    semantic = sum(sims) / len(sims) if sims else 0.0
    flavor = ont.flavor_complement_score(ings_a, ings_b)
    return np.array([jaccard, class_overlap, method_match, semantic, flavor])


def _weighted_class_overlap(ings_a, ings_b, w_a, w_b):
    if not ings_a or not ings_b:
        return 0.0
    score = 0.0
    total_weight = 0.0
    used_b = set()
    for a in ings_a:
        cls_a = ont.ing_to_class.get(a)
        if not cls_a:
            continue
        wa = w_a.get(a, 0.5)
        total_weight += wa
        best = 0.0
        best_j = None
        for j, b in enumerate(ings_b):
            if j in used_b:
                continue
            cls_b = ont.ing_to_class.get(b)
            if not cls_b:
                continue
            if cls_a == cls_b:
                s = 1.0
            elif ont.classes.get(cls_a, {}).get("parent") == ont.classes.get(cls_b, {}).get("parent"):
                s = 0.5
            else:
                continue
            if s > best:
                best = s
                best_j = j
        if best_j is not None:
            used_b.add(best_j)
            score += wa * best
    return score / total_weight if total_weight else 0.0


# ── Metrics ──────────────────────────────────────────────────────

def compute_ranking_metrics(anchor_groups, score_fn):
    """Compute P@K, NDCG@K, MRR@K using score_fn(anchor, candidate) -> float."""
    p_list, ndcg_list, mrr_list = [], [], []

    for anchor, candidates in anchor_groups.items():
        scored = [(cand, llm_gt, score_fn(anchor, cand)) for cand, llm_gt in candidates]
        scored.sort(key=lambda x: -x[2])
        topk = scored[:K]
        rels = [1 if gt >= POSITIVE_THRESHOLD else 0 for _, gt, _ in topk]

        p_list.append(sum(rels) / K)

        dcg = sum(r / math.log2(i + 2) for i, r in enumerate(rels))
        n_pos = sum(1 for _, gt, _ in scored if gt >= POSITIVE_THRESHOLD)
        ideal = sum(1 / math.log2(i + 2) for i in range(min(n_pos, K)))
        ndcg_list.append(dcg / ideal if ideal > 0 else 0.0)

        mrr = 0.0
        for i, r in enumerate(rels):
            if r:
                mrr = 1.0 / (i + 1)
                break
        mrr_list.append(mrr)

    k_label = str(K)
    return {
        f"P@{k_label}": round(float(np.mean(p_list)), 4),
        f"NDCG@{k_label}": round(float(np.mean(ndcg_list)), 4),
        f"MRR@{k_label}": round(float(np.mean(mrr_list)), 4),
    }


# ── Build systems ────────────────────────────────────────────────

def build_systems(anchor_groups, weights):
    all_anchors = list(anchor_groups.keys())
    all_candidates = set()
    for cands in anchor_groups.values():
        for c, _ in cands:
            all_candidates.add(c)

    # Pre-compute ontology components
    print("  Pre-computing ontology components...")
    ont_comps = {}
    for anchor in all_anchors:
        for cand, _ in anchor_groups[anchor]:
            ont_comps[(anchor, cand)] = compute_components(anchor, cand)

    # BM25
    print("  Building BM25...")
    from retrieval.bm25_retriever import BM25Retriever
    bm25 = BM25Retriever()

    # BM25+Expansion: ingredient KB for synonyms
    _ikb = json.loads((ROOT / "app" / "data" / "knowledge_base" /
                       "ingredient_knowledge_base.json").read_text("utf-8"))
    _keyword_to_names = {}
    for entry in _ikb:
        name = entry.get("name_vi", "").lower().strip()
        syns = [s.lower().strip() for s in (entry.get("synonyms") or [])]
        if name:
            _keyword_to_names[name] = syns + [name]
            for s in syns:
                _keyword_to_names.setdefault(s, []).append(name)

    # Dense embeddings
    print("  Building Dense embeddings...")
    from ingestion.embedding import EmbeddingModel
    em = EmbeddingModel()

    all_dish_ids = list(set(all_anchors) | all_candidates)
    dish_texts = {}
    for did in all_dish_ids:
        d = _dish_kb.get(did, {})
        text = d.get("name_vi", "")
        ings = [i.get("name_vi", "") for i in d.get("ingredients", [])[:10]]
        if ings:
            text += " " + " ".join(ings)
        dish_texts[did] = text

    print(f"  Embedding {len(all_dish_ids)} dishes...")
    texts_list = [dish_texts[did] for did in all_dish_ids]
    all_vecs = []
    for i in range(0, len(texts_list), 128):
        vecs = em.embed_documents(texts_list[i:i+128])
        all_vecs.extend(vecs)
    dish_vectors = {did: np.array(vec) for did, vec in zip(all_dish_ids, all_vecs)}

    # Cache BM25 results per anchor
    print("  Caching BM25 rankings...")
    bm25_cache = {}
    bm25_exp_cache = {}
    for anchor in all_anchors:
        d = _dish_kb.get(anchor, {})
        name = d.get("name_vi", "")
        results = bm25.search(name, top_k=200)
        bm25_cache[anchor] = {r["dish_id"]: 1.0 / (idx + 1) for idx, r in enumerate(results)}

        # Expanded query: dish name + ingredient names + synonyms
        query_parts = [name]
        for ing in d.get("ingredients", []):
            ing_name = ing.get("name_vi", "").lower().strip()
            if ing_name:
                query_parts.append(ing_name)
                query_parts.extend(_keyword_to_names.get(ing_name, [])[:3])
        results_exp = bm25.search(" ".join(query_parts), top_k=200)
        bm25_exp_cache[anchor] = {r["dish_id"]: 1.0 / (idx + 1) for idx, r in enumerate(results_exp)}

    def bm25_fn(anchor, cand):
        return bm25_cache.get(anchor, {}).get(cand, 0.0)

    def bm25_exp_fn(anchor, cand):
        return bm25_exp_cache.get(anchor, {}).get(cand, 0.0)

    def dense_fn(anchor, cand):
        va = dish_vectors.get(anchor)
        vb = dish_vectors.get(cand)
        if va is None or vb is None:
            return 0.0
        return float(va @ vb / (np.linalg.norm(va) * np.linalg.norm(vb) + 1e-9))

    def ontology_fn(anchor, cand):
        comps = ont_comps.get((anchor, cand), np.zeros(5))
        return float(comps @ weights)

    return {
        "BM25": bm25_fn,
        "BM25+Expansion": bm25_exp_fn,
        "Dense": dense_fn,
        "Dense+Ontology": ontology_fn,
    }


# ── Also compute ablation on LLM GT ──────────────────────────────

def compute_ablation_llm_gt(anchor_groups):
    """Compute ablation table (A–J) using LLM GT scores (same as run_ablation_5comp but
    on the annotation CSV subset, no CV — just report using pre-trained best weights)."""
    from evaluation.outputs import task3_ablation_cv_results_5comp  # noqa: not real import
    pass  # ablation uses the same weights file; full CV already in task3_ablation_cv_results_5comp.json


# ── Main ─────────────────────────────────────────────────────────

def main():
    print(f"Task 2 eval with LLM GT — K={K}")
    print("=" * 60)

    llm_groups = load_llm_pairs()
    weights = load_weights()

    print("\nBuilding systems...")
    systems = build_systems(llm_groups, weights)

    n_pairs = sum(len(v) for v in llm_groups.values())
    print(f"\nEvaluating on {n_pairs} LLM-annotated pairs ({len(llm_groups)} anchors)...")
    print(f"\n{'System':<18} {'P@'+str(K):<10} {'NDCG@'+str(K):<10} {'MRR@'+str(K):<10}")
    print("-" * 48)

    results = {}
    for sys_name, score_fn in systems.items():
        m = compute_ranking_metrics(llm_groups, score_fn)
        results[sys_name] = m
        print(f"{sys_name:<18} {m['P@'+str(K)]:<10} {m['NDCG@'+str(K)]:<10} {m['MRR@'+str(K)]:<10}")

    # Save
    output = {
        "method": "Weights trained on LLM labels, evaluated on LLM-judge GT (llm_mean_score)",
        "ground_truth": "llm_mean_score from task2_human_annotation_v2.csv",
        "n_anchors": len(llm_groups),
        "n_pairs": n_pairs,
        "positive_threshold": POSITIVE_THRESHOLD,
        "k": K,
        "weights_used": {k: float(v) for k, v in zip(
            ["alpha", "beta", "gamma", "delta", "epsilon"], weights)},
        "results": results,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False), "utf-8")
    print(f"\nSaved → {OUTPUT_PATH}")
    return output


if __name__ == "__main__":
    main()
