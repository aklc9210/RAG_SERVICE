#!/usr/bin/env python3
"""
Day 1 — Person A — Derive Named Relations from existing data.

Outputs:
    app/data/ontology/relations.json  — single consolidated file with 4 relations:
        - substitutes(ing_A, ing_B, context)
        - flavorComplements(ing_A, ing_B, npmi)
        - conflictsWith(ing_A, ing_B, severity, reason)
        - cookedBy(dish_id, method)

Derivation strategies:
    substitutes: dish pairs differing by exactly 1 content token where the differing
                 token matches a main ingredient → those ingredients are substitutes
                 in the context of the remaining name template.
    flavorComplements: NPMI > 0.3 AND both ingredients share the same flat category
                       (category is a proxy for "same parent class" until hierarchy ready).
    conflictsWith: read from app/data/conflict/ingredient_conflict.json, normalize
                   ingredient names, keep un-resolvable names as raw strings
                   (some refer to classes like "Rau giàu vitamin C").
    cookedBy: map dish category (mon xao, mon kho, ...) to a CookingMethod label.

Usage:
    python scripts/build_ontology_relations.py
    python scripts/build_ontology_relations.py --npmi-threshold 0.3
"""

import argparse
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DISH_KB = ROOT / "app" / "data" / "knowledge_base" / "dish_knowledge_base.json"
ING_KB = ROOT / "app" / "data" / "knowledge_base" / "ingredient_knowledge_base.json"
NPMI_PATH = ROOT / "app" / "data" / "cooccurrence" / "npmi.json"
CONFLICT_PATH = ROOT / "app" / "data" / "conflict" / "ingredient_conflict.json"
OUT_DIR = ROOT / "app" / "data" / "ontology"
OUT_FILE = OUT_DIR / "relations.json"


# Map dish category → cooking method
CATEGORY_TO_METHOD = {
    "mon chien":       "Fry",
    "mon xao":         "StirFry",
    "mon canh":        "Boil",
    "mon kho":         "Stew",
    "mon kho - mam":   "Stew",
    "mon nuong":       "Grill",
    "mon hap":         "Steam",
    "mon lau":         "Hotpot",
    "mon chao":        "Porridge",
    "mon nuoc":        "NoodleSoup",
    "mon goi - salad": "Mix",
    "mon cuon - tron": "Roll",
    "mon banh":        "Bake",
    "mon trang mieng": "Dessert",
    "mon kem":         "FrozenDessert",
    "mon che":         "SweetSoup",
    "tra sua":         "MilkTea",
    "nuoc ep":         "Juice",
    "sinh to":         "Smoothie",
    "thuc uong":       "Beverage",
    "an vat":          "Snack",
    "mon tu ga":       "ChickenBased",
    "mon tu bo":       "BeefBased",
    "ngay le tet":     "Festive",
    "mon chay":        "Vegetarian",
}


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "").lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokenize(text: str):
    return _normalize(text).split()


# ------------------------------------------------------------------
# Loaders
# ------------------------------------------------------------------

def load_dishes():
    return json.loads(DISH_KB.read_text(encoding="utf-8"))


def load_ingredients():
    ikb = json.loads(ING_KB.read_text(encoding="utf-8"))
    name_to_id = {}
    norm_to_id = {}
    id_to_meta = {}
    for e in ikb:
        iid = e["id"]
        id_to_meta[iid] = e
        n = e.get("name_vi", "").lower().strip()
        nn = e.get("name_normalized", "").lower().strip()
        if n:
            name_to_id[n] = iid
        if nn:
            norm_to_id[nn] = iid
        for syn in e.get("synonyms") or []:
            s = syn.lower().strip()
            if s and s not in name_to_id:
                name_to_id[s] = iid
    return id_to_meta, name_to_id, norm_to_id


def resolve_ingredient_name(name, name_to_id, norm_to_id):
    nl = name.lower().strip()
    if nl in name_to_id:
        return name_to_id[nl]
    nn = _normalize(name)
    if nn in norm_to_id:
        return norm_to_id[nn]
    return None


# ------------------------------------------------------------------
# 1. substitutes(A, B, context) — dish name pairs differing by 1 token
# ------------------------------------------------------------------

def _ingredient_slot_tokens(ing):
    """
    Candidate slot-token forms for an ingredient.
    E.g. ingredient 'Thịt bò' (normalized 'thit bo') → {'thit bo', 'bo'}
    The last token is the head noun and commonly appears in dish names.
    """
    nn = (ing.get("name_normalized") or "").lower().strip()
    if not nn:
        return set()
    toks = nn.split()
    out = {nn}
    if toks:
        out.add(toks[-1])   # head noun (bò, gà, cá, ...)
    return out


