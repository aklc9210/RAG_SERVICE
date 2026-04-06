#!/usr/bin/env python3
"""
Build PMI (Pointwise Mutual Information) scores from co-occurrence data.

Reads:
    app/data/cooccurrence/matrix.json    — co-occurrence counts: {ingre_id: {ingre_id: count}}
    app/data/cooccurrence/frequency.json — per-ingredient dish count: {ingre_id: count}
    app/data/cooccurrence/metadata.json  — {total_dishes: N}

Writes:
    app/data/cooccurrence/pmi.json       — {ingre_id: {ingre_id: pmi_score}}
    app/data/cooccurrence/pmi_stats.json — summary statistics

Formula:
    PMI(x, y) = log2( P(x,y) / (P(x) * P(y)) )
    P(x,y) = cooccurrence_count(x,y) / total_dishes
    P(x)   = frequency(x) / total_dishes

Usage:
    python scripts/build_pmi.py
    python scripts/build_pmi.py --min-cooccurrence 2  # filter rare pairs
"""

import argparse
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "app" / "data" / "cooccurrence"


def load_data():
    with open(DATA_DIR / "matrix.json", encoding="utf-8") as f:
        matrix = json.load(f)
    with open(DATA_DIR / "frequency.json", encoding="utf-8") as f:
        frequency = json.load(f)
    with open(DATA_DIR / "metadata.json", encoding="utf-8") as f:
        metadata = json.load(f)
    return matrix, frequency, metadata


def compute_pmi(matrix, frequency, total_dishes, min_cooccurrence=1):
    """
    Compute PMI for all pairs in the co-occurrence matrix.

    Returns:
        pmi: {ingre_id: {ingre_id: float}}  — only pairs with count >= min_cooccurrence
        stats: summary dict
    """
    pmi = {}
    n_pairs = 0
    n_positive = 0
    n_negative = 0
    pmi_values = []

    for x, neighbors in matrix.items():
        freq_x = frequency.get(x)
        if not freq_x:
            continue
        p_x = freq_x / total_dishes

        pmi[x] = {}
        for y, count in neighbors.items():
            if count < min_cooccurrence:
                continue
            freq_y = frequency.get(y)
            if not freq_y:
                continue

            p_y = freq_y / total_dishes
            p_xy = count / total_dishes

            pmi_val = math.log2(p_xy / (p_x * p_y))
            pmi[x][y] = round(pmi_val, 6)

            n_pairs += 1
            pmi_values.append(pmi_val)
            if pmi_val > 0:
                n_positive += 1
            else:
                n_negative += 1

        # Remove empty entries
        if not pmi[x]:
            del pmi[x]

    stats = {
        "total_dishes": total_dishes,
        "n_ingredients_with_pmi": len(pmi),
        "n_pairs": n_pairs,
        "n_positive_pmi": n_positive,
        "n_negative_pmi": n_negative,
        "min_cooccurrence_threshold": min_cooccurrence,
        "pmi_min": round(min(pmi_values), 4) if pmi_values else None,
        "pmi_max": round(max(pmi_values), 4) if pmi_values else None,
        "pmi_mean": round(sum(pmi_values) / len(pmi_values), 4) if pmi_values else None,
    }

    return pmi, stats


def parse_args():
    parser = argparse.ArgumentParser(description="Build PMI from co-occurrence data.")
    parser.add_argument(
        "--min-cooccurrence",
        type=int,
        default=1,
        help="Minimum co-occurrence count to include a pair (default: 1)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print("=== Building PMI ===")
    print(f"Min co-occurrence: {args.min_cooccurrence}")

    print("\nLoading data...")
    matrix, frequency, metadata = load_data()
    total_dishes = metadata["total_dishes"]
    print(f"  total_dishes  : {total_dishes}")
    print(f"  ingredients   : {len(frequency)}")
    print(f"  matrix entries: {len(matrix)}")

    print("\nComputing PMI...")
    pmi, stats = compute_pmi(matrix, frequency, total_dishes, args.min_cooccurrence)

    print(f"  PMI pairs computed : {stats['n_pairs']:,}")
    print(f"  PMI > 0 (plausible): {stats['n_positive_pmi']:,}")
    print(f"  PMI < 0 (rare)     : {stats['n_negative_pmi']:,}")
    print(f"  PMI range          : [{stats['pmi_min']}, {stats['pmi_max']}]")
    print(f"  PMI mean           : {stats['pmi_mean']}")

    out_pmi = DATA_DIR / "pmi.json"
    out_stats = DATA_DIR / "pmi_stats.json"

    print(f"\nWriting {out_pmi} ...")
    with open(out_pmi, "w", encoding="utf-8") as f:
        json.dump(pmi, f, ensure_ascii=False)
    size_mb = out_pmi.stat().st_size / 1024 / 1024
    print(f"  Written: {size_mb:.1f} MB")

    print(f"Writing {out_stats} ...")
    with open(out_stats, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print("\nDone.")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
