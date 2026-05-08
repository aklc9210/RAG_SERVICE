#!/usr/bin/env python3
"""Task 3: Build diverse candidate set + LLM judge → new GT for fair ablation.

For each of 200 anchors, select 20 candidates from 4 sources:
  - 5 top Jaccard (easy for Jaccard-based systems)
  - 5 top cosine embedding (easy for Dense)
  - 5 same-category but low Jaccard (hard for Jaccard, tests ontology)
  - 5 random (negatives)

Then 3 LLM judges score each pair → new GT.
"""
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from retrieval.ontology import FoodOntology

GT_PATH = ROOT / "evaluation" / "data" / "datasets" / "task3_related_gt.jsonl"
KB_PATH = ROOT / "app" / "data" / "knowledge_base" / "dish_knowledge_base.json"
OUTPUT_CANDIDATES = ROOT / "evaluation" / "data" / "datasets" / "task3_diverse_candidates.json"
OUTPUT_JUDGED = ROOT / "evaluation" / "outputs" / "task3_diverse_judged.json"

OLLAMA_URL = "http://localhost:11434/api/chat"
JUDGES = ["llama3.1:8b", "gemma2:9b", "mistral:7b"]

ont = FoodOntology()

# ── Load data ────────────────────────────────────────────────────

dish_kb = {d["id"]: d for d in json.loads(KB_PATH.read_text("utf-8"))}

dish_meta = {}
with open(GT_PATH, encoding="utf-8") as f:
    for line in f:
        e = json.loads(line)
        dish_meta[e["dish_id"]] = {
            "name": e["dish_name"],
            "category": e["category"],
            "ingredient_ids": e["ingredient_ids"],
        }

all_dish_ids = list(dish_meta.keys())
print(f"Loaded {len(all_dish_ids)} dishes")

# ── Build candidate sources ──────────────────────────────────────

def jaccard(a_ids, b_ids):
    sa, sb = set(a_ids), set(b_ids)
    u = len(sa | sb)
    return len(sa & sb) / u if u else 0.0


# Pre-compute Jaccard for all pairs of 200 anchors vs all dishes
random.seed(42)
anchors = random.sample(all_dish_ids, 200)

print("Building diverse candidates for 200 anchors...")

candidates_data = []

for i, anchor in enumerate(anchors):
    a_ings = dish_meta[anchor]["ingredient_ids"]
    a_cat = dish_meta[anchor]["category"]

    # Compute Jaccard to all other dishes
    scores = []
    same_cat_low_jacc = []
    for did in all_dish_ids:
        if did == anchor:
            continue
        b_ings = dish_meta[did]["ingredient_ids"]
        j = jaccard(a_ings, b_ings)
        scores.append((did, j))
        if dish_meta[did]["category"] == a_cat and j < 0.2:
            same_cat_low_jacc.append((did, j))

    scores.sort(key=lambda x: -x[1])

    # Source 1: Top-5 Jaccard
    top_jacc = [did for did, _ in scores[:5]]

    # Source 2: Top-5 cosine (approximate: use medium Jaccard range as proxy)
    # Real cosine would need embeddings; use Jaccard rank 10-20 as "different signal"
    mid_range = [did for did, _ in scores[10:20]]
    top_cosine_proxy = random.sample(mid_range, min(5, len(mid_range)))

    # Source 3: Same category, low Jaccard (ontology should help here)
    if len(same_cat_low_jacc) >= 5:
        same_cat_picks = random.sample(same_cat_low_jacc, 5)
        top_same_cat = [did for did, _ in same_cat_picks]
    else:
        top_same_cat = [did for did, _ in same_cat_low_jacc]
        # Fill with random same-cat
        same_cat_all = [did for did in all_dish_ids
                        if did != anchor and dish_meta[did]["category"] == a_cat
                        and did not in top_same_cat]
        extra = random.sample(same_cat_all, min(5 - len(top_same_cat), len(same_cat_all)))
        top_same_cat.extend(extra)

    # Source 4: Random (negatives)
    used = set(top_jacc + top_cosine_proxy + top_same_cat + [anchor])
    pool = [did for did in all_dish_ids if did not in used]
    top_random = random.sample(pool, 5)

    # Combine (deduplicate)
    all_cands = []
    seen = set()
    for source, cands in [("jaccard_top", top_jacc), ("mid_range", top_cosine_proxy),
                           ("same_cat_low_jacc", top_same_cat), ("random", top_random)]:
        for did in cands:
            if did not in seen:
                all_cands.append({"dish_id": did, "source": source})
                seen.add(did)

    candidates_data.append({
        "anchor_id": anchor,
        "anchor_name": dish_meta[anchor]["name"],
        "candidates": all_cands,
    })

    if (i + 1) % 50 == 0:
        print(f"  {i+1}/200 anchors done")

