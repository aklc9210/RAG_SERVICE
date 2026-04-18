#!/usr/bin/env python3
"""
Day 1 — Person B — Build ingredient hierarchy via LLM classification.

Approach:
  1. Define a 4-level class tree manually (TREE constant, 49 classes, 38 leaves).
  2. For each ingredient in ingredient_knowledge_base.json, ask an Ollama LLM
     to choose ONE leaf class from the 38 options, conditioned on the leaf
     definitions + ingredient (name_vi, name_normalized, name_en, category,
     synonyms).
  3. Batch-prompt (default 25 items/call) for throughput; temperature=0 for
     reproducibility.
  4. Checkpoint per batch → resume safe on re-run.
  5. Invalid / missing answers fall back to per-item retry, then to "Other".

Outputs:
  app/data/ontology/ingredient_hierarchy.json
      {
        "classes": {class_id: {parent, level, children}},
        "ingredient_to_class": {ingredient_id: leaf_class_id},
        "class_members": {class_id: [ingredient_ids...]},
        "metadata": {
            "n_ingredients": ..., "n_classes": 49, "max_depth": 3,
            "classifier": "ollama:qwen2.5:7b",
            "leaf_class_counts": {...},
            "unresolved": [ingredient_id, ...]
        }
      }

  app/data/ontology/.hierarchy_checkpoint.json   (auto-managed; delete to rerun)

Usage:
    python scripts/build_ingredient_hierarchy.py
    python scripts/build_ingredient_hierarchy.py --limit 200        # test run
    python scripts/build_ingredient_hierarchy.py --batch-size 20
    python scripts/build_ingredient_hierarchy.py --reset            # drop checkpoint
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.llm_client import LLMClient  # noqa: E402

IKB = ROOT / "app" / "data" / "knowledge_base" / "ingredient_knowledge_base.json"
OUT = ROOT / "app" / "data" / "ontology" / "ingredient_hierarchy.json"
CKPT = ROOT / "app" / "data" / "ontology" / ".hierarchy_checkpoint.json"


# ------------------------------------------------------------------
# Class tree (manually designed, 4 levels, 49 classes, 38 leaves)
# ------------------------------------------------------------------

TREE: Dict[str, List[str]] = {
    "Ingredient": ["Protein", "Produce", "Seasoning", "Staple",
                   "Dairy", "Beverage", "Sweet", "Processed", "Other"],

    "Protein": ["AnimalProtein", "PlantProtein"],
    "AnimalProtein": ["Meat", "Poultry", "Offal", "Seafood", "CuredMeat", "Egg"],

    "Produce": ["Herb", "Vegetable", "RootVeg", "Mushroom", "FreshFruit", "DriedFruit"],

    "Seasoning": ["SaltyUmami", "SweetSeasoning", "SourSeasoning",
                  "Spicy", "Aromatic", "OtherSeasoning"],

    "Staple": ["Grain", "Noodle", "Flour", "Bread"],

    "Dairy": ["Milk", "Cheese", "IceCream", "Yogurt"],

    "Beverage": ["Alcohol", "SoftDrink", "Coffee", "Tea", "OtherBeverage"],

    "Sweet": ["Candy", "Cake", "Jam", "Snack"],

    "Processed": ["InstantFood", "OtherProcessed"],
}


# ------------------------------------------------------------------
# Leaf class definitions (fed to the LLM as the label space)
# ------------------------------------------------------------------

LEAF_DEFS: Dict[str, str] = {
    # Protein
    "Meat":            "Red meat (pork/beef/lamb/goat) — thịt heo, bò, cừu, dê",
    "Poultry":         "Poultry meat — gà, vịt, ngan, ngỗng, chim cút",
    "Offal":           "Organ/offal — lòng, gan, tim, cật, huyết, mề",
    "Seafood":         "Fish/shellfish/mollusks — cá, tôm, cua, mực, nghêu, sò, sứa, ốc",
    "CuredMeat":       "Cured/processed meat — giò chả, xúc xích, lạp xưởng, chà bông, thịt xông khói",
    "Egg":             "Eggs (any animal) — trứng gà, trứng vịt, trứng cút, trứng muối",
    "PlantProtein":    "Plant-based protein — đậu hũ, tàu hũ, đậu phụ, đạm thực vật, mì căn, natto",

    # Produce
    "Herb":            "Fresh aromatic herbs (leaves used raw) — húng, ngò, thì là, rau mùi, bạc hà, kinh giới",
    "Vegetable":       "Leafy/fruit vegetables (non-root, non-herb) — cải, bí, mướp, cà tím, bắp cải, rau muống",
    "RootVeg":         "Root/tuber vegetables — khoai, củ cải, cà rốt, khoai tây, khoai lang, củ sen",
    "Mushroom":        "Mushrooms — nấm kim châm, nấm rơm, nấm hương, mộc nhĩ",
    "FreshFruit":      "Fresh fruits — xoài, chuối, táo, cam, dứa, dưa hấu",
    "DriedFruit":      "Dried fruits/nuts/seeds — nho khô, hạt điều, hạt sen khô, táo đỏ khô, óc chó",
    "Aromatic":        "Fresh aromatic alliums/rhizomes used as base (cut into dishes) — tỏi, sả, gừng, hành tím, hành lá, hẹ, riềng",

    # Seasoning
    "SaltyUmami":      "Salty/umami seasonings — muối, nước mắm, nước tương, maggi, bột nêm, dầu hào, tương",
    "SweetSeasoning":  "Sweet seasonings — đường, mật ong, đường thốt nốt, siro, mạch nha",
    "SourSeasoning":   "Sour/acid seasonings — giấm, chanh (nước cốt), me, khế chua, giấm táo",
    "Spicy":           "Hot/pungent seasonings — ớt, tiêu, mù tạt, sa tế, tương ớt",
    "OtherSeasoning":  "Other culinary seasonings/sauces/oils — dầu ăn, dầu mè, bơ, mayonnaise, sốt, gia vị khô, ngũ vị hương, vanilla",

    # Staple
    "Grain":           "Whole grains/rice — gạo, nếp, lúa mạch, yến mạch, kê, hạt quinoa",
    "Noodle":          "Noodles/pasta (made form) — bún, phở, mì (sợi), miến, hủ tiếu, bánh phở, spaghetti",
    "Flour":           "Flour/starch powders — bột mì, bột gạo, bột năng, bột bắp, bột nở",
    "Bread":           "Bread and bread products — bánh mì, baguette, bánh sandwich",

    # Dairy
    "Milk":            "Milk and cream — sữa tươi, sữa đặc, kem tươi, whipping cream, sữa chua uống",
    "Cheese":          "Cheese — phô mai, cheddar, mozzarella, cream cheese",
    "IceCream":        "Ice cream/frozen dessert — kem lạnh, gelato, sorbet",
    "Yogurt":          "Yogurt — sữa chua (ăn), yoghurt đặc",

    # Beverage
    "Alcohol":         "Alcoholic drinks — rượu, bia, vang, sake, whisky, vodka",
    "SoftDrink":       "Non-alcoholic bottled drinks — coca cola, pepsi, nước ngọt, nước giải khát có gas",
    "Coffee":          "Coffee — cà phê (pha/hòa tan/hạt)",
    "Tea":             "Tea — trà, chè xanh, trà sữa, hồng trà",
    "OtherBeverage":   "Other drinks — nước ép, sinh tố, nước lọc, nước dừa (chỉ uống, không dùng nấu)",

    # Sweet
    "Candy":           "Candy/confectionery — kẹo, socola, chocolate bar",
    "Cake":            "Cake/pastry — bánh kem, bánh quy, bánh ngọt, bánh bông lan",
    "Jam":             "Jam/spread/nut butter — mứt, bơ đậu phộng, bơ hạt, nutella",
    "Snack":           "Packaged snacks — bim bim, snack khoai tây, rong biển ăn liền, kẹo cao su",

    # Processed
    "InstantFood":     "Ready-to-eat meals — mì gói, cháo gói, thức ăn đông lạnh, đồ hộp ăn liền",
    "OtherProcessed":  "Other processed items that do not fit above",

    # Fallback
    "Other":           "Truly ambiguous / non-food / unclassifiable items only (use sparingly)",
}

LEAF_SET = set(LEAF_DEFS.keys())


# ------------------------------------------------------------------
# LLM prompt
# ------------------------------------------------------------------

SYSTEM_PROMPT = """You are a Vietnamese food ontology classifier.

