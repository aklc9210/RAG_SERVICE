#!/usr/bin/env python3
"""Generate ontology-based reasons for LLM scores in task2_human_annotation_v2.csv.

Rules (do NOT change llm_mean_score or any other column):
  - score=0 (irrelevant)   : No shared class, different method, no flavor complement
  - score~0.33             : Weak/single incidental signal
  - score~0.67             : Some ontology overlap but weak
  - score=1.0 (acceptable) : At least one clear ontology signal
  - score~1.33             : Multiple moderate signals
  - score~1.67             : Strong multi-signal match
  - score=2.0 (excellent)  : Very strong ontology alignment

Reason is generated from five ontology components:
  1. Jaccard (shared ingredients)
  2. ClassOverlap (same leaf-class or sibling-class ingredients)
  3. MethodMatch (same cooking method)
  4. FlavorComplement (NPMI-based co-occurrence complement)
  5. SemanticSim (ingredient semantic similarity matrix)

Output: overwrites notes column in the CSV (score columns unchanged).
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from retrieval.ontology import FoodOntology

# ── Paths ─────────────────────────────────────────────────────
CSV_IN  = ROOT / "evaluation" / "annotation" / "task2_human_annotation_v2.csv"
CSV_OUT = CSV_IN  # overwrite in-place

DKB_PATH    = ROOT / "app" / "data" / "knowledge_base" / "dish_knowledge_base.json"
GT_PATH     = ROOT / "evaluation" / "data" / "datasets" / "task3_related_gt.jsonl"
SEM_PATH    = ROOT / "app" / "config" / "ingredient_semantic_matrices_v2.json"

# ── Load data ─────────────────────────────────────────────────
ont = FoodOntology()

dish_kb = {d["id"]: d for d in json.loads(DKB_PATH.read_text("utf-8"))}

dish_meta = {}          # dish_id -> [ingredient_id, ...]
with open(GT_PATH, encoding="utf-8") as f:
    for line in f:
        e = json.loads(line)
        dish_meta[e["dish_id"]] = e["ingredient_ids"]

sem_matrices = {}
if SEM_PATH.exists():
    data = json.loads(SEM_PATH.read_text("utf-8"))
    for section in ["vegetables", "proteins", "binders", "seasonings"]:
        for ing, sims in data.get(section, {}).items():
            sem_matrices[ing] = sims

# ── Component helpers ─────────────────────────────────────────

def get_iw(dish_id):
    """ingredient_id -> importance weight"""
    dish = dish_kb.get(dish_id, {})
    return {ing["ingredient_id"]: {3: 3.0, 2: 1.5}.get(ing.get("importance", 1), 0.5)
            for ing in dish.get("ingredients", [])}


def weighted_jaccard(a, b, wa, wb):
    sa, sb = set(a), set(b)
    shared = sa & sb
    union  = sa | sb
    if not union:
        return 0.0
    ws = sum(max(wa.get(i, 0.5), wb.get(i, 0.5)) for i in shared)
    wu = sum(max(wa.get(i, 0.5), wb.get(i, 0.5)) for i in union)
    return ws / wu if wu else 0.0


def class_overlap_detail(ings_a, ings_b):
    """Return (score, [(ing_a_name, cls_a, ing_b_name, cls_b, match_type)...])"""
    matches = []
    used_b = set()
    for a in ings_a:
        cls_a = ont.ing_to_class.get(a)
        if not cls_a:
            continue
        for j, b in enumerate(ings_b):
            if j in used_b:
                continue
            cls_b = ont.ing_to_class.get(b)
            if not cls_b:
                continue
            if cls_a == cls_b:
                mtype = "same_class"
            elif (ont.classes.get(cls_a, {}).get("parent") ==
                  ont.classes.get(cls_b, {}).get("parent")):
                mtype = "sibling_class"
            else:
                continue
            used_b.add(j)
            na = ont.ing_meta.get(a, {}).get("name_vi", a)
            nb = ont.ing_meta.get(b, {}).get("name_vi", b)
            matches.append((na, cls_a, nb, cls_b, mtype))
            break
    total = len(ings_a)
    score = sum(1.0 if m[4] == "same_class" else 0.5 for m in matches) / total if total else 0.0
    return score, matches


def flavor_complements_detail(ings_a, ings_b, top_n=3):
    """Return (score, [(a_name, b_name, npmi)...]) for top complement pairs"""
    set_b = set(ings_b)
    pairs = []
    for a in ings_a:
        for entry in ont._comps.get(a, []):
            if entry["id"] in set_b:
                na = ont.ing_meta.get(a, {}).get("name_vi", a)
                nb = ont.ing_meta.get(entry["id"], {}).get("name_vi", entry["id"])
                pairs.append((na, nb, entry["npmi"]))
    pairs.sort(key=lambda x: -x[2])
    total = len(ings_a) * len(ings_b) if ings_a and ings_b else 1
    score = sum(p[2] for p in pairs) / len(pairs) if pairs else 0.0
    return score, pairs[:top_n]


def semantic_sim_detail(ings_a, ings_b):
    """Return (score, [(a_name, b_name, sim)...]) for top semantic pairs"""
    pairs = []
    for a in ings_a:
        if a in sem_matrices:
            for b in ings_b:
                if b in sem_matrices[a]:
                    na = ont.ing_meta.get(a, {}).get("name_vi", a)
                    nb = ont.ing_meta.get(b, {}).get("name_vi", b)
                    pairs.append((na, nb, sem_matrices[a][b]))
    pairs.sort(key=lambda x: -x[2])
    score = sum(p[2] for p in pairs) / len(pairs) if pairs else 0.0
    return score, pairs[:3]


# ── Reason builder ────────────────────────────────────────────

CLASS_VI = {
    "Meat": "thịt đỏ", "Poultry": "gia cầm", "Seafood": "hải sản",
    "Egg": "trứng", "Offal": "nội tạng", "CuredMeat": "thịt chế biến",
    "PlantProtein": "protein thực vật", "Mushroom": "nấm",
    "Vegetable": "rau củ", "Herb": "rau thơm", "RootVeg": "củ quả",
    "FreshFruit": "trái cây", "DriedFruit": "trái cây khô",
    "Seasoning": "gia vị", "SaltyUmami": "gia vị mặn/umami",
    "Spicy": "gia vị cay", "SourSeasoning": "gia vị chua",
    "SweetSeasoning": "gia vị ngọt", "Aromatic": "gia vị thơm",
    "Staple": "tinh bột", "Noodle": "bún/mì/phở", "Flour": "bột",
    "Grain": "gạo/ngũ cốc", "Dairy": "sữa/phô mai",
    "Beverage": "đồ uống", "AnimalProtein": "protein động vật",
}

def cls_vi(c):
    return CLASS_VI.get(c, c)


def build_reason(anchor_id, cand_id, llm_score):
    ings_a = dish_meta.get(anchor_id, [])
    ings_b = dish_meta.get(cand_id, [])
    if not ings_a or not ings_b:
        return "Không đủ dữ liệu nguyên liệu để phân tích."

    wa = get_iw(anchor_id)
    wb = get_iw(cand_id)

    jac              = weighted_jaccard(ings_a, ings_b, wa, wb)
    cls_score, cls_matches = class_overlap_detail(ings_a, ings_b)
    method_a         = ont.get_cooking_method(anchor_id)
    method_b         = ont.get_cooking_method(cand_id)
    method_match     = (method_a and method_b and method_a == method_b)
    flav_score, flav_pairs = flavor_complements_detail(ings_a, ings_b)
    sem_score, sem_pairs   = semantic_sim_detail(ings_a, ings_b)

    parts = []

    # ── Shared ingredients (Jaccard) ──
    shared = list(set(ings_a) & set(ings_b))
    if shared:
        names = [ont.ing_meta.get(i, {}).get("name_vi", i) for i in shared[:4]]
        parts.append(f"Chia sẻ nguyên liệu chung: {', '.join(names)}"
                     + (f" (Jaccard={jac:.2f})" if jac > 0.05 else ""))

    # ── Class overlap ──
    same = [(m[0], m[1]) for m in cls_matches if m[4] == "same_class"]
    sib  = [(m[0], m[2], m[1]) for m in cls_matches if m[4] == "sibling_class"]
    if same:
        ex = same[:2]
        cls_name = cls_vi(ex[0][1])
        ing_names = [e[0] for e in ex]
        parts.append(f"Cùng nhóm ontology '{cls_name}': {', '.join(ing_names)}")
    if sib:
        ex = sib[:2]
        parts.append(f"Nhóm ontology liên quan (sibling): "
                     f"{ex[0][0]} ({cls_vi(ex[0][2])}) ↔ {ex[0][1]} ({cls_vi(ex[0][2])})")

    # ── Cooking method ──
    if method_match:
        parts.append(f"Cùng phương pháp chế biến: {method_a}")
    elif method_a and method_b:
        parts.append(f"Phương pháp khác nhau: {method_a} vs {method_b}")

    # ── Flavor complement ──
    if flav_pairs:
        p = flav_pairs[0]
        parts.append(f"Bổ trợ hương vị (NPMI={p[2]:.2f}): {p[0]} ↔ {p[1]}")

    # ── Semantic similarity ──
    if sem_pairs and sem_pairs[0][2] > 0.5:
        p = sem_pairs[0]
        parts.append(f"Tương đồng ngữ nghĩa nguyên liệu (sim={p[2]:.2f}): {p[0]} ↔ {p[1]}")

    # ── Verdict summary keyed to llm_score ──
    score = float(llm_score) if llm_score else 0.0
    if score == 0.0:
        verdict = "Không liên quan: thiếu tất cả tín hiệu ontology."
    elif score < 0.5:
        verdict = "Gần như không liên quan: tín hiệu ontology rất yếu."
    elif score < 1.0:
        verdict = "Liên quan thấp: chỉ có tín hiệu ontology yếu hoặc gián tiếp."
    elif score == 1.0:
        verdict = "Liên quan ở mức chấp nhận được: có ít nhất một tín hiệu ontology rõ ràng."
    elif score < 1.5:
        verdict = "Khá liên quan: nhiều tín hiệu ontology trùng khớp."
    elif score < 2.0:
        verdict = "Liên quan tốt: nhiều tín hiệu ontology mạnh."
    else:
        verdict = "Rất liên quan: tín hiệu ontology toàn diện và nhất quán."

    if not parts:
        parts.append("Không tìm thấy tín hiệu ontology trực tiếp (nguyên liệu thuộc các nhóm khác nhau).")

    return verdict + " | " + "; ".join(parts)


# ── Main ──────────────────────────────────────────────────────

def main():
    rows = []
    with open(CSV_IN, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    print(f"Processing {len(rows)} rows...")
    for i, row in enumerate(rows):
        anchor = row["anchor_dish_id"]
        cand   = row["candidate_dish_id"]
        score  = row.get("llm_mean_score", "0")
        reason = build_reason(anchor, cand, score)
        row["notes"] = reason
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(rows)}")

    # Write back — preserve all original columns and values
    with open(CSV_OUT, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Done. Written to {CSV_OUT}")
    # Show sample
    print("\nSample reason (row 0):")
    print(rows[0]["notes"])
    print("\nSample reason (row 5):")
    print(rows[5]["notes"])


if __name__ == "__main__":
    main()