def derive_substitutes(dishes, id_to_meta, name_to_id, norm_to_id):
    """
    For each pair of dishes whose names differ by exactly one position,
    check if both slot tokens map to a main ingredient (importance >= 2) of
    their respective dish — either the full normalized name or its head noun.
    If yes, record substitutes(A, B, context=remaining_template).
    """
    # Pre-compute per-dish: token_list, and for each main ingredient the set of
    # slot forms. Build template bucket = (tuple of tokens with slot replaced by "_").
    buckets = defaultdict(list)   # template_tuple → [(dish, slot_token, ing)]

    for d in dishes:
        tokens = _tokenize(d.get("name_vi", ""))
        n = len(tokens)
        if n < 2 or n > 8:
            continue
        mains = [ing for ing in d.get("ingredients", [])
                 if ing.get("importance", 0) >= 2]
        for ing in mains:
            slot_forms = _ingredient_slot_tokens(ing)
            for idx in range(n):
                tok = tokens[idx]
                # Single-token match (head noun in dish name)
                if tok in slot_forms:
                    template = tuple(tokens[:idx] + ["_"] + tokens[idx + 1:])
                    buckets[template].append((d, tok, ing))
                    continue
                # 2-token match for 'thit bo' style ingredients in a 'thit _' window
                if idx + 1 < n:
                    bigram = f"{tok} {tokens[idx + 1]}"
                    if bigram in slot_forms:
                        template = tuple(tokens[:idx] + ["_"] + tokens[idx + 2:])
                        buckets[template].append((d, bigram, ing))

    subs = []
    seen = set()
    for template, entries in buckets.items():
        if len(entries) < 2:
            continue
        # Deduplicate by (dish_id, ing_id) so we don't pair a dish with itself
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                di, slot_i, ing_i = entries[i]
                dj, slot_j, ing_j = entries[j]
                if di["id"] == dj["id"]:
                    continue
                if ing_i["ingredient_id"] == ing_j["ingredient_id"]:
                    continue
                # Same-category filter reduces spurious pairs
                # (e.g. 'chanh' ↔ 'coca cola' in context 'bánh')
                cat_i = id_to_meta.get(ing_i["ingredient_id"], {}).get("category")
                cat_j = id_to_meta.get(ing_j["ingredient_id"], {}).get("category")
                if not cat_i or cat_i != cat_j:
                    continue
                a, b = sorted([ing_i["ingredient_id"], ing_j["ingredient_id"]])
                context = " ".join(t for t in template if t != "_")
                key = (a, b, context)
                if key in seen:
                    continue
                seen.add(key)
                subs.append({
                    "a": a,
                    "b": b,
                    "a_name": id_to_meta.get(a, {}).get("name_vi", ""),
                    "b_name": id_to_meta.get(b, {}).get("name_vi", ""),
                    "context": context,
                    "evidence": [di["id"], dj["id"]],
                })
    return subs


# ------------------------------------------------------------------
# 2. flavorComplements(A, B, npmi)
# ------------------------------------------------------------------

def derive_flavor_complements(npmi, id_to_meta, threshold=0.3):
    """
    NPMI >= threshold AND both ingredients share the same flat category.
    (Category acts as a proxy for 'same parent class' until Person B's hierarchy
    is ready; swap in hierarchy lookup in Day 2 integration.)
    """
    complements = []
    seen = set()
    for a, peers in npmi.items():
        meta_a = id_to_meta.get(a)
        if not meta_a:
            continue
        cat_a = meta_a.get("category")
        if not cat_a:
            continue
        for b, score in peers.items():
            if score < threshold or a == b:
                continue
            meta_b = id_to_meta.get(b)
            if not meta_b:
                continue
            if meta_b.get("category") != cat_a:
                continue
            x, y = sorted([a, b])
            if (x, y) in seen:
                continue
            seen.add((x, y))
            complements.append({
                "a": x,
                "b": y,
                "a_name": id_to_meta.get(x, {}).get("name_vi", ""),
                "b_name": id_to_meta.get(y, {}).get("name_vi", ""),
                "category": cat_a,
                "npmi": round(score, 4),
            })
    complements.sort(key=lambda r: r["npmi"], reverse=True)
    return complements


# ------------------------------------------------------------------
# 3. conflictsWith(A, B, severity, reason)
# ------------------------------------------------------------------

def derive_conflicts(conflicts_raw, id_to_meta, name_to_id, norm_to_id):
    """
    Expand the rule list into binary conflict pairs.
    Some names refer to classes (e.g. "Rau giàu vitamin C") — keep these as
    string-only relations for later mapping to ontology classes.
    """
    pairs = []
    seen = set()
    for rule in conflicts_raw:
        for a_name in rule.get("ingre", []):
            a_id = resolve_ingredient_name(a_name, name_to_id, norm_to_id)
            for b_name in rule.get("conflicts", []):
                b_id = resolve_ingredient_name(b_name, name_to_id, norm_to_id)
                key_parts = [a_id or f"name:{a_name.lower().strip()}",
                             b_id or f"name:{b_name.lower().strip()}"]
                key = tuple(sorted(key_parts))
                if key in seen:
                    continue
                seen.add(key)
                pairs.append({
                    "a": a_id,
                    "b": b_id,
                    "a_name": a_name,
                    "b_name": b_name,
                    "a_resolved": a_id is not None,
                    "b_resolved": b_id is not None,
                    "severity": rule.get("severity"),
                    "reason": rule.get("reason"),
                    "rule_id": rule.get("id"),
                })
    return pairs