Given a list of ingredients, assign EACH ingredient to EXACTLY ONE leaf class
from the taxonomy. Use the full context: Vietnamese name, English name,
original category tag, and synonyms.

Guidelines:
- Pick the MOST SPECIFIC class that fits (e.g. "thịt bò" → Meat, not Protein).
- Aromatic alliums (tỏi, sả, gừng, hành lá, hẹ, riềng) → "Aromatic", not "Vegetable".
- Fresh leafy herbs (húng, ngò, thì là, kinh giới) → "Herb".
- "bột mì/bột gạo/bột bắp" → "Flour" (NOT Noodle — only finished noodle strands are Noodle).
- Cooking liquids like "nước cốt chanh", "nước cốt me" → SourSeasoning; "nước cốt dừa" → OtherSeasoning.
- "sứa" is jellyfish → Seafood (even if KB tags it fresh_fruits).
- Finished dishes served as snacks → Snack; frozen/instant meals → InstantFood.
- Use "Other" ONLY when truly ambiguous or non-food.

Output: a single JSON array of objects with fields "id" and "class".
Do NOT output any prose, markdown, or explanation — only the JSON array."""


def build_leaf_menu() -> str:
    lines = ["LEAF CLASSES (pick exactly one id from this list):"]
    for leaf, desc in LEAF_DEFS.items():
        lines.append(f"- {leaf}: {desc}")
    return "\n".join(lines)


def format_item(ing: Dict[str, Any]) -> str:
    syns = ing.get("synonyms") or []
    syn_str = ", ".join(syns[:4]) if syns else "—"
    return (
        f'- id: {ing["id"]}\n'
        f'  name_vi: {ing.get("name_vi", "")}\n'
        f'  name_normalized: {ing.get("name_normalized", "")}\n'
        f'  name_en: {ing.get("name_en", "")}\n'
        f'  category: {ing.get("category", "")}\n'
        f'  synonyms: {syn_str}'
    )


def build_user_prompt(batch: List[Dict[str, Any]]) -> str:
    menu = build_leaf_menu()
    body = "\n".join(format_item(i) for i in batch)
    return (
        f"{menu}\n\n"
        f"INGREDIENTS ({len(batch)} items):\n{body}\n\n"
        f'Respond with ONLY a JSON array like: '
        f'[{{"id": "ingre00001", "class": "Flour"}}, ...]\n'
        f"Every id in the input MUST appear exactly once in the output."
    )


# ------------------------------------------------------------------
# Canonicalization (dedup key so "boa ro", "boa-ro", "boa - ro" share one LLM call)
# ------------------------------------------------------------------

_PUNCT_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)
_WS_RE = re.compile(r"\s+")


def canonical_key(ing: Dict[str, Any]) -> Tuple[str, str]:
    """Key that collapses spelling variants of the same ingredient+category."""
    raw = (ing.get("name_normalized") or ing.get("name_vi") or "").lower()
    raw = unicodedata.normalize("NFKC", raw)
    raw = _PUNCT_RE.sub(" ", raw)
    raw = _WS_RE.sub(" ", raw).strip()
    cat = (ing.get("category") or "").lower().strip()
    return (raw, cat)


# ------------------------------------------------------------------
# LLM response parsing
# ------------------------------------------------------------------

_JSON_ARRAY_RE = re.compile(r"\[[\s\S]*\]")


def parse_llm_response(text: str) -> List[Dict[str, str]]:
    """Extract the first JSON array from LLM output, tolerating code fences."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    m = _JSON_ARRAY_RE.search(text)
    if not m:
        raise ValueError("No JSON array found in response")
    arr = json.loads(m.group(0))
    if not isinstance(arr, list):
        raise ValueError("Top-level JSON is not a list")
    return arr


