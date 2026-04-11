#!/usr/bin/env python3
"""
Task 2 RAG+LLM baseline evaluation.

For each test dish:
  1. Query Pinecone for top-K similar dish documents (retrieved context)
  2. Send dish info + retrieved docs to LLM
  3. LLM suggests 5 flavor-enhancing ingredients (by name)
  4. Fuzzy-match names to ingredient_ids via knowledge base
  5. Evaluate P@5, F1@5, Avg PMI against Task 2 GT

Supports multiple models for comparison:
  python scripts/run_task2_rag_llm.py --models qwen2.5:7b llama3.1:8b

Writes:
  evaluation/outputs/ir_task2_rag_llm.json
"""

import argparse
import json
import math
import os
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

DATASETS_DIR = ROOT / "evaluation" / "data" / "datasets"
OUT_DIR = ROOT / "evaluation" / "outputs"
IKB_PATH = ROOT / "app" / "data" / "knowledge_base" / "ingredient_knowledge_base.json"
PMI_PATH = ROOT / "app" / "data" / "cooccurrence" / "pmi.json"


# ============================================================
# Metric helpers (same as run_evaluation.py)
# ============================================================

def precision_at_k(predicted, ground_truth_ids, k):
    if not predicted:
        return 0.0
    hits = sum(1 for x in predicted[:k] if x in ground_truth_ids)
    return hits / min(k, len(predicted))


def f1_at_k(predicted, ground_truth_ids, k):
    p = precision_at_k(predicted, ground_truth_ids, k)
    n_gt = len(ground_truth_ids)
    r = sum(1 for x in predicted[:k] if x in ground_truth_ids) / n_gt if n_gt > 0 else 0.0
    return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


# ============================================================
# Ingredient name → ID fuzzy resolver
# ============================================================