# ------------------------------------------------------------------
# 4. cookedBy(dish, method)
# ------------------------------------------------------------------

def derive_cooked_by(dishes):
    """
    Map each dish's category → a canonical cooking method label.
    Also apply name-token override (e.g. 'nướng' in name → Grill even if category is mixed).
    """
    name_overrides = {
        "nuong": "Grill",
        "chien": "Fry",
        "xao": "StirFry",
        "kho": "Stew",
        "canh": "Boil",
        "hap": "Steam",
        "luoc": "Boil",
        "lau": "Hotpot",
        "chao": "Porridge",
        "cuon": "Roll",
        "tron": "Mix",
        "goi": "Mix",
    }
    out = []
    for d in dishes:
        cat = d.get("category", "")
        method = CATEGORY_TO_METHOD.get(cat, "Other")
        # Name-token override: strong signal from dish name
        for tok in _tokenize(d.get("name_vi", "")):
            if tok in name_overrides:
                method = name_overrides[tok]
                break
        out.append({
            "dish_id": d["id"],
            "dish_name": d.get("name_vi", ""),
            "method": method,
            "category": cat,
        })
    return out


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--npmi-threshold", type=float, default=0.3)
    return p.parse_args()


def main():
    args = parse_args()
    print("=== Building Ontology Relations (Day 1 — Person A) ===")

    print("Loading dishes, ingredients, NPMI, conflicts...")
    dishes = load_dishes()
    id_to_meta, name_to_id, norm_to_id = load_ingredients()
    npmi = json.loads(NPMI_PATH.read_text(encoding="utf-8"))
    conflicts_raw = json.loads(CONFLICT_PATH.read_text(encoding="utf-8"))
    print(f"  Dishes: {len(dishes)}")
    print(f"  Ingredients: {len(id_to_meta)}")
    print(f"  NPMI ingredients: {len(npmi)}")
    print(f"  Conflict rules: {len(conflicts_raw)}")

    print("\n[1/4] Deriving substitutes...")
    subs = derive_substitutes(dishes, id_to_meta, name_to_id, norm_to_id)
    print(f"  → {len(subs)} substitute triples")

    print(f"\n[2/4] Deriving flavorComplements (NPMI ≥ {args.npmi_threshold}, same category)...")
    complements = derive_flavor_complements(npmi, id_to_meta, threshold=args.npmi_threshold)
    print(f"  → {len(complements)} complement pairs")

    print("\n[3/4] Formatting conflictsWith...")
    conflicts = derive_conflicts(conflicts_raw, id_to_meta, name_to_id, norm_to_id)
    resolved = sum(1 for c in conflicts if c["a_resolved"] and c["b_resolved"])
    print(f"  → {len(conflicts)} conflict pairs ({resolved} fully resolved)")

    print("\n[4/4] Deriving cookedBy...")
    cooked_by = derive_cooked_by(dishes)
    from collections import Counter
    by_method = Counter(c["method"] for c in cooked_by)
    print(f"  → {len(cooked_by)} dish-method entries")
    print(f"  Top methods: {dict(by_method.most_common(8))}")

    # Consolidated output
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {
            "source_dishes": len(dishes),
            "source_ingredients": len(id_to_meta),
            "npmi_threshold": args.npmi_threshold,
            "counts": {
                "substitutes": len(subs),
                "flavorComplements": len(complements),
                "conflictsWith": len(conflicts),
                "cookedBy": len(cooked_by),
            },
        },
        "substitutes": subs,
        "flavorComplements": complements,
        "conflictsWith": conflicts,
        "cookedBy": cooked_by,
    }
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWritten: {OUT_FILE}")
    print(f"File size: {OUT_FILE.stat().st_size / 1024:.1f} KB")

    # Sample preview
    print("\n=== Samples ===")
    if subs:
        print("\nsubstitutes[0–2]:")
        for s in subs[:3]:
            print(f"  {s['a_name']} ↔ {s['b_name']} (context: '{s['context']}')")
    if complements:
        print("\nflavorComplements[0–2] (top NPMI):")
        for c in complements[:3]:
            print(f"  {c['a_name']} + {c['b_name']} [{c['category']}] npmi={c['npmi']}")
    if conflicts:
        print("\nconflictsWith[0–2]:")
        for c in conflicts[:3]:
            print(f"  {c['a_name']} ⚠ {c['b_name']} ({c['severity']})")
    print("\nDone.")


if __name__ == "__main__":
    main()
