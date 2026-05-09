#!/usr/bin/env python3
"""Task 2 v2: Improved substitution evaluation.

Improvements over v1:
  A. 3 LLM judges (Llama, Gemma, Mistral) + IAA
  B. 200 test cases (up from 100)
  C. Dense baseline (embedding similarity)
  D. Breakdown by constraint type
  E. Weighted NPMI (main ingredients count more)

Checkpointing every 20 cases. Resume-safe.
"""
import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from retrieval.ontology import FoodOntology

DKB_PATH = ROOT / "app" / "data" / "knowledge_base" / "dish_knowledge_base.json"
OUTPUT_PATH = ROOT / "evaluation" / "outputs" / "task2_v2_results.json"
CHECKPOINT_PATH = OUTPUT_PATH.with_suffix(".checkpoint.json")

OLLAMA_URL = "http://localhost:11434/api/chat"
JUDGES = ["llama3.1:8b", "gemma2:9b", "mistral:7b"]
CONSTRAINTS = [None, None, "vegetarian", "vegetarian", "no_seafood", "no_meat"]
N_CASES = 200

# ── Load data ────────────────────────────────────────────────────

FoodOntology._instance = None
ont = FoodOntology()
dishes = json.loads(DKB_PATH.read_text("utf-8"))
dish_map = {d["id"]: d for d in dishes}

# ── Generate test cases ──────────────────────────────────────────

def generate_cases():
    random.seed(42)
    eligible = [d for d in dishes
                if len(d.get("ingredients", [])) >= 3
                and any(i.get("importance", 0) >= 3 for i in d["ingredients"])]
    random.shuffle(eligible)

    cases = []
    used = set()
    for d in eligible:
        if len(cases) >= N_CASES:
            break
        if d["id"] in used:
            continue
        mains = [i for i in d["ingredients"] if i.get("importance", 0) >= 3]
        if not mains:
            continue
        used.add(d["id"])
        # Pick 1-2 ingredients per dish
        targets = mains[:2] if len(mains) >= 2 else mains[:1]
        for ing in targets:
            if len(cases) >= N_CASES:
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


# ── Dense baseline (embedding similarity) ────────────────────────

def build_dense_substitution():
    """Find substitutes by embedding similarity to original ingredient."""
    from ingestion.embedding import EmbeddingModel
    em = EmbeddingModel()

    # Embed all ingredients
    ing_ids = list(ont.ing_meta.keys())
    ing_texts = [ont.ing_meta[iid].get("name_vi", "") for iid in ing_ids]

    print("  Embedding ingredients for Dense baseline...")
    batch_size = 128
    all_vecs = []
    for i in range(0, len(ing_texts), batch_size):
        vecs = em.embed_documents(ing_texts[i:i+batch_size])
        all_vecs.extend(vecs)
    ing_matrix = np.array(all_vecs)
    id_to_idx = {iid: idx for idx, iid in enumerate(ing_ids)}

    def get_substitutes(ing_id, constraint, top_k=5):
        idx = id_to_idx.get(ing_id)
        if idx is None:
            return []
        qvec = ing_matrix[idx]
        scores = (ing_matrix @ qvec).flatten()
        # Sort by similarity, exclude self
        ranked = np.argsort(scores)[::-1]
        results = []
        for r_idx in ranked:
            if len(results) >= top_k:
                break
            cid = ing_ids[r_idx]
            if cid == ing_id:
                continue
            if not ont._passes_constraint(cid, constraint):
                continue
            meta = ont.ing_meta.get(cid, {})
            results.append({"id": cid, "name": meta.get("name_vi", ""), "score": float(scores[r_idx])})
        return results

    return get_substitutes


# ── Weighted NPMI strategy ───────────────────────────────────────

