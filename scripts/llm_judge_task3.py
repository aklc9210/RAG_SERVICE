#!/usr/bin/env python3
"""
LLM-as-Judge for Task 3: Related Dishes Evaluation
====================================================
Runs locally via Ollama.

Usage:
    python scripts/llm_judge_task3.py
    python scripts/llm_judge_task3.py --models qwen2.5:7b mistral:7b
    python scripts/llm_judge_task3.py --limit 10

Output:
    evaluation/outputs/llm_judge_task3_results.csv
    evaluation/outputs/llm_judge_task3_summary.json
"""

import argparse
import csv
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUT_CSV = ROOT / "evaluation" / "annotation" / "task3_annotation_template.csv"
OUT_DIR = ROOT / "evaluation" / "outputs"

MODELS = ["qwen2.5:7b", "llama3.1:8b", "gemma2:9b", "mistral:7b"]

# ============================================================
# Per-model prompts
# ============================================================

MODEL_PROMPTS = {
    "qwen2.5:7b": {
        "system": (
            "Bạn là chuyên gia ẩm thực Việt Nam. "
            "Đánh giá mức độ liên quan giữa hai món ăn. "
            "Chỉ trả về một số duy nhất: 0, 1, hoặc 2."
        ),
        "template": """\
Món gốc: {query_name} (loại: {query_cat})
Nguyên liệu chính: {query_ingr}

Món cần đánh giá: {cand_name} (loại: {cand_cat})
Nguyên liệu chính: {cand_ingr}

Hai món này liên quan đến nhau ở mức nào?
- 0: Không liên quan — khác nguyên liệu, khác phong cách
- 1: Liên quan — có điểm chung về nguyên liệu hoặc phong cách
- 2: Rất liên quan — nhiều nguyên liệu chung, cùng phong cách, có thể thay thế nhau

Trả về đúng một số (0, 1, hoặc 2):""",
    },
    "llama3.1:8b": {
        "system": (
            "You are a Vietnamese cuisine expert. "
            "Rate how related two dishes are. "
            "Reply with ONLY a single digit: 0, 1, or 2. No explanation."
        ),
        "template": """\
Dish A: {query_name} (type: {query_cat})
Main ingredients: {query_ingr}

Dish B: {cand_name} (type: {cand_cat})
Main ingredients: {cand_ingr}

How related are these two Vietnamese dishes?
- 0: Not related — different ingredients and cooking style
- 1: Related — some shared ingredients or similar style
- 2: Very related — many shared ingredients, same style, interchangeable

Answer with ONLY one number (0, 1, or 2):""",
    },
    "gemma2:9b": {
        "system": (
            "Bạn là chuyên gia ẩm thực Việt Nam. "
            "Đánh giá mức độ liên quan giữa hai món ăn. "
            "CHỈ trả về một số: 0, 1, hoặc 2. Không giải thích."
        ),
        "template": """\
Món gốc: {query_name} (loại: {query_cat})
Nguyên liệu: {query_ingr}

Món so sánh: {cand_name} (loại: {cand_cat})
Nguyên liệu: {cand_ingr}

Mức độ liên quan:
- 0: Không liên quan
- 1: Liên quan
- 2: Rất liên quan

Số điểm:""",
    },
    "mistral:7b": {
        "system": (
            "You are a Vietnamese cuisine expert. "
            "Rate how related two dishes are. "
            "Reply with ONLY one number: 0, 1, or 2."
        ),
        "template": """\
Dish A: {query_name} (type: {query_cat})
Ingredients: {query_ingr}

Dish B: {cand_name} (type: {cand_cat})
Ingredients: {cand_ingr}

Relatedness:
- 0: Not related
- 1: Related — some overlap
- 2: Very related — highly similar, interchangeable

Score:""",
    },
}

DEFAULT_PROMPT = {
    "system": "Bạn là chuyên gia ẩm thực Việt Nam. Chỉ trả về một số: 0, 1, hoặc 2.",
    "template": """\
Món gốc: {query_name} ({query_cat}) — {query_ingr}
Món so sánh: {cand_name} ({cand_cat}) — {cand_ingr}
- 0: Không liên quan  - 1: Liên quan  - 2: Rất liên quan
Số điểm:""",
}


# ============================================================
# Helpers
# ============================================================

def load_data(csv_path: Path) -> list[dict]:
    rows = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            rows.append({
                "query_dish_id": row["query_dish_id"],
                "query_dish_name": row["query_dish_name"],
                "query_category": row["query_category"],
                "query_ingredients": row["query_ingredients_preview"],
                "candidate_dish_id": row["candidate_dish_id"],
                "candidate_dish_name": row["candidate_dish_name"],
                "candidate_category": row["candidate_category"],
                "candidate_ingredients": row["candidate_ingredients_preview"],
            })
    return rows


