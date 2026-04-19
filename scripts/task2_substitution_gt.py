#!/usr/bin/env python3
"""
Day 4 — Task 2: Substitution Ground Truth via LLM-Judge

Workflow:
  1. Select 50 dishes randomly
  2. For each dish, select 1 main ingredient + create 2 substitution candidates
  3. Generate 100 test cases with mixed constraints (vegetarian, no-seafood, low-sodium)
  4. Run LLM-judge on each case: "Is [X] an acceptable substitute for [Y] in [dish]?"
     Scoring: 0 = No, 1 = Maybe, 2 = Yes
  5. Aggregate scores as GT
  6. Save to evaluation/data/datasets/task2_substitution_gt.jsonl

Usage:
    python scripts/task2_substitution_gt.py
"""

import json
import random
import sys
from pathlib import Path
from typing import List, Dict, Tuple
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from retrieval.ontology import FoodOntology

KB_PATH = ROOT / "app" / "data" / "knowledge_base" / "dish_knowledge_base.json"
OUTPUT_PATH = ROOT / "evaluation" / "data" / "datasets" / "task2_substitution_gt.jsonl"

OLLAMA_API = "http://localhost:11434/api/chat"
LLM_MODEL = "qwen2.5:7b"

# Constraint definitions (map to ontology classes)
CONSTRAINTS = {
    "vegetarian": {
        "description": "No meat/seafood",
        "allowed_classes": ["PlantProtein", "Vegetable", "Herb", "Seasoning", "Staple"],
    },
    "no_seafood": {
        "description": "No seafood/shellfish",
        "allowed_classes": ["Meat", "Poultry", "Egg", "PlantProtein", "Vegetable", "Seasoning", "Staple"],
    },
    "low_sodium": {
        "description": "Reduce salt/soy sauce",
        "allowed_classes": ["Meat", "Vegetable", "Herb", "Fruit", "PlantProtein"],
    },
    "none": {
        "description": "No constraint",
        "allowed_classes": None,
    },
}