def get_substitutes_weighted_npmi(dish_id, ing_id, constraint, top_k=5):
    """Like full_ontology but weights NPMI by ingredient importance."""
    dish = dish_map.get(dish_id, {})
    other_ings = [(i["ingredient_id"], i.get("importance", 1))
                  for i in dish.get("ingredients", []) if i["ingredient_id"] != ing_id]

    ing_class = ont.ing_to_class.get(ing_id)
    # Get candidates (same as full_ontology)
    ont_subs = ont.get_substitutes(ing_id)
    candidates = {s["id"] for s in ont_subs}
    # Add class members + siblings
    class_members = set(ont.class_members.get(ing_class, []))
    parent = ont.classes.get(ing_class, {}).get("parent")
    if parent:
        for sib in ont.classes.get(parent, {}).get("children", []):
            class_members |= set(ont.class_members.get(sib, []))
    # Expand for constraint
    if constraint == "vegetarian":
        class_members |= set(ont.get_descendants("PlantProtein"))
        class_members |= set(ont.get_descendants("Mushroom"))
    candidates |= class_members
    candidates.discard(ing_id)
    candidates = {c for c in candidates if ont._passes_constraint(c, constraint)}

    # Weighted NPMI scoring
    ont_ids = {s["id"] for s in ont_subs}
    scored = []
    for c in candidates:
        comps = ont._comps.get(c, {})
        comp_map = {e["id"]: e["npmi"] for e in comps} if isinstance(comps, list) else {}
        # Weighted average: main ingredients (imp=3) count 3x
        weighted_sum = 0.0
        total_weight = 0.0
        for oid, imp in other_ings:
            w = {3: 3.0, 2: 1.5}.get(imp, 0.5)
            npmi = comp_map.get(oid, 0.0)
            weighted_sum += w * npmi
            total_weight += w
        npmi_score = weighted_sum / total_weight if total_weight else 0.0
        ont_bonus = 0.3 if c in ont_ids else 0.0
        same_leaf = 0.2 if ont.ing_to_class.get(c) == ing_class else 0.0
        scored.append((c, npmi_score + ont_bonus + same_leaf))

    scored.sort(key=lambda x: -x[1])
    results = []
    for c, s in scored[:top_k]:
        meta = ont.ing_meta.get(c, {})
        results.append({"id": c, "name": meta.get("name_vi", ""), "score": round(s, 4)})
    return results


# ── Hybrid: Dense + Ontology ──────────────────────────────────────

def get_substitutes_hybrid(dish_id, ing_id, constraint, dense_fn, top_k=5):
    """Combine embedding similarity + ontology signals + constraint filter.
    Score = 0.5*cosine + 0.3*npmi_weighted + 0.2*ontology_bonus, filtered by constraint.
    """
    dish = dish_map.get(dish_id, {})
    other_ings = [(i["ingredient_id"], i.get("importance", 1))
                  for i in dish.get("ingredients", []) if i["ingredient_id"] != ing_id]
    ing_class = ont.ing_to_class.get(ing_id)

    # Get dense candidates (top-30, pre-filtered by constraint)
    dense_results = dense_fn(ing_id, constraint, top_k=30)
    dense_scores = {r["id"]: r["score"] for r in dense_results}

    # Also get ontology candidates
    ont_subs = ont.get_substitutes(ing_id)
    ont_ids = {s["id"] for s in ont_subs}
    class_members = set(ont.class_members.get(ing_class, []))
    parent = ont.classes.get(ing_class, {}).get("parent")
    if parent:
        for sib in ont.classes.get(parent, {}).get("children", []):
            class_members |= set(ont.class_members.get(sib, []))
    if constraint == "vegetarian":
        class_members |= set(ont.get_descendants("PlantProtein"))
        class_members |= set(ont.get_descendants("Mushroom"))

    # Union of candidates
    all_candidates = set(dense_scores.keys()) | ont_ids | class_members
    all_candidates.discard(ing_id)
    all_candidates = {c for c in all_candidates if ont._passes_constraint(c, constraint)}

    # Score each candidate
    scored = []
    for c in all_candidates:
        # Cosine similarity (normalize to 0-1)
        cosine = dense_scores.get(c, 0.0)

        # Weighted NPMI with other dish ingredients
        comps = ont._comps.get(c, [])
        comp_map = {e["id"]: e["npmi"] for e in comps} if isinstance(comps, list) else {}
        weighted_sum = 0.0
        total_weight = 0.0
        for oid, imp in other_ings:
            w = {3: 3.0, 2: 1.5}.get(imp, 0.5)
            weighted_sum += w * comp_map.get(oid, 0.0)
            total_weight += w
        npmi = weighted_sum / total_weight if total_weight else 0.0

        # Ontology bonus
        ont_bonus = 0.2 if c in ont_ids else 0.0
        same_leaf = 0.1 if ont.ing_to_class.get(c) == ing_class else 0.0

        total = 0.5 * cosine + 0.3 * npmi + ont_bonus + same_leaf
        scored.append((c, total))

    scored.sort(key=lambda x: -x[1])
    results = []
    for c, s in scored[:top_k]:
        meta = ont.ing_meta.get(c, {})
        results.append({"id": c, "name": meta.get("name_vi", ""), "score": round(s, 4)})
    return results


