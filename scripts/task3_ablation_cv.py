#!/usr/bin/env python3
"""Task 3: Ablation + Cross-validation weight tuning with ranking metrics.

Compares configurations:
  A: Jaccard only
  B: Jaccard + ClassOverlap
  C: Jaccard + ClassOverlap + MethodMatch
  D: Jaccard + ClassOverlap + MethodMatch + SemanticSim (full)
  E: No Jaccard (ClassOverlap + MethodMatch + SemanticSim)
  F: No ClassOverlap
  G: No MethodMatch
  H: No SemanticSim

For each config: 5-fold CV on 1,600 judge pairs, optimize weights via Nelder-Mead.
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
JUDGE_PATH = ROOT / "evaluation" / "outputs" / "llm_judge_task3_3judges.json"
OUTPUT_PATH = ROOT / "evaluation" / "outputs" / "task3_ablation_cv_results.json"

ont = FoodOntology()

# ── Load data ────────────────────────────────────────────────────

dish_meta = {}
with open(GT_PATH, encoding="utf-8") as f:
    for line in f:
        e = json.loads(line)
        dish_meta[e["dish_id"]] = e["ingredient_ids"]

judges = json.loads(JUDGE_PATH.read_text("utf-8"))
judge_pairs = [(it["query_dish_id"], it["candidate_dish_id"], it["new_mean_3j"])
               for it in judges["items"]
               if it["query_dish_id"] in dish_meta and it["candidate_dish_id"] in dish_meta]
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

    return np.array([jaccard, class_overlap, method_match, semantic])


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

# mask: which components are active [jaccard, class_overlap, method_match, semantic]
CONFIGS = {
    "A: Jaccard only":           [1, 0, 0, 0],
    "B: Jaccard+Class":          [1, 1, 0, 0],
    "C: Jaccard+Class+Method":   [1, 1, 1, 0],
    "D: Full (all 4)":           [1, 1, 1, 1],
    "E: No Jaccard":             [0, 1, 1, 1],
    "F: No ClassOverlap":        [1, 0, 1, 1],
    "G: No MethodMatch":         [1, 1, 0, 1],
    "H: No SemanticSim":         [1, 1, 1, 0],
}

# ── 5-fold CV ────────────────────────────────────────────────────

def optimize_weights(train_anchors, mask):
    """Optimize weights on train anchors, return normalized weights."""
    active = [i for i, m in enumerate(mask) if m]
    if len(active) == 1:
        w = np.zeros(4)
        w[active[0]] = 1.0
        return w

    def neg_spearman(raw_w):
        w = np.zeros(4)
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
    w = np.zeros(4)
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

    print(f"  Weights (mean): α={mean_weights[0]:.3f} β={mean_weights[1]:.3f} γ={mean_weights[2]:.3f} δ={mean_weights[3]:.3f}")
    print(f"  P@5:    {mean_metrics['P@5']:.4f} ± {std_metrics['P@5']:.4f}")
    print(f"  NDCG@5: {mean_metrics['NDCG@5']:.4f} ± {std_metrics['NDCG@5']:.4f}")
    print(f"  MRR@5:  {mean_metrics['MRR@5']:.4f} ± {std_metrics['MRR@5']:.4f}")

    all_results[config_name] = {
        "mask": mask,
        "mean_weights": {"alpha": mean_weights[0], "beta": mean_weights[1],
                         "gamma": mean_weights[2], "delta": mean_weights[3]},
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
print(f"\nBEST: {best[0]}")
print(f"  Recommended weights: α={best[1]['mean_weights']['alpha']:.4f}, "
      f"β={best[1]['mean_weights']['beta']:.4f}, "
      f"γ={best[1]['mean_weights']['gamma']:.4f}, "
      f"δ={best[1]['mean_weights']['delta']:.4f}")

# ── Save ─────────────────────────────────────────────────────────

output = {
    "method": "5-fold CV, Nelder-Mead optimization, Spearman objective",
    "n_anchors": len(anchors),
    "n_pairs": len(judge_pairs),
    "positive_threshold": POSITIVE_THRESHOLD,
    "configs": all_results,
    "best_config": best[0],
    "best_weights": best[1]["mean_weights"],
}
OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False), "utf-8")
print(f"\nSaved → {OUTPUT_PATH}")
