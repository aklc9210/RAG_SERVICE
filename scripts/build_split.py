#!/usr/bin/env python3
"""
Create reproducible train/test split from processed dish IDs.

Reads:
    processed/dishes/*.json  — all dish files

Writes:
    data/splits/train_ids.txt  — 80% dish IDs (one per line)
    data/splits/test_ids.txt   — 20% dish IDs (one per line)
    data/splits/split_stats.json

Usage:
    python scripts/build_split.py
    python scripts/build_split.py --seed 42 --test-ratio 0.2
"""

import argparse
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DISHES_DIR = ROOT / "processed" / "dishes"
SPLITS_DIR = ROOT / "data" / "splits"


def parse_args():
    parser = argparse.ArgumentParser(description="Build train/test split.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--test-ratio", type=float, default=0.2, help="Test set ratio (default: 0.2)")
    return parser.parse_args()


def main():
    args = parse_args()

    print("=== Building Train/Test Split ===")
    print(f"Seed      : {args.seed}")
    print(f"Test ratio: {args.test_ratio}")

    # Collect all dish IDs from processed/dishes/
    dish_files = sorted(DISHES_DIR.glob("*.json"))
    all_ids = []
    for f in dish_files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            all_ids.append(data["id"])
        except Exception as e:
            print(f"  Warning: skipping {f.name} — {e}")

    print(f"\nTotal dishes found: {len(all_ids)}")

    # Shuffle deterministically
    rng = random.Random(args.seed)
    shuffled = all_ids[:]
    rng.shuffle(shuffled)

    n_test = int(len(shuffled) * args.test_ratio)
    n_train = len(shuffled) - n_test

    test_ids = sorted(shuffled[:n_test])    # sort for readability
    train_ids = sorted(shuffled[n_test:])

    # Write output
    SPLITS_DIR.mkdir(parents=True, exist_ok=True)

    train_path = SPLITS_DIR / "train_ids.txt"
    test_path = SPLITS_DIR / "test_ids.txt"
    stats_path = SPLITS_DIR / "split_stats.json"

    train_path.write_text("\n".join(train_ids) + "\n", encoding="utf-8")
    test_path.write_text("\n".join(test_ids) + "\n", encoding="utf-8")

    stats = {
        "seed": args.seed,
        "test_ratio": args.test_ratio,
        "total": len(all_ids),
        "n_train": n_train,
        "n_test": n_test,
    }
    stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")

    print(f"  Train : {n_train} dishes → {train_path}")
    print(f"  Test  : {n_test} dishes  → {test_path}")
    print(f"  Stats : {stats_path}")
    print("\nDone.")


if __name__ == "__main__":
    main()