# ── LLM Judge ────────────────────────────────────────────────────

JUDGE_PROMPT = """Rate this ingredient substitution (0=bad, 1=acceptable, 2=good). Reply with ONLY one number.
Dish: {dish}
Original: {original}
Substitute: {substitute}
Constraint: {constraint}
Score:"""


def judge(dish_name, original, substitute, constraint, model, max_retries=3):
    prompt = JUDGE_PROMPT.format(
        dish=dish_name, original=original,
        substitute=substitute, constraint=constraint or "none")
    for attempt in range(max_retries):
        try:
            resp = requests.post(OLLAMA_URL, json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0, "num_predict": 3},
            }, timeout=30)
            text = resp.json()["message"]["content"].strip()
            for ch in text:
                if ch in "012":
                    return int(ch)
            return None
        except:
            if attempt < max_retries - 1:
                time.sleep(2)
    return None


# ── Checkpoint ───────────────────────────────────────────────────

def load_checkpoint():
    if CHECKPOINT_PATH.exists():
        data = json.loads(CHECKPOINT_PATH.read_text("utf-8"))
        print(f"[RESUME] {data['completed']} cases done")
        return data["completed"], data["results"]
    return 0, []


def save_checkpoint(completed, results):
    CHECKPOINT_PATH.write_text(json.dumps({"completed": completed, "results": results}, ensure_ascii=False), "utf-8")


# ── Main ─────────────────────────────────────────────────────────

