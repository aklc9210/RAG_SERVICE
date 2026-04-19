#!/usr/bin/env python3
"""Generate 200 class-level queries + GT for Task 1.

Queries are hand-crafted templates with randomized class/method slots,
producing natural Vietnamese search phrases. No LLM needed.

Usage:
    python scripts/build_task1_class_queries.py
"""
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from retrieval.ontology import FoodOntology

DKB = ROOT / "app" / "data" / "knowledge_base" / "dish_knowledge_base.json"
OUT = ROOT / "evaluation" / "data" / "task1_class_queries.jsonl"

VI = {
    "Seafood": ["hải sản", "tôm cua cá", "đồ biển"],
    "Meat": ["thịt heo", "thịt bò", "thịt"],
    "Poultry": ["gà", "vịt", "gia cầm"],
    "Offal": ["nội tạng", "lòng", "phá lấu"],
    "Egg": ["trứng", "trứng gà", "trứng vịt"],
    "CuredMeat": ["chả", "giò", "lạp xưởng", "thịt nguội"],
    "PlantProtein": ["đậu hũ", "đậu phụ", "đạm thực vật", "chay"],
    "Vegetable": ["rau", "rau xanh", "rau củ"],
    "Herb": ["rau thơm", "húng quế", "thảo mộc"],
    "RootVeg": ["củ", "khoai", "cà rốt"],
    "Mushroom": ["nấm", "nấm hương", "nấm đông cô"],
    "FreshFruit": ["trái cây", "hoa quả"],
    "DriedFruit": ["trái cây khô", "mứt", "nho khô"],
    "SaltyUmami": ["mặn", "nước mắm", "mắm"],
    "Spicy": ["cay", "ớt", "tiêu"],
    "SourSeasoning": ["chua", "me", "chanh"],
    "SweetSeasoning": ["ngọt", "đường"],
    "Aromatic": ["sả", "gừng", "tỏi", "thơm nồng"],
    "Grain": ["cơm", "gạo", "xôi"],
    "Noodle": ["bún", "phở", "mì", "miến"],
    "Flour": ["bột", "bột mì", "bột gạo"],
    "Bread": ["bánh mì"],
    "Milk": ["sữa", "sữa tươi"],
    "Cheese": ["phô mai", "phô mai mozzarella"],
}

METHOD_VI = {
    "Fry": ["chiên", "rán"],
    "StirFry": ["xào"],
    "Boil": ["luộc", "nấu canh"],
    "Stew": ["kho", "rim"],
    "Grill": ["nướng", "nướng than"],
    "Steam": ["hấp"],
    "Hotpot": ["lẩu", "nhúng"],
    "Bake": ["nướng lò", "làm bánh"],
    "Mix": ["gỏi", "trộn", "nộm"],
    "NoodleSoup": ["nấu nước", "nấu phở"],
}

# ── Query templates ──────────────────────────────────────────────

SINGLE_TEMPLATES = [
    "các món {ing}",
    "món {ing} ngon",
    "gợi ý món {ing}",
    "hôm nay ăn {ing} gì",
    "công thức món {ing}",
    "làm gì từ {ing}",
    "thực đơn {ing}",
    "{ing} chế biến kiểu gì",
    "món ngon từ {ing}",
    "tổng hợp món {ing}",
]

MULTI_TEMPLATES = [
    "món {a} kết hợp {b}",
    "{a} nấu với {b}",
    "món có {a} và {b}",
    "{a} {b} làm món gì",
    "kết hợp {a} với {b}",
    "gợi ý món {a} ăn kèm {b}",
    "thực đơn {a} và {b}",
    "món ngon từ {a} và {b}",
]

NEG_TEMPLATES = [
    "món {pos} không {neg}",
    "{pos} nhưng không có {neg}",
    "món {pos} cho người kiêng {neg}",
    "thay {neg} bằng gì trong món {pos}",
    "{pos} không dùng {neg}",
    "món {pos} bỏ {neg}",
    "gợi ý món {pos} không chứa {neg}",
]

METHOD_TEMPLATES = [
    "món {method} {ing}",
    "{ing} {method}",
    "cách {method} {ing}",
    "{method} {ing} ngon",
    "công thức {ing} {method}",
    "làm {ing} {method} kiểu gì",
    "{ing} {method} đơn giản",
]


