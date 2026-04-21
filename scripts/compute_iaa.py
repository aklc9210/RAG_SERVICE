"""Compute Inter-Annotator Agreement (IAA) for LLM-judge Task 3."""
import csv
import numpy as np
from collections import Counter

CSV_PATH = "evaluation/outputs/llm_judge_task3_results.csv"

def load_ratings(path):
    """Return N×4 array of ratings (0,1,2)."""
    rows = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            scores = [
                int(r["score_qwen2_5_7b"]),
                int(r["score_llama3_1_8b"]),
                int(r["score_gemma2_9b"]),
                int(r["score_mistral_7b"]),
            ]
            rows.append(scores)
    return np.array(rows)

def fleiss_kappa(ratings):
    """Fleiss' kappa for N items, n raters, k categories."""
    N, n = ratings.shape
    cats = sorted(set(ratings.flatten()))
    k = len(cats)
    cat_map = {c: i for i, c in enumerate(cats)}

    # Build N×k count matrix
    table = np.zeros((N, k), dtype=int)
    for i in range(N):
        for j in range(n):
            table[i, cat_map[ratings[i, j]]] += 1

    # P_i for each item
    P_i = (np.sum(table ** 2, axis=1) - n) / (n * (n - 1))
    P_bar = np.mean(P_i)

    # P_e
    p_j = np.sum(table, axis=0) / (N * n)
    P_e = np.sum(p_j ** 2)

    kappa = (P_bar - P_e) / (1 - P_e) if P_e < 1 else 0
    return kappa, P_bar, P_e

def krippendorff_alpha(ratings, level="ordinal"):
    """Krippendorff's alpha (nominal or ordinal)."""
    N, n = ratings.shape
    cats = sorted(set(ratings.flatten()))
    k = len(cats)

    # Build coincidence matrix
    coinc = np.zeros((k, k))
    cat_map = {c: i for i, c in enumerate(cats)}
    for i in range(N):
        pairs = []
        for a in range(n):
            for b in range(a + 1, n):
                ca = cat_map[ratings[i, a]]
                cb = cat_map[ratings[i, b]]
                coinc[ca, cb] += 1
                coinc[cb, ca] += 1

    # Observed disagreement
    n_pairs = N * n * (n - 1) / 2
    if level == "nominal":
        D_o = 1 - np.trace(coinc) / coinc.sum()
    else:  # ordinal
        D_o = 0
        total = coinc.sum()
        for c in range(k):
            for d in range(k):
                if c != d:
                    D_o += coinc[c, d] * (c - d) ** 2
        D_o /= total

    # Expected disagreement
    marginals = coinc.sum(axis=1)
    total = marginals.sum()
    if level == "nominal":
        D_e = 1 - np.sum(marginals ** 2) / (total ** 2)
    else:
        D_e = 0
        for c in range(k):
            for d in range(k):
                if c != d:
                    D_e += marginals[c] * marginals[d] * (c - d) ** 2
        D_e /= (total * (total - 1))

    alpha = 1 - D_o / D_e if D_e > 0 else 0
    return alpha

def pairwise_agreement(ratings):
    """Percentage of exact agreement for each judge pair."""
    n = ratings.shape[1]
    names = ["qwen2.5", "llama3.1", "gemma2", "mistral"]
    results = {}
    for i in range(n):
        for j in range(i + 1, n):
            agree = np.mean(ratings[:, i] == ratings[:, j])
            results[f"{names[i]} vs {names[j]}"] = round(agree, 4)
    return results

if __name__ == "__main__":
    ratings = load_ratings(CSV_PATH)
    print(f"Loaded {ratings.shape[0]} items × {ratings.shape[1]} judges")
    print(f"Score distribution: {dict(Counter(ratings.flatten()))}\n")

    kappa, P_bar, P_e = fleiss_kappa(ratings)
    print(f"Fleiss' κ = {kappa:.4f}  (P_bar={P_bar:.4f}, P_e={P_e:.4f})")

    alpha_nom = krippendorff_alpha(ratings, level="nominal")
    alpha_ord = krippendorff_alpha(ratings, level="ordinal")
    print(f"Krippendorff's α (nominal) = {alpha_nom:.4f}")
    print(f"Krippendorff's α (ordinal) = {alpha_ord:.4f}\n")

    print("Pairwise exact agreement:")
    for pair, agree in pairwise_agreement(ratings).items():
        print(f"  {pair}: {agree:.1%}")