def _norm(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def build_name_index(ikb: dict) -> list:
    """Returns list of (ingredient_id, name_vi_norm, name_vi_raw)."""
    index = []
    for iid, ing in ikb.items():
        name = ing.get("name_vi", "")
        if name:
            index.append((iid, _norm(name), name))
        for syn in ing.get("synonyms", []):
            if syn:
                index.append((iid, _norm(syn), syn))
    return index


def resolve_name(name: str, index: list, threshold: float = 0.55) -> str | None:
    """Fuzzy match ingredient name to ID. Returns ingredient_id or None."""
    q = _norm(name)
    if not q:
        return None
    best_id, best_score = None, 0.0
    for iid, cand_norm, _ in index:
        # Token overlap score
        q_tokens = set(q.split())
        c_tokens = set(cand_norm.split())
        if not q_tokens or not c_tokens:
            continue
        inter = len(q_tokens & c_tokens)
        union = len(q_tokens | c_tokens)
        score = inter / union
        # Exact substring bonus
        if q in cand_norm or cand_norm in q:
            score = min(1.0, score + 0.3)
        if score > best_score:
            best_score, best_id = score, iid
    return best_id if best_score >= threshold else None


# ============================================================
# LLM prompt + parser
# ============================================================

_SYSTEM_PROMPT = (
    "Bạn là chuyên gia ẩm thực Việt Nam. "
    "Nhiệm vụ: gợi ý nguyên liệu tăng hương vị cho món ăn dựa trên ngữ cảnh được cung cấp. "
    "Chỉ trả về danh sách tên nguyên liệu, mỗi dòng một nguyên liệu, không giải thích."
)

_USER_PROMPT_TEMPLATE = """\
Món ăn: {dish_name}
Nguyên liệu chính: {core_names}

Các món ăn tương tự (ngữ cảnh tham khảo):
{context}

Hãy gợi ý đúng 5 nguyên liệu tăng hương vị cho món "{dish_name}".
Yêu cầu:
- KHÔNG lặp lại nguyên liệu chính ở trên
- Chọn nguyên liệu phù hợp hương vị của món
- Chỉ liệt kê tên nguyên liệu, mỗi dòng một cái, không đánh số, không giải thích"""


def build_context(retrieved_docs: list) -> str:
    """Format retrieved Pinecone docs as context string."""
    lines = []
    for i, doc in enumerate(retrieved_docs[:8], 1):
        name = doc.get("name_vi", "")
        text = doc.get("text", "")[:300]
        if name:
            lines.append(f"{i}. {name}: {text}")
    return "\n".join(lines) if lines else "(không có ngữ cảnh)"


def parse_llm_ingredients(response: str) -> list:
    """Extract ingredient names from LLM response (one per line)."""
    names = []
    for line in response.strip().splitlines():
        line = line.strip()
        line = re.sub(r"^[\d\-\*\.\)]+\s*", "", line)  # remove leading bullets/numbers
        line = line.strip("- ").strip()
        if line and len(line) > 1:
            names.append(line)
    return names[:5]


# ============================================================
# PMI helper
# ============================================================

def get_pmi(pmi: dict, x: str, y: str):
    if x in pmi and y in pmi[x]:
        return pmi[x][y]
    if y in pmi and x in pmi[y]:
        return pmi[y][x]
    return None


# ============================================================
# Core evaluation
# ============================================================

def run_rag_llm_task2(model: str, retriever, llm_client, gt_entries: list,
                      name_index: list, pmi: dict, k: int = 5) -> dict:
    """
    Run RAG+LLM baseline for one model.
    Returns metrics dict.
    """
    from tqdm import tqdm

    metrics = {"precision": [], "f1": [], "avg_pmi": [], "parse_failures": 0}

    for entry in tqdm(gt_entries, desc=f"  {model}", unit="dish"):
        dish_id = entry["dish_id"]
        dish_name = entry["dish_name"]
        core_ids = entry.get("core_ingredient_ids", [])
        core_names = entry.get("core_ingredient_names", [])
        gt_flavor_ids = {f["ingredient_id"] for f in entry["flavor_enhancing"]}
        if not gt_flavor_ids:
            continue

        # 1. Retrieve similar dish documents from Pinecone
        raw_docs = retriever.search_filtered(
            query_text=dish_name, top_k=10, type_filter="dish"
        )
        # Exclude self
        raw_docs = [d for d in raw_docs if d.get("entity_id") != dish_id]

        # 2. Build context and prompt
        context = build_context(raw_docs)
        core_names_str = ", ".join(core_names) if core_names else "(không rõ)"
        user_prompt = _USER_PROMPT_TEMPLATE.format(
            dish_name=dish_name,
            core_names=core_names_str,
            context=context,
        )

        # 3. Call LLM
        try:
            response = llm_client.chat(
                messages=[{"role": "user", "content": user_prompt}],
                model=model,
                system_prompt=_SYSTEM_PROMPT,
                temperature=0.1,
                max_tokens=128,
            )
        except Exception as e:
            metrics["parse_failures"] += 1
            metrics["precision"].append(0.0)
            metrics["f1"].append(0.0)
            metrics["avg_pmi"].append(0.0)
            continue

        # 4. Parse names → resolve to ingredient_ids
        names = parse_llm_ingredients(response)
        if not names:
            metrics["parse_failures"] += 1

        core_id_set = set(core_ids)
        pred_ids = []
        seen = set()
        for name in names:
            iid = resolve_name(name, name_index)
            if iid and iid not in core_id_set and iid not in seen:
                pred_ids.append(iid)
                seen.add(iid)

        # 5. Compute metrics
        p = precision_at_k(pred_ids, gt_flavor_ids, k)
        f = f1_at_k(pred_ids, gt_flavor_ids, k)

        pmi_vals = []
        for iid in pred_ids[:k]:
            for cid in core_ids:
                v = get_pmi(pmi, cid, iid)
                if v is not None:
                    pmi_vals.append(v)
        avg_p = sum(pmi_vals) / len(pmi_vals) if pmi_vals else 0.0

        metrics["precision"].append(p)
        metrics["f1"].append(f)
        metrics["avg_pmi"].append(avg_p)

    def avg(lst):
        return round(sum(lst) / len(lst), 4) if lst else 0.0

    n = len(metrics["precision"])
    return {
        "Precision@5": avg(metrics["precision"]),
        "F1@5": avg(metrics["f1"]),
        "Avg_PMI": avg(metrics["avg_pmi"]),
        "n_dishes": n,
        "parse_failures": metrics["parse_failures"],
    }


# ============================================================
# Main
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(description="Task 2 RAG+LLM baseline.")
    parser.add_argument(
        "--models", nargs="+",
        default=["qwen2.5:7b"],
        help="Ollama model names to evaluate (default: qwen2.5:7b)",
    )
    parser.add_argument("--k", type=int, default=5, help="Top-K (default: 5)")
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Limit number of dishes (for quick testing)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("=== Task 2 RAG+LLM Baseline ===")
    print(f"Models: {args.models}")

    # Load GT
    gt_path = DATASETS_DIR / "task2_flavor_gt.jsonl"
    gt_entries = [json.loads(l) for l in gt_path.read_text().splitlines() if l]
    if args.limit:
        gt_entries = gt_entries[: args.limit]
    print(f"Dishes: {len(gt_entries)}")

    # Load ingredient knowledge base + build name index
    print("Loading ingredient KB...")
    ikb = json.loads(IKB_PATH.read_text(encoding="utf-8"))
    name_index = build_name_index(ikb)
    print(f"  {len(ikb)} ingredients indexed")

    # Load PMI
    pmi = json.loads(PMI_PATH.read_text(encoding="utf-8")) if PMI_PATH.exists() else {}

    # Build Pinecone retriever
    print("Connecting to Pinecone...")
    api_key = os.environ.get("PINECONE_API_KEY")
    index_name = os.environ.get("PINECONE_INDEX_NAME", "vn-food-rag")
    if not api_key:
        print("ERROR: PINECONE_API_KEY not set")
        sys.exit(1)

    from pinecone import Pinecone
    from ingestion.embedding import EmbeddingModel
    from retrieval.retriever import Retriever

    pc = Pinecone(api_key=api_key)
    index = pc.Index(index_name)
    embed = EmbeddingModel()
    retriever = Retriever(embedding_model=embed, pinecone_index=index)
    print("  Pinecone ready")

    # Build LLM client
    from app.services.llm_client import LLMClient
    llm_client = LLMClient()

    # Run each model
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {}

    for model in args.models:
        print(f"\n--- Model: {model} ---")
        model_result = run_rag_llm_task2(
            model=model,
            retriever=retriever,
            llm_client=llm_client,
            gt_entries=gt_entries,
            name_index=name_index,
            pmi=pmi,
            k=args.k,
        )
        results[f"RAG+LLM ({model})"] = model_result
        print(f"  P@5={model_result['Precision@5']}  F1@5={model_result['F1@5']}  "
              f"Avg_PMI={model_result['Avg_PMI']}  parse_failures={model_result['parse_failures']}")

    out_path = OUT_DIR / "ir_task2_rag_llm.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\nResults → {out_path}")

    # Print comparison table
    print("\nTask 2 — RAG+LLM vs baselines")
    print(f"{'System':<30} {'P@5':>8} {'F1@5':>8} {'Avg PMI':>10}")
    print("-" * 60)
    for sys_name, m in results.items():
        print(f"{sys_name:<30} {m['Precision@5']:>8} {m['F1@5']:>8} {m['Avg_PMI']:>10}")

    # Load existing baselines for comparison
    existing = OUT_DIR / "ir_task2_results.json"
    if existing.exists():
        base = json.loads(existing.read_text())
        for sys_name, m in base.items():
            print(f"{sys_name:<30} {m['Precision@5']:>8} {m['F1@5']:>8} {m['Avg_PMI']:>10}")


if __name__ == "__main__":
    main()
