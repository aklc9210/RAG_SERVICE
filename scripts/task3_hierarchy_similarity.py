#!/usr/bin/env python3
"""
Day 3 — Task 3: Hierarchy-aware Dish Similarity Evaluation (Phase 2)

Compute similarity between dish pairs using:
  Sim(A, B) = α·IDF-Jaccard + β·ClassOverlap + γ·CookingMethodMatch + δ·IngredientSemantic

Workflow:
  1. Load GT pairs from task3_related_gt.jsonl
  2. Load semantic matrices from ingredient_semantic_matrices_v2.json
  3. Tune α, β, γ, δ on 50 random pairs (maximize Pearson correlation)
  4. Evaluate on all pairs
  5. Save results to evaluation/outputs/task3_hierarchy_similarity_results.json

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
SEMANTIC_MATRICES_PATH = ROOT / "app" / "config" / "ingredient_semantic_matrices_v2.json"


class Task3Evaluator:
    """Compute and evaluate hierarchy-aware dish similarity."""

    def __init__(self):
        self.ontology = FoodOntology()
        self.pairs: List[Tuple[str, str, float]] = []
        self.dish_meta: Dict[str, dict] = {}
        self.semantic_matrices: Dict[str, Dict[str, float]] = {}
        self._load_data()
        self._load_semantic_matrices()

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

    def _load_semantic_matrices(self):
        """Load ingredient semantic similarity matrices from v2 config."""
        if not SEMANTIC_MATRICES_PATH.exists():
            print(f"[WARN] {SEMANTIC_MATRICES_PATH} not found, semantic component disabled")
            return

        try:
            with open(SEMANTIC_MATRICES_PATH, encoding="utf-8") as f:
                data = json.load(f)
            
            # Build ingredient -> {similar_to -> similarity} map
            for section in ["vegetables", "proteins", "binders", "seasonings"]:
                if section not in data:
                    continue
                for ing_name, sim_dict in data[section].items():
                    self.semantic_matrices[ing_name] = sim_dict
            
            print(f"[OK] Loaded semantic matrices for {len(self.semantic_matrices)} ingredients")
        except Exception as e:
            print(f"[WARN] Error loading semantic matrices: {e}")


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

    def _ingredient_semantic(self, ings_a: List[str], ings_b: List[str]) -> float:
        """Compute semantic similarity between ingredient lists."""
        if not ings_a or not ings_b or not self.semantic_matrices:
            return 0.0
        
        similarities = []
        for ing_a in ings_a:
            if ing_a not in self.semantic_matrices:
                continue
            sim_dict = self.semantic_matrices[ing_a]
            for ing_b in ings_b:
                if ing_b in sim_dict:
                    similarities.append(sim_dict[ing_b])
        
        return sum(similarities) / len(similarities) if similarities else 0.0


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
            "ingredient_semantic": self._ingredient_semantic(ings_a, ings_b),
        }

    def compute_similarity(
        self, components: Dict[str, float], alpha: float, beta: float, gamma: float, delta: float = 0.0
    ) -> float:
        """Weighted combination of 4 components."""
        return (
            alpha * components["idf_jaccard"]
            + beta * components["class_overlap"]
            + gamma * components["cooking_method_match"]
            + delta * components["ingredient_semantic"]
        )

    def tune_weights(self, sample_size: int = 50) -> Tuple[float, float, float, float]:
        """
        Tune α, β, γ, δ on sample pairs to maximize Pearson correlation.
        Returns best (α, β, γ, δ).
        """
        random.seed(42)
        sample_pairs = random.sample(self.pairs, min(sample_size, len(self.pairs)))

        # Pre-compute components for sample
        sample_components = []
        for dish_a, dish_b, gt in sample_pairs:
            comps = self.compute_components(dish_a, dish_b)
            sample_components.append((comps, gt))

        print(f"\n[TUNING] Tuning weights on {len(sample_pairs)} sample pairs...")

        # Try weight combinations (4 components: alpha, beta, gamma, delta)
        weight_combos = [
            (0.3, 0.4, 0.2, 0.1),   # Phase 2 proposal
            (0.25, 0.4, 0.2, 0.15),  # variant 1
            (0.35, 0.35, 0.2, 0.1),  # variant 2
            (0.4, 0.3, 0.2, 0.1),    # variant 3
            (0.3, 0.4, 0.15, 0.15),  # variant 4
            (0.2, 0.5, 0.15, 0.15),  # variant 5
            (0.5, 0.25, 0.15, 0.1),  # Phase 1 baseline with semantic
            (0.25, 0.5, 0.15, 0.1),  # variant 6
        ]

        best_corr = -2.0
        best_weights = (0.3, 0.4, 0.2, 0.1)

        for alpha, beta, gamma, delta in weight_combos:
            preds = []
            gts = []
            for comps, gt in sample_components:
                pred = self.compute_similarity(comps, alpha, beta, gamma, delta)
                preds.append(pred)
                gts.append(gt)

            try:
                corr, _ = pearsonr(gts, preds)
                print(
                    f"  a={alpha:.2f}, b={beta:.2f}, c={gamma:.2f}, d={delta:.2f} -> "
                    f"Pearson r = {corr:.4f}"
                )
                if corr > best_corr:
                    best_corr = corr
                    best_weights = (alpha, beta, gamma, delta)
            except Exception as e:
                print(
                    f"  a={alpha:.2f}, b={beta:.2f}, c={gamma:.2f}, d={delta:.2f} -> "
                    f"Error: {e}"
                )

        print(
            f"\n[BEST] Best weights: alpha={best_weights[0]:.2f}, "
            f"beta={best_weights[1]:.2f}, gamma={best_weights[2]:.2f}, delta={best_weights[3]:.2f}"
        )
        print(f"  Tuning Pearson r: {best_corr:.4f}")
        return best_weights

    def evaluate(
        self, alpha: float, beta: float, gamma: float, delta: float
    ) -> Dict:
        """Evaluate on all pairs, compute metrics."""
        print(
            f"\n[EVAL] Evaluating on {len(self.pairs)} pairs "
            f"with alpha={alpha:.2f}, beta={beta:.2f}, gamma={gamma:.2f}, delta={delta:.2f}..."
        )

        results_list = []
        preds = []
        gts = []

        for pair_idx, (dish_a, dish_b, gt) in enumerate(self.pairs):
            comps = self.compute_components(dish_a, dish_b)
            pred = self.compute_similarity(comps, alpha, beta, gamma, delta)
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
                "variant": "RAG+Ontology+Semantic",
                "alpha": alpha,
                "beta": beta,
                "gamma": gamma,
                "delta": delta,
                "total_pairs": len(results_list),
            },
            "results": results_list,
            "metrics": metrics,
        }


def main():
    """Run Task 3 evaluation."""
    evaluator = Task3Evaluator()

    # Step 1: Tune weights on 50 sample pairs
    alpha, beta, gamma, delta = evaluator.tune_weights(sample_size=50)

    # Step 2: Evaluate on all pairs
    output_data = evaluator.evaluate(alpha, beta, gamma, delta)

    # Step 3: Save results
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\n[OK] Results saved to {OUTPUT_PATH}")
    print(f"\n[SUMMARY] Task 3 Evaluation Summary:")
    print(f"  Variant: {output_data['metadata']['variant']}")
    print(f"  Total pairs: {output_data['metadata']['total_pairs']}")
    print(f"  Weights: alpha={alpha:.2f}, beta={beta:.2f}, gamma={gamma:.2f}, delta={delta:.2f}")
    print(f"  Pearson r: {output_data['metrics']['pearson_correlation']:.4f}")
    print(f"  Spearman rho: {output_data['metrics']['spearman_correlation']:.4f}")
    print(f"  MAE: {output_data['metrics']['mae']:.4f}")
    print(f"  RMSE: {output_data['metrics']['rmse']:.4f}")


if __name__ == "__main__":
    main()