def main():
    cases = generate_cases()
    print(f"Generated {len(cases)} test cases")
    constraints_dist = defaultdict(int)
    for c in cases:
        constraints_dist[c["constraint"] or "none"] += 1
    print(f"  Constraints: {dict(constraints_dist)}")

    # Build Dense baseline
    print("\nBuilding Dense baseline...")
    dense_fn = build_dense_substitution()

    # Strategies
    strategies = ["random_class", "dense", "weighted_ontology", "hybrid"]

    start, all_results = load_checkpoint()
    t0 = time.time()

    print(f"\nEvaluating {len(cases)} cases × {len(strategies)} strategies × {len(JUDGES)} judges...")

    for i in range(start, len(cases)):
        case = cases[i]
        case_results = {"case": case, "strategies": {}}

        for strat in strategies:
            if strat == "dense":
                subs = dense_fn(case["ingredient_id"], case["constraint"], top_k=5)
            elif strat == "weighted_ontology":
                subs = get_substitutes_weighted_npmi(
                    case["dish_id"], case["ingredient_id"], case["constraint"], top_k=5)
            elif strat == "hybrid":
                subs = get_substitutes_hybrid(
                    case["dish_id"], case["ingredient_id"], case["constraint"], dense_fn, top_k=5)
            else:
                subs = ont.get_substitutes_for_dish(
                    case["dish_id"], case["ingredient_id"],
                    constraint=case["constraint"], strategy=strat, top_k=5)

            if not subs:
                case_results["strategies"][strat] = {"top1": None, "scores": {}, "mean": None}
                continue

            top1 = subs[0]
            # Judge with 3 models
            scores = {}
            for model in JUDGES:
                s = judge(case["dish_name"], case["ingredient_name"], top1["name"], case["constraint"], model)
                scores[model] = s

            valid = [v for v in scores.values() if v is not None]
            mean = sum(valid) / len(valid) if valid else None

            case_results["strategies"][strat] = {
                "top1": top1["name"],
                "top1_id": top1["id"],
                "scores": scores,
                "mean": mean,
                "all_subs": [s["name"] for s in subs[:5]],
            }

        all_results.append(case_results)

        # Progress
        elapsed = time.time() - t0
        rate = (i - start + 1) / elapsed if elapsed > 0 else 0
        eta = (len(cases) - i - 1) / rate if rate > 0 else 0
        print(f"  [{i+1}/{len(cases)}] {case['dish_name'][:25]:<25} | {elapsed:.0f}s | ETA {eta:.0f}s")

        # Checkpoint every 20
        if (i + 1) % 20 == 0:
            save_checkpoint(i + 1, all_results)
            print(f"    [SAVED]")

    # ── Aggregate ────────────────────────────────────────────────

    print(f"\n{'='*70}")
    print(f"{'Strategy':<20} {'Mean':<8} {'Accept%':<10} {'Good%':<8}")
    print(f"{'-'*70}")

    summary = {}
    for strat in strategies:
        means = [r["strategies"][strat]["mean"] for r in all_results
                 if r["strategies"][strat].get("mean") is not None]
        if not means:
            continue
        avg = np.mean(means)
        accept = sum(1 for m in means if m >= 1.0) / len(means)
        good = sum(1 for m in means if m >= 1.67) / len(means)  # 2/3 judges give 2
        print(f"{strat:<20} {avg:.3f}   {accept:.1%}      {good:.1%}")
        summary[strat] = {"mean": round(avg, 3), "accept_rate": round(accept, 3), "good_rate": round(good, 3), "n": len(means)}

    # Breakdown by constraint
    print(f"\n{'='*70}")
    print("Breakdown by constraint (dense vs weighted_ontology):")
    for constraint_val in ["none", "vegetarian", "no_seafood", "no_meat"]:
        subset = [r for r in all_results if (r["case"]["constraint"] or "none") == constraint_val]
        if not subset:
            continue
        de_means = [r["strategies"]["dense"]["mean"] for r in subset if r["strategies"]["dense"].get("mean") is not None]
        wo_means = [r["strategies"]["weighted_ontology"]["mean"] for r in subset if r["strategies"]["weighted_ontology"].get("mean") is not None]
        print(f"  {constraint_val:<12}: dense={np.mean(de_means):.3f} (n={len(de_means)}), weighted_ont={np.mean(wo_means):.3f} (n={len(wo_means)})")

    # IAA
    print(f"\n{'='*70}")
    print("Inter-annotator agreement (weighted_ontology):")
    ratings = []
    for r in all_results:
        scores = r["strategies"]["weighted_ontology"].get("scores", {})
        if all(scores.get(j) is not None for j in JUDGES):
            ratings.append([scores[j] for j in JUDGES])
    if ratings:
        ratings_arr = np.array(ratings)
        for i in range(3):
            for j in range(i+1, 3):
                agree = np.mean(ratings_arr[:, i] == ratings_arr[:, j])
                print(f"  {JUDGES[i]} vs {JUDGES[j]}: {agree:.1%}")

    # Save
    output = {"n_cases": len(cases), "strategies": strategies, "judges": JUDGES,
              "summary": summary, "results": all_results}
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), "utf-8")
    print(f"\nSaved → {OUTPUT_PATH}")
    if CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()


if __name__ == "__main__":
    main()