def ollama_generate(model: str, prompt: str, system: str) -> str:
    import urllib.request
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 16},
    }).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())["response"]


def parse_score(text: str) -> int:
    found = [ch for ch in text if ch in "012"]
    if found:
        return int(found[-1])
    low = text.lower()
    if "không liên quan" in low or "not related" in low:
        return 0
    if "rất liên quan" in low or "very related" in low:
        return 2
    if "liên quan" in low or "related" in low:
        return 1
    return -1


def judge_all(model: str, rows: list[dict]) -> list[int]:
    cfg = MODEL_PROMPTS.get(model, DEFAULT_PROMPT)
    scores = []
    total = len(rows)
    t0 = time.time()

    for i, row in enumerate(rows):
        prompt = cfg["template"].format(
            query_name=row["query_dish_name"],
            query_cat=row["query_category"],
            query_ingr=row["query_ingredients"],
            cand_name=row["candidate_dish_name"],
            cand_cat=row["candidate_category"],
            cand_ingr=row["candidate_ingredients"],
        )
        try:
            resp = ollama_generate(model, prompt, cfg["system"])
            score = parse_score(resp)
        except Exception as e:
            print(f"    Error row {i}: {e}")
            score = -1
        scores.append(score)

        if (i + 1) % 50 == 0 or i == total - 1:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (total - i - 1) / rate if rate > 0 else 0
            print(f"  [{i+1}/{total}] {rate:.1f} req/s, ETA {eta:.0f}s")

    return scores


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=MODELS)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    rows = load_data(INPUT_CSV)
    if args.limit:
        rows = rows[:args.limit]
    print(f"Loaded {len(rows)} judgements, {len(set(r['query_dish_id'] for r in rows))} dishes")

    try:
        import urllib.request
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
    except Exception:
        print("ERROR: Ollama not running. Start with: ollama serve")
        return

    model_cols = []
    for model in args.models:
        col = f"score_{model.replace(':', '_').replace('.', '_')}"
        model_cols.append((model, col))

        print(f"\n{'='*50}")
        print(f"Model: {model}")
        print(f"{'='*50}")

        print("  Warming up...")
        try:
            ollama_generate(model, "test", "test")
        except Exception:
            print(f"  SKIP — run: ollama pull {model}")
            for row in rows:
                row[col] = -1
            continue

        scores = judge_all(model, rows)
        for row, score in zip(rows, scores):
            row[col] = score

        valid = [s for s in scores if s >= 0]
        if valid:
            print(f"  Mean={sum(valid)/len(valid):.2f}, "
                  f"Dist: 0={valid.count(0)} 1={valid.count(1)} 2={valid.count(2)}, "
                  f"Failures={scores.count(-1)}")
        else:
            print(f"  All {len(scores)} failed to parse!")

    # Aggregate
    for row in rows:
        valid = [row[col] for _, col in model_cols if row.get(col, -1) >= 0]
        row["score_mean"] = round(sum(valid) / len(valid), 4) if valid else -1
        row["n_models"] = len(valid)

    # Save CSV
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = OUT_DIR / "llm_judge_task3_results.csv"
    fieldnames = [
        "query_dish_id", "query_dish_name", "query_category", "query_ingredients",
        "candidate_dish_id", "candidate_dish_name", "candidate_category", "candidate_ingredients",
    ] + [col for _, col in model_cols] + ["score_mean", "n_models"]

    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})
    print(f"\nResults → {out_csv}")

    # Summary JSON
    summary = {"models": {}}
    for model, col in model_cols:
        valid = [r[col] for r in rows if r.get(col, -1) >= 0]
        n = len(valid)
        summary["models"][model] = {
            "n_valid": n,
            "parse_failures": len(rows) - n,
            "mean_score": round(sum(valid) / n, 4) if n else 0,
            "distribution": {str(i): valid.count(i) for i in range(3)},
        }

    agg = [r["score_mean"] for r in rows if r["score_mean"] >= 0]
    summary["aggregate"] = {
        "n_valid": len(agg),
        "mean_score": round(sum(agg) / len(agg), 4) if agg else 0,
    }

    out_json = OUT_DIR / "llm_judge_task3_summary.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"Summary → {out_json}")

    # Print table
    print(f"\n{'Model':<25} {'Mean':>6} {'0':>5} {'1':>5} {'2':>5} {'Fail':>5}")
    print("-" * 55)
    for model, col in model_cols:
        m = summary["models"][model]
        d = m["distribution"]
        print(f"{model:<25} {m['mean_score']:>6.3f} {d['0']:>5} {d['1']:>5} {d['2']:>5} {m['parse_failures']:>5}")
    print(f"{'Aggregate':<25} {summary['aggregate']['mean_score']:>6.3f}")


if __name__ == "__main__":
    main()
