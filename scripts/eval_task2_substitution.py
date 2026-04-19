#!/usr/bin/env python3
"""Day 4 — Task 2: Substitution evaluation.

1. Generate 100 test cases (50 dishes × 2 replacements, mixed constraints)
2. Run 3 strategies: random_class, npmi_only, full_ontology
3. LLM-judge each suggestion (0/1/2 score)
4. Save results

Usage:
    python scripts/eval_task2_substitution.py
"""
import json
import random
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.llm_client import LLMClient
from retrieval.ontology import FoodOntology

DKB = ROOT / "app" / "data" / "knowledge_base" / "dish_knowledge_base.json"
OUT = ROOT / "evaluation" / "outputs" / "ir_task2_substitution_results.json"

CONSTRAINTS = [None, None, None, "vegetarian", "no_seafood", "no_meat"]

JUDGE_PROMPT = """Bạn là chuyên gia ẩm thực Việt Nam. Đánh giá xem nguyên liệu thay thế có phù hợp không.

Món ăn: {dish_name}
Nguyên liệu gốc: {original}
Nguyên liệu thay thế: {substitute}
Ràng buộc: {constraint}

Chấm điểm:
- 2 = Thay thế tốt, hợp lý về hương vị và kết cấu
- 1 = Chấp nhận được nhưng không lý tưởng
- 0 = Không phù hợp

Chỉ trả về 1 số: 0, 1, hoặc 2."""


def generate_test_cases(ont, dishes):
    """Select 50 dishes × 2 ingredient replacements = 100 cases."""
    random.seed(42)
    # Filter dishes with >= 3 ingredients, has main ingredient
    eligible = [d for d in dishes
                if len(d.get("ingredients", [])) >= 3
                and any(i.get("importance", 0) >= 3 for i in d["ingredients"])]
    random.shuffle(eligible)

    cases = []
    used_dishes = set()
    for d in eligible:
        if len(cases) >= 100:
            break
        if d["id"] in used_dishes:
            continue
        # Pick 1-2 main ingredients to replace
        mains = [i for i in d["ingredients"] if i.get("importance", 0) >= 3]
        secondaries = [i for i in d["ingredients"] if i.get("importance", 0) == 2]
        targets = mains[:1] + secondaries[:1]
        if not targets:
            continue
        used_dishes.add(d["id"])
        for ing in targets:
            if len(cases) >= 100:
                break
            constraint = random.choice(CONSTRAINTS)
            cases.append({
                "dish_id": d["id"],
                "dish_name": d.get("name_vi", ""),
                "ingredient_id": ing["ingredient_id"],
                "ingredient_name": ing.get("name_vi", ""),
                "constraint": constraint,
            })
    return cases


def judge_substitute(client, dish_name, original, substitute, constraint):
    """LLM judge: score 0/1/2."""
    prompt = JUDGE_PROMPT.format(
        dish_name=dish_name, original=original,
        substitute=substitute,
        constraint=constraint or "Không có",
    )
    try:
        resp = client.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0, max_tokens=10,
        )
        match = re.search(r"[012]", resp)
        return int(match.group()) if match else 0
    except Exception:
        return 0


def main():
    random.seed(42)
    FoodOntology._instance = None
    ont = FoodOntology()
    dishes = json.loads(DKB.read_text("utf-8"))
    client = LLMClient()
    print(f"Model: {client.model}")

    # Generate test cases
    print("Generating 100 test cases...")
    cases = generate_test_cases(ont, dishes)
    print(f"  Generated {len(cases)} cases")
    constraints = defaultdict(int)
    for c in cases:
        constraints[c["constraint"] or "none"] += 1
    print(f"  Constraints: {dict(constraints)}")

    # Run 3 strategies + judge
    strategies = ["random_class", "npmi_only", "full_ontology"]
    all_results = {s: [] for s in strategies}

    print(f"\nEvaluating {len(cases)} cases × {len(strategies)} strategies...")
    for i, case in enumerate(cases):
        for strat in strategies:
            subs = ont.get_substitutes_for_dish(
                case["dish_id"], case["ingredient_id"],
                constraint=case["constraint"], strategy=strat, top_k=3,
            )
            if not subs:
                all_results[strat].append({"case": case, "top1": None, "score": 0})
                continue

            top1 = subs[0]
            score = judge_substitute(
                client, case["dish_name"],
                case["ingredient_name"], top1["name"],
                case["constraint"],
            )
            all_results[strat].append({
                "case": case,
                "top1": top1["name"],
                "top1_id": top1["id"],
                "score": score,
                "all_subs": [s["name"] for s in subs[:3]],
            })

        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{len(cases)}")

    # Aggregate
    print("\n" + "=" * 60)
    summary = {}
    for strat in strategies:
        scores = [r["score"] for r in all_results[strat]]
        n_empty = sum(1 for r in all_results[strat] if r.get("top1") is None)
        mean = sum(scores) / len(scores) if scores else 0
        score_dist = {s: scores.count(s) for s in [0, 1, 2]}
        accept_rate = sum(1 for s in scores if s >= 1) / len(scores) if scores else 0
        good_rate = sum(1 for s in scores if s == 2) / len(scores) if scores else 0

        summary[strat] = {
            "mean_score": round(mean, 3),
            "accept_rate": round(accept_rate, 3),
            "good_rate": round(good_rate, 3),
            "score_dist": score_dist,
            "n_empty": n_empty,
            "n_cases": len(scores),
        }
        print(f"[{strat:15s}] mean={mean:.3f}  accept={accept_rate:.1%}  good={good_rate:.1%}  empty={n_empty}  dist={score_dist}")

    # Save
    OUT.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "summary": summary,
        "cases": cases,
        "detailed": {s: all_results[s] for s in strategies},
    }
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), "utf-8")
    print(f"\nSaved → {OUT}")


if __name__ == "__main__":
    main()