class Task2GTBuilder:
    """Build ground truth for Task 2 substitution via LLM-judge."""

    def __init__(self):
        self.ontology = FoodOntology()
        self.dishes = self._load_dishes()
        print(f"[OK] Loaded {len(self.dishes)} dishes from KB")

    def _load_dishes(self) -> List[dict]:
        """Load dishes from KB."""
        dishes = []
        with open(KB_PATH, encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                dishes = data
            elif isinstance(data, dict) and "dishes" in data:
                dishes = data["dishes"]
        return dishes

    def _select_test_dishes(self, n: int = 50) -> List[dict]:
        """Randomly select n dishes with ingredient data."""
        random.seed(42)
        valid = [d for d in self.dishes if d.get("ingredients")]
        selected = random.sample(valid, min(n, len(valid)))
        print(f"[OK] Selected {len(selected)} test dishes")
        return selected

    def _get_substitutes_for_ingredient(
        self, ing_id: str, constraint: str = "none", dish_category: str = ""
    ) -> List[str]:
        """
        Get potential substitutes for an ingredient.
        Uses BOTH:
          1. Ontology relations (get_substitutes) - context-aware
          2. Flavor complements (get_complements) - semantic similarity
          3. Same-class ingredients - fallback

        Strict constraint filtering applied.
        """
        candidates = []

        # 1. Get ontology substitutes (context-aware from relations.json)
        subs = self.ontology.get_substitutes(ing_id, context=dish_category)
        candidates.extend([s["id"] for s in subs])

        # 2. Get flavor complements (high NPMI = work well together)
        comps = self.ontology.get_complements(ing_id, top_k=15)
        candidates.extend([c["id"] for c in comps])

        # 3. Fallback: same-class ingredients
        ing_class = self.ontology.ing_to_class.get(ing_id)
        if ing_class:
            same_class = self.ontology.get_descendants(ing_class)
            candidates.extend([i for i in same_class if i != ing_id])

        # Remove duplicates
        candidates = list(set(candidates))

        # STRICT constraint filtering
        if constraint != "none" and constraint in CONSTRAINTS:
            allowed_classes = CONSTRAINTS[constraint]["allowed_classes"]
            if allowed_classes:
                filtered = []
                for c in candidates:
                    c_class = self.ontology.ing_to_class.get(c)
                    if not c_class:
                        continue

                    # Check STRICT match
                    is_allowed = False
                    for allowed in allowed_classes:
                        if c_class == allowed:  # Exact match preferred
                            is_allowed = True
                            break

                    # If no exact match, check subclass (but more strict)
                    if not is_allowed:
                        for allowed in allowed_classes:
                            if self.ontology.is_subclass_of(c_class, allowed):
                                is_allowed = True
                                break

                    if is_allowed:
                        filtered.append(c)

                # Use filtered, but fallback if empty
                if filtered:
                    candidates = filtered

        return candidates[:15]  # Return top 15 candidates

    def generate_test_cases(self, n_dishes: int = 60) -> List[Dict]:
        """
        Generate 100+ test cases (60 dishes × 2 substitutions each).
        Target: at least 100 cases.
        Each case: {dish_id, dish_name, main_ingredient, substitute_ing, constraint}
        """
        test_dishes = self._select_test_dishes(n=n_dishes)
        test_cases = []

        constraints_list = list(CONSTRAINTS.keys())

        for dish_idx, dish in enumerate(test_dishes):
            # Pick main ingredient (longest ingredient list)
            ings_raw = dish.get("ingredients", [])
            if not ings_raw:
                continue

            # Extract ingredient IDs (handle both string and dict formats)
            ings = []
            for ing in ings_raw:
                if isinstance(ing, dict):
                    ings.append(ing.get("ingredient_id"))
                else:
                    ings.append(ing)
            ings = [i for i in ings if i]  # Filter None values

            if not ings:
                continue

            # Get up to 3 constraints for this dish (to ensure we get 100 cases)
            max_constraints = min(3, len(constraints_list))
            chosen_constraints = random.sample(constraints_list, max_constraints)

            # Get dish category for context-aware substitutes
            dish_category = dish.get("category", dish.get("type", ""))

            for constraint in chosen_constraints:
                # Pick random ingredient from dish
                main_ing = random.choice(ings)

                # Get substitutes (improved with relations + complements + context)
                subs = self._get_substitutes_for_ingredient(
                    main_ing, constraint=constraint, dish_category=dish_category
                )
                if not subs:
                    continue

                substitute = random.choice(subs)

                test_cases.append({
                    "case_id": len(test_cases),
                    "dish_id": dish["id"],
                    "dish_name": dish.get("name_vi", dish.get("name", "")),
                    "main_ingredient_id": main_ing,
                    "main_ingredient_name": self.ontology.ing_meta.get(main_ing, {}).get(
                        "name_vi", ""
                    ),
                    "substitute_id": substitute,
                    "substitute_name": self.ontology.ing_meta.get(substitute, {}).get(
                        "name_vi", ""
                    ),
                    "constraint": constraint,
                })

                if len(test_cases) >= 100:
                    break

            if len(test_cases) >= 100:
                break

        print(f"[OK] Generated {len(test_cases)} test cases")
        return test_cases

    def llm_judge_single(self, dish_name: str, main_ing: str, sub_ing: str) -> int:
        """
        Call LLM-judge for a single substitution.
        Returns: 0 (No), 1 (Maybe), 2 (Yes)
        """
        prompt = (
            f"Assess if '{sub_ing}' is an acceptable substitute for '{main_ing}' in '{dish_name}'.\n"
            f"Score:\n"
            f"  0 = Completely unacceptable\n"
            f"  1 = Acceptable with modifications\n"
            f"  2 = Perfect substitute\n"
            f"Answer with ONLY: 0, 1, or 2"
        )

        try:
            response = requests.post(
                OLLAMA_API,
                json={
                    "model": LLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "temperature": 0.3,
                },
                timeout=60,
            )
            response.raise_for_status()
            result = response.json()
            content = result.get("message", {}).get("content", "").strip()

            # Extract score from response
            for char in content:
                if char in ["0", "1", "2"]:
                    return int(char)

            return 1  # Default to "Maybe"
        except Exception as e:
            print(f"[ERROR] LLM call failed: {e}")
            return 1  # Default to "Maybe"

    def run_llm_judgment(self, test_cases: List[Dict]) -> List[Dict]:
        """Run LLM-judge on all test cases."""
        print(f"\n[JUDGE] Running LLM-judge on {len(test_cases)} cases...")

        results = []
        for idx, case in enumerate(test_cases):
            score = self.llm_judge_single(
                case["dish_name"],
                case["main_ingredient_name"],
                case["substitute_name"],
            )

            case["llm_score"] = score
            results.append(case)

            if (idx + 1) % 10 == 0:
                print(f"  [{idx + 1}/{len(test_cases)}] LLM-judged")

        # Compute aggregated score
        scores = [r["llm_score"] for r in results]
        mean_score = sum(scores) / len(scores) if scores else 0

        print(f"\n[STATS] Mean LLM score: {mean_score:.2f}")
        print(f"  Score 0 (unacceptable): {scores.count(0)}")
        print(f"  Score 1 (maybe): {scores.count(1)}")
        print(f"  Score 2 (perfect): {scores.count(2)}")

        return results

    def save_results(self, results: List[Dict]):
        """Save GT to JSONL format."""
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            for result in results:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")

        print(f"\n[OK] Saved {len(results)} GT cases to {OUTPUT_PATH}")

        # Also save summary
        summary = {
            "n_cases": len(results),
            "mean_score": sum(r["llm_score"] for r in results) / len(results),
            "distribution": {
                "score_0": sum(1 for r in results if r["llm_score"] == 0),
                "score_1": sum(1 for r in results if r["llm_score"] == 1),
                "score_2": sum(1 for r in results if r["llm_score"] == 2),
            },
            "constraints": list(set(r["constraint"] for r in results)),
        }

        summary_path = OUTPUT_PATH.parent / "task2_substitution_stats.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        print(f"[OK] Summary saved to {summary_path}")
        print(f"\n[SUMMARY]")
        print(f"  Total cases: {summary['n_cases']}")
        print(f"  Mean score: {summary['mean_score']:.2f}")
        print(f"  Score distribution: {summary['distribution']}")


def main():
    """Run Task 2 GT generation."""
    builder = Task2GTBuilder()

    # Step 1: Generate 100+ test cases (target: at least 100)
    test_cases = builder.generate_test_cases(n_dishes=60)

    # Step 2: Run LLM-judge
    results = builder.run_llm_judgment(test_cases)

    # Step 3: Save results
    builder.save_results(results)


if __name__ == "__main__":
    main()
