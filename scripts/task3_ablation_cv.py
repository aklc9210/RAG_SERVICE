#!/usr/bin/env python3
"""Task 3: Ablation + Cross-validation weight tuning with ranking metrics.

Compares configurations (5 components):
  A: Jaccard only
  B: + ClassOverlap
  C: + MethodMatch
  D: + SemanticSim
  E: Full (all 5: J + C + M + S + Flavor)
  F: No Jaccard
  G: No ClassOverlap
  H: No MethodMatch
  I: No SemanticSim
  J: No Flavor

For each config: 5-fold CV on judge pairs, optimize weights via Nelder-Mead.
Metrics: P@5, NDCG@5, MRR@5 (positive threshold: judge mean >= 1.0)
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from retrieval.ontology import FoodOntology

GT_PATH = ROOT / "evaluation" / "data" / "datasets" / "task3_related_gt.jsonl"
JUDGE_PATH = ROOT / "evaluation" / "outputs" / "task3_diverse_judged.json"
OUTPUT_PATH = ROOT / "evaluation" / "outputs" / "task3_ablation_cv_results.json"

ont = FoodOntology()

# ── Load data ────────────────────────────────────────────────────

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

# Group by anchor for ranking metrics
from collections import defaultdict
anchor_groups = defaultdict(list)
for a, b, score in judge_pairs:
    anchor_groups[a].append((b, score))
anchors = list(anchor_groups.keys())
print(f"Unique anchors: {len(anchors)}")

# ── Semantic matrices ────────────────────────────────────────────

SEMANTIC_PATH = ROOT / "app" / "config" / "ingredient_semantic_matrices_v2.json"
sem_matrices = {}
if SEMANTIC_PATH.exists():
    data = json.loads(SEMANTIC_PATH.read_text("utf-8"))
    for section in ["vegetables", "proteins", "binders", "seasonings"]:
        for ing, sims in data.get(section, {}).items():
            sem_matrices[ing] = sims

# ── Load ingredient importance from dish KB ──────────────────────

_dish_kb = {d["id"]: d for d in json.loads((ROOT / "app" / "data" / "knowledge_base" / "dish_knowledge_base.json").read_text("utf-8"))}

def get_ingredient_weights(dish_id):
    """Return {ingredient_id: weight} based on importance field.
    importance 3 (main) → weight 3.0, importance 2 → 1.5, importance 1 (seasoning) → 0.5
    """
    dish = _dish_kb.get(dish_id, {})
    weights = {}
    for ing in dish.get("ingredients", []):
        iid = ing.get("ingredient_id")
        imp = ing.get("importance", 1)
        weights[iid] = {3: 3.0, 2: 1.5}.get(imp, 0.5)
    return weights


# ── Component computation ────────────────────────────────────────

def compute_components(dish_a, dish_b):
    ings_a = dish_meta[dish_a]
    ings_b = dish_meta[dish_b]
    w_a = get_ingredient_weights(dish_a)
    w_b = get_ingredient_weights(dish_b)

    # Weighted Jaccard: Σw(shared) / Σw(union)
    set_a, set_b = set(ings_a), set(ings_b)
    shared = set_a & set_b
    union = set_a | set_b
    if union:
        w_shared = sum(max(w_a.get(i, 0.5), w_b.get(i, 0.5)) for i in shared)
        w_union = sum(max(w_a.get(i, 0.5), w_b.get(i, 0.5)) for i in union)
        jaccard = w_shared / w_union if w_union else 0.0
    else:
        jaccard = 0.0

    # Weighted ClassOverlap: greedy match, weighted by importance
    class_overlap = _weighted_class_overlap(ings_a, ings_b, w_a, w_b)

    # MethodMatch (unchanged)
    method_match = ont.cooking_method_match(dish_a, dish_b)

    # SemanticSim (unchanged)
    sims = []
    for a in ings_a:
        if a in sem_matrices:
            for b in ings_b:
                if b in sem_matrices[a]:
                    sims.append(sem_matrices[a][b])
    semantic = sum(sims) / len(sims) if sims else 0.0

    # FlavorComplement: fraction of cross-dish pairs that are complements
    flavor = ont.flavor_complement_score(ings_a, ings_b)

    return np.array([jaccard, class_overlap, method_match, semantic, flavor])


def _weighted_class_overlap(ings_a, ings_b, w_a, w_b):
    """Class overlap with importance weighting. Main ingredient matches count more."""
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


# Pre-compute all components per anchor
print("Pre-computing components...")
anchor_data = {}  # anchor -> [(candidate, score, components), ...]
for anchor in anchors:
    candidates = anchor_groups[anchor]
    items = []
    for cand_id, gt_score in candidates:
        comps = compute_components(anchor, cand_id)
        items.append((cand_id, gt_score, comps))
    anchor_data[anchor] = items
print("Done.")

# ── Ranking metrics ──────────────────────────────────────────────

POSITIVE_THRESHOLD = 1.0

def ranking_metrics(anchor_list, weights):
    """Compute P@5, NDCG@5, MRR@5 over a list of anchors."""
    p5_scores, ndcg5_scores, mrr5_scores = [], [], []

    for anchor in anchor_list:
        items = anchor_data[anchor]
        # Score and rank
        scored = [(gt, float(comps @ weights)) for _, gt, comps in items]
        scored.sort(key=lambda x: -x[1])  # rank by predicted score desc

        # Binary relevance: positive if judge mean >= threshold
        top5 = scored[:5]
        rels = [1 if gt >= POSITIVE_THRESHOLD else 0 for gt, _ in top5]

        # P@5
        p5_scores.append(sum(rels) / 5)

        # NDCG@5
        dcg = sum(r / math.log2(i + 2) for i, r in enumerate(rels))
        n_pos = sum(1 for gt, _ in scored if gt >= POSITIVE_THRESHOLD)
        ideal = sum(1 / math.log2(i + 2) for i in range(min(n_pos, 5)))
        ndcg5_scores.append(dcg / ideal if ideal > 0 else 0.0)

        # MRR@5
        mrr = 0.0
        for i, r in enumerate(rels):
            if r == 1:
                mrr = 1.0 / (i + 1)
                break
        mrr5_scores.append(mrr)

    return {
        "P@5": float(np.mean(p5_scores)),
        "NDCG@5": float(np.mean(ndcg5_scores)),
        "MRR@5": float(np.mean(mrr5_scores)),
    }

# ── Configurations ───────────────────────────────────────────────

# mask: which components are active [jaccard, class_overlap, method_match, semantic, flavor]
CONFIGS = {
    "A: Jaccard only":           [1, 0, 0, 0, 0],
    "B: +ClassOverlap":          [1, 1, 0, 0, 0],
    "C: +MethodMatch":           [1, 1, 1, 0, 0],
    "D: +SemanticSim":           [1, 1, 1, 1, 0],
    "E: Full (all 5)":           [1, 1, 1, 1, 1],
    "F: No Jaccard":             [0, 1, 1, 1, 1],
    "G: No ClassOverlap":        [1, 0, 1, 1, 1],
    "H: No MethodMatch":         [1, 1, 0, 1, 1],
    "I: No SemanticSim":         [1, 1, 1, 0, 1],
    "J: No Flavor":              [1, 1, 1, 1, 0],
}

# ── 5-fold CV ────────────────────────────────────────────────────

def optimize_weights(train_anchors, mask):
    """Optimize weights on train anchors, return normalized weights."""
    n_components = 5
    active = [i for i, m in enumerate(mask) if m]
    if len(active) == 1:
        w = np.zeros(n_components)
        w[active[0]] = 1.0
        return w

    def neg_spearman(raw_w):
        w = np.zeros(n_components)
        for i, idx in enumerate(active):
            w[idx] = abs(raw_w[i])
        s = w.sum()
        if s == 0:
            return 0
        w /= s
        # Compute spearman over all pairs in train anchors
        all_gt, all_pred = [], []
        for anchor in train_anchors:
            for _, gt, comps in anchor_data[anchor]:
                all_gt.append(gt)
                all_pred.append(float(comps @ w))
        rho, _ = spearmanr(all_gt, all_pred)
        return -rho

    x0 = np.ones(len(active)) / len(active)
    result = minimize(neg_spearman, x0, method="Nelder-Mead",
                      options={"maxiter": 5000, "xatol": 0.005})
    w = np.zeros(n_components)
    for i, idx in enumerate(active):
        w[idx] = abs(result.x[i])
    w /= w.sum()
    return w


print(f"\n{'='*70}")
print(f"5-FOLD CROSS-VALIDATION ON {len(anchors)} ANCHORS")
print(f"{'='*70}")

rng = np.random.default_rng(42)
fold_indices = rng.permutation(len(anchors))
folds = np.array_split(fold_indices, 5)

all_results = {}

for config_name, mask in CONFIGS.items():
    print(f"\n--- {config_name} ---")
    fold_metrics = []
    fold_weights = []

    for fold_i in range(5):
        test_idx = folds[fold_i]
        train_idx = np.concatenate([folds[j] for j in range(5) if j != fold_i])

        train_anchors = [anchors[i] for i in train_idx]
        test_anchors = [anchors[i] for i in test_idx]

        # Optimize on train
        w = optimize_weights(train_anchors, mask)
        fold_weights.append(w.tolist())

        # Evaluate on test
        metrics = ranking_metrics(test_anchors, w)
        fold_metrics.append(metrics)

    # Aggregate
    mean_metrics = {k: float(np.mean([m[k] for m in fold_metrics])) for k in fold_metrics[0]}
    std_metrics = {k: float(np.std([m[k] for m in fold_metrics])) for k in fold_metrics[0]}
    mean_weights = np.mean(fold_weights, axis=0).tolist()

    print(f"  Weights (mean): a={mean_weights[0]:.3f} b={mean_weights[1]:.3f} g={mean_weights[2]:.3f} d={mean_weights[3]:.3f} e={mean_weights[4]:.3f}")
    print(f"  P@5:    {mean_metrics['P@5']:.4f} ± {std_metrics['P@5']:.4f}")
    print(f"  NDCG@5: {mean_metrics['NDCG@5']:.4f} ± {std_metrics['NDCG@5']:.4f}")
    print(f"  MRR@5:  {mean_metrics['MRR@5']:.4f} ± {std_metrics['MRR@5']:.4f}")

    all_results[config_name] = {
        "mask": mask,
        "mean_weights": {"alpha": mean_weights[0], "beta": mean_weights[1],
                         "gamma": mean_weights[2], "delta": mean_weights[3],
                         "epsilon": mean_weights[4]},
        "metrics_mean": mean_metrics,
        "metrics_std": std_metrics,
        "fold_weights": fold_weights,
        "fold_metrics": fold_metrics,
    }

# ── Summary table ────────────────────────────────────────────────

print(f"\n{'='*70}")
print(f"{'Config':<28} {'P@5':<12} {'NDCG@5':<12} {'MRR@5':<12}")
print(f"{'-'*70}")
for name, res in all_results.items():
    m = res["metrics_mean"]
    s = res["metrics_std"]
    print(f"{name:<28} {m['P@5']:.4f}±{s['P@5']:.3f}  {m['NDCG@5']:.4f}±{s['NDCG@5']:.3f}  {m['MRR@5']:.4f}±{s['MRR@5']:.3f}")

# Best config
best = max(all_results.items(), key=lambda x: x[1]["metrics_mean"]["NDCG@5"])
best_w = np.array([best[1]['mean_weights']['alpha'], best[1]['mean_weights']['beta'],
                   best[1]['mean_weights']['gamma'], best[1]['mean_weights']['delta'],
                   best[1]['mean_weights']['epsilon']])
print(f"\nBEST: {best[0]}")
print(f"  Recommended weights: a={best_w[0]:.4f}, b={best_w[1]:.4f}, g={best_w[2]:.4f}, d={best_w[3]:.4f}, e={best_w[4]:.4f}")

# ── System comparison: BM25, Dense, Dense+Ontology ───────────────

print(f"\n{'='*70}")
print("SYSTEM COMPARISON (using best weights from ablation)")
print(f"{'='*70}")

# BM25
from retrieval.bm25_retriever import BM25Retriever
print("\nBuilding BM25...")
bm25 = BM25Retriever()
bm25_rankings = {}
for i, anchor in enumerate(anchors):
    d = _dish_kb.get(anchor, {})
    name = d.get("name_vi", "")
    res = bm25.search(name, top_k=200)
    bm25_rankings[anchor] = {r["dish_id"]: 1.0 / (idx + 1) for idx, r in enumerate(res)}
    if (i + 1) % 50 == 0:
        print(f"  BM25: {i+1}/{len(anchors)}")

# Dense (embedding)
print("Building Dense (embedding)...")
from ingestion.embedding import EmbeddingModel
em = EmbeddingModel()
dishes_dir = ROOT / "processed" / "dishes"
corpus_ids = []
corpus_texts = []
for f in sorted(dishes_dir.glob("*.json")):
    try:
        d = json.loads(f.read_text("utf-8"))
    except:
        continue
    text = d.get("name_vi", "")
    ings = d.get("main_ingredients", []) + d.get("secondary_ingredients", [])
    if ings:
        text += " " + " ".join(ings[:10])
    corpus_ids.append(d["id"])
    corpus_texts.append(text)

print(f"  Embedding {len(corpus_ids)} dishes...")
all_vecs = []
for i in range(0, len(corpus_texts), 128):
    vecs = em.embed_documents(corpus_texts[i:i+128])
    all_vecs.extend(vecs)
corpus_matrix = np.array(all_vecs)
id_to_idx = {did: idx for idx, did in enumerate(corpus_ids)}

dense_rankings = {}
for i, anchor in enumerate(anchors):
    a_idx = id_to_idx.get(anchor)
    if a_idx is not None:
        qvec = corpus_matrix[a_idx]
    else:
        name = _dish_kb.get(anchor, {}).get("name_vi", "")
        qvec = np.array(em.embed_query(name))
    scores = (corpus_matrix @ qvec).flatten()
    cand_scores = {}
    for cand_id, _ in anchor_groups[anchor]:
        c_idx = id_to_idx.get(cand_id)
        cand_scores[cand_id] = float(scores[c_idx]) if c_idx is not None else 0.0
    dense_rankings[anchor] = cand_scores
    if (i + 1) % 50 == 0:
        print(f"  Dense: {i+1}/{len(anchors)}")

# Dense+Ontology: use pre-computed components with best weights
ontology_rankings = {}
for anchor in anchors:
    cand_scores = {}
    for cand_id, gt_score, comps in anchor_data[anchor]:
        cand_scores[cand_id] = float(comps @ best_w)
    ontology_rankings[anchor] = cand_scores

# Compute metrics for each system
def system_metrics(rankings):
    p5_list, ndcg5_list, mrr5_list = [], [], []
    for anchor in anchors:
        candidates = anchor_groups[anchor]
        r = rankings.get(anchor, {})
        sorted_cands = sorted(candidates, key=lambda x: r.get(x[0], 0), reverse=True)
        top5 = sorted_cands[:5]
        rels = [1 if gt >= POSITIVE_THRESHOLD else 0 for _, gt in top5]
        p5_list.append(sum(rels) / 5)
        dcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(rels))
        n_pos = sum(1 for _, gt in sorted_cands if gt >= POSITIVE_THRESHOLD)
        ideal = sum(1 / math.log2(i + 2) for i in range(min(n_pos, 5)))
        ndcg5_list.append(dcg / ideal if ideal > 0 else 0.0)
        mrr = 0.0
        for i, rel in enumerate(rels):
            if rel:
                mrr = 1.0 / (i + 1)
                break
        mrr5_list.append(mrr)
    return {"P@5": float(np.mean(p5_list)), "NDCG@5": float(np.mean(ndcg5_list)), "MRR@5": float(np.mean(mrr5_list))}

bm25_m = system_metrics(bm25_rankings)
dense_m = system_metrics(dense_rankings)
ont_m = system_metrics(ontology_rankings)

print(f"\n{'System':<18} {'P@5':<8} {'NDCG@5':<8} {'MRR@5':<8}")
print("-" * 42)
print(f"{'BM25':<18} {bm25_m['P@5']:.4f}  {bm25_m['NDCG@5']:.4f}  {bm25_m['MRR@5']:.4f}")
print(f"{'Dense':<18} {dense_m['P@5']:.4f}  {dense_m['NDCG@5']:.4f}  {dense_m['MRR@5']:.4f}")
print(f"{'Dense+Ontology':<18} {ont_m['P@5']:.4f}  {ont_m['NDCG@5']:.4f}  {ont_m['MRR@5']:.4f}")

# ── Save ─────────────────────────────────────────────────────────

output = {
    "method": "5-fold CV, Nelder-Mead optimization, Spearman objective",
    "n_anchors": len(anchors),
    "n_pairs": len(judge_pairs),
    "positive_threshold": POSITIVE_THRESHOLD,
    "configs": all_results,
    "best_config": best[0],
    "best_weights": best[1]["mean_weights"],
    "system_comparison": {"BM25": bm25_m, "Dense": dense_m, "Dense+Ontology": ont_m},
}
OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False), "utf-8")
print(f"\nSaved → {OUTPUT_PATH}")