def classify_batch(
    client: LLMClient, batch: List[Dict[str, Any]], max_retries: int = 2
) -> Dict[str, str]:
    """Send one batch; return {ingredient_id: leaf_class} for valid mappings."""
    prompt = build_user_prompt(batch)
    last_err: Optional[str] = None
    for attempt in range(max_retries + 1):
        try:
            raw = client.chat(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=SYSTEM_PROMPT,
                temperature=0.0,
                max_tokens=4096,
            )
            arr = parse_llm_response(raw)
            out: Dict[str, str] = {}
            for row in arr:
                iid = str(row.get("id", "")).strip()
                cls = str(row.get("class", "")).strip()
                if iid and cls in LEAF_SET:
                    out[iid] = cls
            return out
        except Exception as exc:  # noqa: BLE001
            last_err = f"{type(exc).__name__}: {exc}"
            time.sleep(1.0 * (attempt + 1))
    print(f"    [warn] batch failed after retries: {last_err}")
    return {}


# ------------------------------------------------------------------
# Checkpoint helpers
# ------------------------------------------------------------------

def load_checkpoint() -> Dict[str, str]:
    if CKPT.exists():
        try:
            return json.loads(CKPT.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            print(f"[warn] checkpoint unreadable, starting fresh")
    return {}


def save_checkpoint(mapping: Dict[str, str]) -> None:
    CKPT.parent.mkdir(parents=True, exist_ok=True)
    CKPT.write_text(json.dumps(mapping, ensure_ascii=False), encoding="utf-8")


# ------------------------------------------------------------------
# Tree helpers
# ------------------------------------------------------------------

def build_classes_dict() -> Dict[str, Dict[str, Any]]:
    """Flatten TREE into {class_id: {parent, level, children}}."""
    classes: Dict[str, Dict[str, Any]] = {}
    parent_of: Dict[str, Optional[str]] = {"Ingredient": None}

    # BFS to fix parents and levels
    stack = [("Ingredient", 0)]
    while stack:
        node, level = stack.pop()
        children = TREE.get(node, [])
        classes[node] = {
            "parent": parent_of.get(node),
            "level": level,
            "children": children,
        }
        for c in children:
            parent_of[c] = node
            stack.append((c, level + 1))

    # Ensure every declared leaf exists as a class
    for leaf in LEAF_DEFS:
        if leaf not in classes:
            classes[leaf] = {"parent": "Other" if leaf != "Other" else "Ingredient",
                             "level": 2, "children": []}
    return classes


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None,
                    help="Classify only the first N ingredients (debug).")
    ap.add_argument("--batch-size", type=int, default=15)
    ap.add_argument("--reset", action="store_true",
                    help="Delete checkpoint and start from scratch.")
    args = ap.parse_args()

    if args.reset and CKPT.exists():
        CKPT.unlink()
        print(f"[info] removed checkpoint {CKPT}")

    # Load ingredients
    kb = json.loads(IKB.read_text(encoding="utf-8"))
    if isinstance(kb, dict):
        kb = list(kb.values())
    if args.limit:
        kb = kb[: args.limit]
    print(f"[info] total ingredients: {len(kb)}")

    # Group by canonical key so spelling variants share ONE LLM call
    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for ing in kb:
        groups[canonical_key(ing)].append(ing)
    reps: List[Dict[str, Any]] = [members[0] for members in groups.values()]
    print(f"[info] canonical groups: {len(reps)} (saves {len(kb) - len(reps)} calls)")

    # Resume (checkpoint is per-ingredient id; derive rep coverage)
    mapping: Dict[str, str] = load_checkpoint()
    already = len(mapping)
    print(f"[info] resumed {already} from checkpoint")

    todo_reps = [r for r in reps if r["id"] not in mapping]
    print(f"[info] reps still to classify: {len(todo_reps)}")

    client = LLMClient()
    print(f"[info] using model: {client.model} @ {client.base_url}")

    bs = args.batch_size
    n_batches = (len(todo_reps) + bs - 1) // bs
    t_start = time.time()
    for i in range(0, len(todo_reps), bs):
        batch = todo_reps[i : i + bs]
        idx = i // bs + 1
        got = classify_batch(client, batch)

        # Per-item retry for any item the batch missed
        missing = [ing for ing in batch if ing["id"] not in got]
        if missing:
            for ing in missing:
                single = classify_batch(client, [ing])
                got.update(single)

        # Final fallback → "Other"
        for ing in batch:
            if ing["id"] not in got:
                got[ing["id"]] = "Other"

        mapping.update(got)
        save_checkpoint(mapping)
        elapsed = time.time() - t_start
        rate = (i + len(batch)) / max(elapsed, 1e-6)
        eta = (len(todo_reps) - (i + len(batch))) / max(rate, 1e-6)
        print(f"  batch {idx}/{n_batches}  +{len(got)}  "
              f"reps={len(mapping)}  rate={rate:.1f}/s  eta={eta:.0f}s")

    # Propagate rep class → all group members
    for members in groups.values():
        rep_id = members[0]["id"]
        if rep_id not in mapping:
            continue
        cls = mapping[rep_id]
        for m in members[1:]:
            mapping[m["id"]] = cls
    save_checkpoint(mapping)

    # Assemble final JSON
    classes = build_classes_dict()
    class_members: Dict[str, List[str]] = defaultdict(list)
    for iid, cls in mapping.items():
        class_members[cls].append(iid)

    unresolved = [iid for iid, cls in mapping.items() if cls == "Other"]
    leaf_counts = Counter(mapping.values())

    out_doc = {
        "metadata": {
            "n_ingredients": len(mapping),
            "n_classes": len(classes),
            "max_depth": max(c["level"] for c in classes.values()),
            "classifier": f"ollama:{client.model}",
            "leaf_class_counts": dict(leaf_counts),
            "unresolved": unresolved,
        },
        "classes": classes,
        "ingredient_to_class": mapping,
        "class_members": dict(class_members),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[done] wrote {OUT}  ({OUT.stat().st_size / 1024:.1f} KB)")

    # Spot-check printout
    kb_by_id = {ing["id"]: ing for ing in kb}
    print("\n=== Leaf distribution ===")
    for leaf, n in leaf_counts.most_common():
        print(f"  {leaf}: {n}")

    print("\n=== 30 random placements ===")
    random.seed(42)
    for iid in random.sample(list(mapping.keys()), min(30, len(mapping))):
        ing = kb_by_id.get(iid, {})
        print(f"  [{ing.get('category', '?'):20s}] "
              f"{ing.get('name_normalized', ''):35s} → {mapping[iid]}")


if __name__ == "__main__":
    main()