def pick(d, cls):
    return random.choice(d[cls])


def build_gt(pos, neg, method, ont, dishes):
    pos_sets = [set(ont.get_descendants(c)) for c in pos]
    neg_ids = set()
    for c in neg:
        neg_ids |= set(ont.get_descendants(c))
    gt = []
    for d in dishes:
        ings = {i["ingredient_id"] for i in d.get("ingredients", [])}
        if pos_sets and not all(ings & ps for ps in pos_sets):
            continue
        if neg_ids and (ings & neg_ids):
            continue
        if method and ont.get_cooking_method(d["id"]) != method:
            continue
        gt.append(d["id"])
    return gt


def main():
    random.seed(42)
    FoodOntology._instance = None
    ont = FoodOntology()
    dishes = json.loads(DKB.read_text("utf-8"))
    classes = list(VI.keys())

    results = []

    def add(query, qtype, pos, neg, method):
        gt = build_gt(pos, neg, method, ont, dishes)
        if len(gt) < 3 or len(gt) > 5000:
            return False
        results.append({
            "query": query, "type": qtype,
            "classes_positive": pos, "classes_negative": neg,
            "cooking_method": method, "gt_dish_ids": gt, "gt_count": len(gt),
        })
        return True

    # ── single_class: 50 ──
    random.shuffle(classes)
    i = 0
    while sum(1 for r in results if r["type"] == "single_class") < 50:
        cls = classes[i % len(classes)]
        tmpl = random.choice(SINGLE_TEMPLATES)
        q = tmpl.format(ing=pick(VI, cls))
        add(q, "single_class", [cls], [], None)
        i += 1

    # ── multi_class: 50 ──
    i = 0
    while sum(1 for r in results if r["type"] == "multi_class") < 50:
        a, b = random.sample(classes, 2)
        tmpl = random.choice(MULTI_TEMPLATES)
        q = tmpl.format(a=pick(VI, a), b=pick(VI, b))
        add(q, "multi_class", [a, b], [], None)
        i += 1
        if i > 200:
            break

    # ── negation: 50 ──
    i = 0
    while sum(1 for r in results if r["type"] == "negation") < 50:
        pos_cls = random.choice(classes)
        neg_cls = random.choice([c for c in classes if c != pos_cls])
        tmpl = random.choice(NEG_TEMPLATES)
        q = tmpl.format(pos=pick(VI, pos_cls), neg=pick(VI, neg_cls))
        add(q, "negation", [pos_cls], [neg_cls], None)
        i += 1
        if i > 200:
            break

    # ── cooking_method: 50 ──
    methods = list(METHOD_VI.keys())
    i = 0
    while sum(1 for r in results if r["type"] == "cooking_method") < 50:
        cls = random.choice(classes)
        m = random.choice(methods)
        tmpl = random.choice(METHOD_TEMPLATES)
        q = tmpl.format(ing=pick(VI, cls), method=random.choice(METHOD_VI[m]))
        add(q, "cooking_method", [cls], [], m)
        i += 1
        if i > 200:
            break

    # Assign IDs
    for i, r in enumerate(results):
        r["query_id"] = f"q{i+1:03d}"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    tc = Counter(r["type"] for r in results)
    gt_sizes = [r["gt_count"] for r in results]
    cls_used = set()
    for r in results:
        cls_used.update(r["classes_positive"] + r["classes_negative"])

    print(f"Wrote {len(results)} queries → {OUT}")
    print(f"By type: {dict(tc)}")
    print(f"GT: min={min(gt_sizes)}, median={sorted(gt_sizes)[len(gt_sizes)//2]}, max={max(gt_sizes)}")
    print(f"Classes: {len(cls_used)}/{len(classes)}")
    print()
    for t in ["single_class", "multi_class", "negation", "cooking_method"]:
        typed = [r for r in results if r["type"] == t]
        print(f"=== {t} ===")
        for r in random.sample(typed, min(5, len(typed))):
            print(f"  \"{r['query']}\" → {r['gt_count']} dishes")
        print()


if __name__ == "__main__":
    main()
