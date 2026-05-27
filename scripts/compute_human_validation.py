#!/usr/bin/env python3
"""Compute human annotation validation metrics for Task 3.

Combines the original 300 pairs + extra 204 pairs = 504 pairs total.
Computes:
  1. Inter-annotator agreement (Cohen's κ linear, exact agreement, adjacent agreement)
  2. Spearman/Kendall correlation between human consensus and LLM-judge mean
  3. LLM bias analysis (mean difference)
  4. Binarized recall at positive threshold (≥1)

These metrics are reported in Section 5.3 of the paper.

Usage:
    python scripts/compute_human_validation.py
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr, kendalltau

ROOT = Path(__file__).resolve().parent.parent

# ── Load both annotation files ───────────────────────────────────

def load_annotation_csv(path):
    """Load annotation CSV, return list of dicts with valid scores."""
    rows = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            a1 = r.get("annotator_1", "").strip()
            a2 = r.get("annotator_2", "").strip()
            if a1 == "" or a2 == "":
                continue
            try:
                rows.append({
                    "anchor_id": r["anchor_dish_id"],
                    "candidate_id": r["candidate_dish_id"],
                    "annotator_1": int(a1),
                    "annotator_2": int(a2),
                    "llm_mean": float(r["llm_mean_score"]),
                })
            except (ValueError, KeyError):
                continue
    return rows


CSV_PATH = ROOT / "evaluation" / "annotation" / "task2_human_annotation_v2.csv"

all_rows = load_annotation_csv(CSV_PATH)

print(f"Total pairs: {len(all_rows)}")

if len(all_rows) == 0:
    print("ERROR: No valid annotated pairs found!")
    sys.exit(1)

# ── Extract arrays ───────────────────────────────────────────────

a1_scores = np.array([r["annotator_1"] for r in all_rows])
a2_scores = np.array([r["annotator_2"] for r in all_rows])
llm_scores = np.array([r["llm_mean"] for r in all_rows])
human_consensus = (a1_scores + a2_scores) / 2.0

print(f"\n{'='*60}")
print(f"  INTER-ANNOTATOR AGREEMENT (N={len(all_rows)} pairs)")
print(f"{'='*60}")

# ── 1. Cohen's κ (linear weighted) ──────────────────────────────

def cohen_kappa_linear(y1, y2):
    """Compute Cohen's kappa with linear weighting for ordinal scale."""
    cats = sorted(set(y1) | set(y2))
    k = len(cats)
    cat_map = {c: i for i, c in enumerate(cats)}
    
    n = len(y1)
    # Confusion matrix
    conf = np.zeros((k, k))
    for a, b in zip(y1, y2):
        conf[cat_map[a], cat_map[b]] += 1
    conf /= n
    
    # Marginals
    row_sum = conf.sum(axis=1)
    col_sum = conf.sum(axis=0)
    
    # Weight matrix (linear)
    W = np.zeros((k, k))
    for i in range(k):
        for j in range(k):
            W[i, j] = abs(i - j) / (k - 1) if k > 1 else 0
    
    # Observed and expected disagreement
    p_o = np.sum(W * conf)
    p_e = np.sum(W * np.outer(row_sum, col_sum))
    
    kappa = 1 - p_o / p_e if p_e > 0 else 0
    return kappa


def cohen_kappa_nominal(y1, y2):
    """Compute Cohen's kappa (unweighted/nominal)."""
    cats = sorted(set(y1) | set(y2))
    k = len(cats)
    cat_map = {c: i for i, c in enumerate(cats)}
    
    n = len(y1)
    conf = np.zeros((k, k))
    for a, b in zip(y1, y2):
        conf[cat_map[a], cat_map[b]] += 1
    conf /= n
    
    p_o = np.trace(conf)
    row_sum = conf.sum(axis=1)
    col_sum = conf.sum(axis=0)
    p_e = np.sum(row_sum * col_sum)
    
    kappa = (p_o - p_e) / (1 - p_e) if p_e < 1 else 0
    return kappa


kappa_linear = cohen_kappa_linear(a1_scores, a2_scores)
kappa_nominal = cohen_kappa_nominal(a1_scores, a2_scores)

# Exact agreement
exact_agree = np.mean(a1_scores == a2_scores)

# Adjacent agreement (differ by at most 1)
adjacent_agree = np.mean(np.abs(a1_scores - a2_scores) <= 1)

print(f"\nCohen's κ (linear weighted): {kappa_linear:.4f}")
print(f"Cohen's κ (nominal):         {kappa_nominal:.4f}")
print(f"Exact agreement:             {exact_agree:.1%}")
print(f"Adjacent agreement (±1):     {adjacent_agree:.1%}")

# Score distribution per annotator
print(f"\nScore distribution:")
print(f"  Annotator 1: 0={np.sum(a1_scores==0)}, 1={np.sum(a1_scores==1)}, 2={np.sum(a1_scores==2)}")
print(f"  Annotator 2: 0={np.sum(a2_scores==0)}, 1={np.sum(a2_scores==1)}, 2={np.sum(a2_scores==2)}")
print(f"  Mean A1: {a1_scores.mean():.3f}, Mean A2: {a2_scores.mean():.3f}")

