#!/usr/bin/env python3
"""
Day 3 — Task 3: Hierarchy-aware Dish Similarity Evaluation

Compute similarity between dish pairs using:
  Sim(A, B) = α·IDF-Jaccard + β·ClassOverlap + γ·CookingMethodMatch

Workflow:
  1. Load GT pairs from task3_related_gt.jsonl
  2. Tune α, β, γ on 50 random pairs (maximize Pearson correlation)
  3. Evaluate on all pairs
  4. Save results to evaluation/outputs/task3_hierarchy_similarity_results.json

Usage:
    python scripts/task3_hierarchy_similarity.py
"""

import json
import random
import sys
from pathlib import Path
from typing import List, Dict, Tuple

import numpy as np
from scipy.stats import pearsonr, spearmanr

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from retrieval.ontology import FoodOntology

GT_PATH = ROOT / "evaluation" / "data" / "datasets" / "task3_related_gt.jsonl"
KB_PATH = ROOT / "app" / "data" / "knowledge_base" / "dish_knowledge_base.json"
OUTPUT_PATH = ROOT / "evaluation" / "outputs" / "task3_hierarchy_similarity_results.json"


class Task3Evaluator:
    """Compute and evaluate hierarchy-aware dish similarity."""

    def __init__(self):
        self.ontology = FoodOntology()
        self.pairs: List[Tuple[str, str, float]] = []
        self.dish_meta: Dict[str, dict] = {}
        self._load_data()

    def _load_data(self):
        """Load GT pairs and dish metadata from task3_related_gt.jsonl."""
        with open(GT_PATH, encoding="utf-8") as f:
            for line in f:
                entry = json.loads(line)
                dish_id = entry["dish_id"]
                self.dish_meta[dish_id] = {
                    "name": entry["dish_name"],
                    "category": entry["category"],
                    "ingredient_ids": entry["ingredient_ids"],
                }
                for rel in entry.get("related", []):
                    rel_id = rel["dish_id"]
                    gt_sim = rel["relatedness"]
                    self.pairs.append((dish_id, rel_id, gt_sim))

        print(f"[OK] Loaded {len(self.pairs)} GT pairs from {len(self.dish_meta)} dishes")

    def _idf_jaccard(self, ings_a: List[str], ings_b: List[str]) -> float:
        """Jaccard similarity on ingredient IDs."""
        if not ings_a or not ings_b:
            return 0.0
        set_a = set(ings_a)
        set_b = set(ings_b)
        union_size = len(set_a | set_b)
        if union_size == 0:
            return 0.0
        return len(set_a & set_b) / union_size

    def _class_overlap(self, ings_a: List[str], ings_b: List[str]) -> float:
        """Class-based overlap from ontology (reuse builtin method)."""
        return self.ontology.ingredient_class_overlap(ings_a, ings_b)

    def _cooking_method_match(self, dish_a_id: str, dish_b_id: str) -> float:
        """Cooking method match (1.0 if same, else 0.0)."""
        return self.ontology.cooking_method_match(dish_a_id, dish_b_id)

    def compute_components(
        self, dish_a_id: str, dish_b_id: str
    ) -> Dict[str, float]:
        """Compute similarity components without weighting."""
        ings_a = self.dish_meta[dish_a_id]["ingredient_ids"]
        ings_b = self.dish_meta[dish_b_id]["ingredient_ids"]

        return {
            "idf_jaccard": self._idf_jaccard(ings_a, ings_b),
            "class_overlap": self._class_overlap(ings_a, ings_b),
            "cooking_method_match": self._cooking_method_match(dish_a_id, dish_b_id),
        }

    def compute_similarity(
        self, components: Dict[str, float], alpha: float, beta: float, gamma: float
    ) -> float:
        """Weighted combination of components."""
        return (
            alpha * components["idf_jaccard"]
            + beta * components["class_overlap"]
            + gamma * components["cooking_method_match"]
        )

    def tune_weights(self, sample_size: int = 50) -> Tuple[float, float, float]:
        """
        Tune α, β, γ on sample pairs to maximize Pearson correlation.
        Returns best (α, β, γ).
        """
        random.seed(42)
        sample_pairs = random.sample(self.pairs, min(sample_size, len(self.pairs)))

        # Pre-compute components for sample
        sample_components = []
        for dish_a, dish_b, gt in sample_pairs:
            comps = self.compute_components(dish_a, dish_b)
            sample_components.append((comps, gt))

        print(f"\n[TUNING] Tuning weights on {len(sample_pairs)} sample pairs...")

        # Try weight combinations
        weight_combos = [
            (0.3, 0.4, 0.3),
            (0.4, 0.3, 0.3),
            (0.25, 0.5, 0.25),
            (0.33, 0.33, 0.34),
            (0.2, 0.6, 0.2),
            (0.5, 0.25, 0.25),
            (0.35, 0.35, 0.3),
            (0.4, 0.4, 0.2),
            (0.3, 0.5, 0.2),
            (0.2, 0.7, 0.1),
        ]

        best_corr = -2.0
        best_weights = (0.33, 0.33, 0.34)

        for alpha, beta, gamma in weight_combos:
            preds = []
            gts = []
            for comps, gt in sample_components:
                pred = self.compute_similarity(comps, alpha, beta, gamma)
                preds.append(pred)
                gts.append(gt)

            try:
                corr, _ = pearsonr(gts, preds)
                print(
                    f"  a={alpha:.2f}, b={beta:.2f}, c={gamma:.2f} -> "
                    f"Pearson r = {corr:.4f}"
                )
                if corr > best_corr:
                    best_corr = corr
                    best_weights = (alpha, beta, gamma)
            except Exception as e:
                print(
                    f"  a={alpha:.2f}, b={beta:.2f}, c={gamma:.2f} -> "
                    f"Error: {e}"
                )

        print(
            f"\n[BEST] Best weights: alpha={best_weights[0]:.2f}, "
            f"beta={best_weights[1]:.2f}, gamma={best_weights[2]:.2f}"
        )
        print(f"  Tuning Pearson r: {best_corr:.4f}")
        return best_weights

    def evaluate(
        self, alpha: float, beta: float, gamma: float
    ) -> Dict:
        """Evaluate on all pairs, compute metrics."""
        print(
            f"\n[EVAL] Evaluating on {len(self.pairs)} pairs "
            f"with alpha={alpha:.2f}, beta={beta:.2f}, gamma={gamma:.2f}..."
        )

        results_list = []
        preds = []
        gts = []

        for pair_idx, (dish_a, dish_b, gt) in enumerate(self.pairs):
            comps = self.compute_components(dish_a, dish_b)
            pred = self.compute_similarity(comps, alpha, beta, gamma)
            preds.append(pred)
            gts.append(gt)

            results_list.append({
                "pair_id": pair_idx,
                "dish_a_id": dish_a,
                "dish_a_name": self.dish_meta[dish_a]["name"],
                "dish_b_id": dish_b,
                "dish_b_name": self.dish_meta[dish_b]["name"],
                "gt_similarity": gt,
                "predicted_similarity": pred,
                "components": comps,
            })

        # Compute metrics
        preds_arr = np.array(preds)
        gts_arr = np.array(gts)

        try:
            pearson_r, _ = pearsonr(gts_arr, preds_arr)
        except Exception:
            pearson_r = np.nan

        try:
            spearman_r, _ = spearmanr(gts_arr, preds_arr)
        except Exception:
            spearman_r = np.nan

        mae = float(np.mean(np.abs(preds_arr - gts_arr)))
        rmse = float(np.sqrt(np.mean((preds_arr - gts_arr) ** 2)))

        metrics = {
            "pearson_correlation": float(pearson_r),
            "spearman_correlation": float(spearman_r),
            "mae": mae,
            "rmse": rmse,
        }

        print(f"  Pearson r: {pearson_r:.4f}")
        print(f"  Spearman rho: {spearman_r:.4f}")
        print(f"  MAE: {mae:.4f}")
        print(f"  RMSE: {rmse:.4f}")

        return {
            "metadata": {
                "variant": "RAG+Ontology",
                "alpha": alpha,
                "beta": beta,
                "gamma": gamma,
                "total_pairs": len(results_list),
            },
            "results": results_list,
            "metrics": metrics,
        }


def main():
    """Run Task 3 evaluation."""
    evaluator = Task3Evaluator()

    # Step 1: Tune weights on 50 sample pairs
    alpha, beta, gamma = evaluator.tune_weights(sample_size=50)

    # Step 2: Evaluate on all pairs
    output_data = evaluator.evaluate(alpha, beta, gamma)

    # Step 3: Save results
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\n[OK] Results saved to {OUTPUT_PATH}")
    print(f"\n[SUMMARY] Task 3 Evaluation Summary:")
    print(f"  Variant: {output_data['metadata']['variant']}")
    print(f"  Total pairs: {output_data['metadata']['total_pairs']}")
    print(f"  Weights: alpha={alpha:.2f}, beta={beta:.2f}, gamma={gamma:.2f}")
    print(f"  Pearson r: {output_data['metrics']['pearson_correlation']:.4f}")
    print(f"  Spearman rho: {output_data['metrics']['spearman_correlation']:.4f}")
    print(f"  MAE: {output_data['metrics']['mae']:.4f}")
    print(f"  RMSE: {output_data['metrics']['rmse']:.4f}")


if __name__ == "__main__":
    main()