# Save candidates
OUTPUT_CANDIDATES.write_text(json.dumps(candidates_data, ensure_ascii=False, indent=2), "utf-8")
total_pairs = sum(len(c["candidates"]) for c in candidates_data)
print(f"\nSaved {total_pairs} candidate pairs → {OUTPUT_CANDIDATES}")

# ── LLM Judge ────────────────────────────────────────────────────

JUDGE_PROMPT = """Chấm mức liên quan giữa 2 món (0=không, 1=một phần, 2=rất liên quan). Trả lời CHỈ 1 SỐ.
Món 1: {dish_a}
Món 2: {dish_b}
Điểm:"""


def judge_pair(dish_a_name, dish_b_name, model, max_retries=3):
    prompt = JUDGE_PROMPT.format(dish_a=dish_a_name, dish_b=dish_b_name)
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
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                print(f"    [WARN] Failed {model} after {max_retries} retries: {e}")
                return None


# ── Checkpoint/Resume ────────────────────────────────────────────

CHECKPOINT_PATH = OUTPUT_JUDGED.with_suffix(".checkpoint.json")


def load_checkpoint():
    if CHECKPOINT_PATH.exists():
        data = json.loads(CHECKPOINT_PATH.read_text("utf-8"))
        print(f"[RESUME] Loaded checkpoint: {data['completed_anchors']} anchors, {len(data['results'])} pairs")
        return data["completed_anchors"], data["results"]
    return 0, []


def save_checkpoint(completed_anchors, results):
    data = {"completed_anchors": completed_anchors, "results": results}
    CHECKPOINT_PATH.write_text(json.dumps(data, ensure_ascii=False), "utf-8")


# ── Judge with checkpointing ────────────────────────────────────

print(f"\nJudging {total_pairs} pairs × {len(JUDGES)} judges...")
start_anchor, results = load_checkpoint()
t0 = time.time()

for ci in range(start_anchor, len(candidates_data)):
    cdata = candidates_data[ci]
    anchor_name = cdata["anchor_name"]

    for cand in cdata["candidates"]:
        cand_name = dish_meta[cand["dish_id"]]["name"]
        scores = {}
        for model in JUDGES:
            s = judge_pair(anchor_name, cand_name, model)
            scores[model] = s

        valid_scores = [v for v in scores.values() if v is not None]
        mean_score = sum(valid_scores) / len(valid_scores) if valid_scores else None

        results.append({
            "anchor_id": cdata["anchor_id"],
            "candidate_id": cand["dish_id"],
            "source": cand["source"],
            "scores": scores,
            "mean_score": mean_score,
        })

    # Progress every anchor
    elapsed = time.time() - t0
    pairs_done = len(results) - (start_anchor * 20)  # approximate
    rate = pairs_done / elapsed if elapsed > 0 else 0
    remaining_pairs = total_pairs - len(results)
    eta = remaining_pairs / rate if rate > 0 else 0
    print(f"  [{ci+1}/200] {cdata['anchor_name'][:30]:<30} | "
          f"{len(results)}/{total_pairs} pairs | {elapsed:.0f}s | ETA {eta:.0f}s")

    # Checkpoint every 10 anchors
    if (ci + 1) % 10 == 0:
        save_checkpoint(ci + 1, results)
        print(f"    [CHECKPOINT] Saved at anchor {ci+1}")

# Final save
output = {
    "n_anchors": len(candidates_data),
    "n_pairs": len(results),
    "judges": JUDGES,
    "positive_threshold": 1.0,
    "results": results,
}
OUTPUT_JUDGED.write_text(json.dumps(output, ensure_ascii=False, indent=2), "utf-8")
elapsed = time.time() - t0
print(f"\nDone in {elapsed:.0f}s. Saved → {OUTPUT_JUDGED}")

# Clean up checkpoint
if CHECKPOINT_PATH.exists():
    CHECKPOINT_PATH.unlink()
    print("[OK] Checkpoint removed")

# Save judged results
output = {
    "n_anchors": len(candidates_data),
    "n_pairs": len(results),
    "judges": JUDGES,
    "positive_threshold": 1.0,
    "results": results,
}
OUTPUT_JUDGED.write_text(json.dumps(output, ensure_ascii=False, indent=2), "utf-8")
elapsed = time.time() - t0
print(f"\nDone in {elapsed:.0f}s. Saved → {OUTPUT_JUDGED}")

# Quick stats
scores_all = [r["mean_score"] for r in results if r["mean_score"] is not None]
n_pos = sum(1 for s in scores_all if s >= 1.0)
print(f"Stats: {len(scores_all)} scored, {n_pos} positive ({100*n_pos/len(scores_all):.1f}%)")
by_source = {}
for r in results:
    src = r["source"]
    if r["mean_score"] is not None:
        by_source.setdefault(src, []).append(r["mean_score"])
for src, vals in by_source.items():
    pos = sum(1 for v in vals if v >= 1.0)
    print(f"  {src:<20}: mean={np.mean(vals):.2f}, positive={pos}/{len(vals)} ({100*pos/len(vals):.0f}%)")