# ── 2. Human consensus vs LLM judges ────────────────────────────

print(f"\n{'='*60}")
print(f"  HUMAN CONSENSUS vs LLM JUDGES")
print(f"{'='*60}")

rho, p_rho = spearmanr(human_consensus, llm_scores)
tau, p_tau = kendalltau(human_consensus, llm_scores)

print(f"\nSpearman ρ: {rho:.4f} (p = {p_rho:.2e})")
print(f"Kendall τ:  {tau:.4f} (p = {p_tau:.2e})")

# Bias: LLM mean - human consensus mean
llm_mean = llm_scores.mean()
human_mean = human_consensus.mean()
bias = llm_mean - human_mean

print(f"\nMean scores:")
print(f"  Human consensus: {human_mean:.3f}")
print(f"  LLM judges:      {llm_mean:.3f}")
print(f"  LLM bias:        +{bias:.3f} (LLM rates higher)")

# ── 3. Binarized analysis at positive threshold ──────────────────

print(f"\n{'='*60}")
print(f"  BINARIZED ANALYSIS (threshold ≥ 1.0)")
print(f"{'='*60}")

THRESHOLD = 1.0

# Human positive: consensus >= 1.0
human_pos = human_consensus >= THRESHOLD
# LLM positive: mean >= 1.0
llm_pos = llm_scores >= THRESHOLD

# Recall: of human-positive pairs, how many does LLM also mark positive?
n_human_pos = human_pos.sum()
n_llm_pos = llm_pos.sum()
n_both_pos = (human_pos & llm_pos).sum()

recall = n_both_pos / n_human_pos if n_human_pos > 0 else 0
precision = n_both_pos / n_llm_pos if n_llm_pos > 0 else 0

print(f"\nHuman positive (consensus ≥ 1.0): {n_human_pos} ({n_human_pos/len(all_rows)*100:.0f}%)")
print(f"LLM positive (mean ≥ 1.0):        {n_llm_pos} ({n_llm_pos/len(all_rows)*100:.0f}%)")
print(f"Both positive:                     {n_both_pos}")
print(f"\nRecall (LLM catches human-relevant): {recall:.1%}")
print(f"Precision (LLM positive is human-relevant): {precision:.1%}")

# ── 4. Confusion matrix ─────────────────────────────────────────

print(f"\n{'='*60}")
print(f"  CONFUSION MATRIX (Human consensus binned vs LLM)")
print(f"{'='*60}")

# Bin human consensus into 0, 1, 2
human_binned = np.round(human_consensus).astype(int)
human_binned = np.clip(human_binned, 0, 2)

# Bin LLM into 0, 1, 2
llm_binned = np.round(llm_scores).astype(int)
llm_binned = np.clip(llm_binned, 0, 2)

conf = np.zeros((3, 3), dtype=int)
for h, l in zip(human_binned, llm_binned):
    conf[h, l] += 1

print(f"\n{'':>12} LLM=0  LLM=1  LLM=2")
for i in range(3):
    print(f"  Human={i}:  {conf[i,0]:>5}  {conf[i,1]:>5}  {conf[i,2]:>5}")

# ── 5. Save results ─────────────────────────────────────────────

OUTPUT_PATH = ROOT / "evaluation" / "outputs" / "task3_human_validation_results.json"

results = {
    "n_pairs_total": len(all_rows),
    "inter_annotator_agreement": {
        "cohen_kappa_linear": round(kappa_linear, 4),
        "cohen_kappa_nominal": round(kappa_nominal, 4),
        "exact_agreement": round(exact_agree, 4),
        "adjacent_agreement": round(adjacent_agree, 4),
    },
    "human_vs_llm": {
        "spearman_rho": round(rho, 4),
        "spearman_p": float(p_rho),
        "kendall_tau": round(tau, 4),
        "kendall_p": float(p_tau),
        "human_mean": round(human_mean, 4),
        "llm_mean": round(llm_mean, 4),
        "llm_bias": round(bias, 4),
    },
    "binarized_threshold_1.0": {
        "n_human_positive": int(n_human_pos),
        "n_llm_positive": int(n_llm_pos),
        "recall": round(recall, 4),
        "precision": round(precision, 4),
    },
    "score_distribution": {
        "annotator_1": {"0": int(np.sum(a1_scores==0)), "1": int(np.sum(a1_scores==1)), "2": int(np.sum(a1_scores==2))},
        "annotator_2": {"0": int(np.sum(a2_scores==0)), "1": int(np.sum(a2_scores==1)), "2": int(np.sum(a2_scores==2))},
    },
}

OUTPUT_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), "utf-8")
print(f"\n{'='*60}")
print(f"✓ Saved results → {OUTPUT_PATH}")
print(f"{'='*60}")
