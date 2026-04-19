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


def _strip_accents(text: str) -> str:
    """Remove Vietnamese diacritics: nghêu → ngheu, bò → bo."""
    nfkd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


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
# Hierarchy loader (for substitute & complement filtering)
# ------------------------------------------------------------------

HIERARCHY_PATH = ROOT / "app" / "data" / "ontology" / "ingredient_hierarchy.json"


def load_hierarchy():
    """Load hierarchy; return (ing_to_class, classes) or (None, None)."""
    if not HIERARCHY_PATH.exists():
        return None, None
    h = json.loads(HIERARCHY_PATH.read_text(encoding="utf-8"))
    return h.get("ingredient_to_class", {}), h.get("classes", {})


def _get_parent_class(cls, classes):
    """Get the level-1 (top-level) ancestor of a leaf class."""
    cur = cls
    while cur and classes.get(cur, {}).get("parent") \
          and classes[cur]["parent"] != "Ingredient":
        cur = classes[cur]["parent"]
    return cur


# ------------------------------------------------------------------
# 1. substitutes(A, B, context) — two strategies combined
# ------------------------------------------------------------------

def _ingredient_name_tokens(ing):
    """All token forms that might appear in a dish name for this ingredient."""
    nn = (ing.get("name_normalized") or "").lower().strip()
    if not nn:
        return set()
    toks = nn.split()
    out = {nn}
    if toks:
        out.add(toks[-1])          # head noun: bò, gà, tôm
    if len(toks) >= 2:
        out.add(" ".join(toks[-2:]))  # 2-gram tail: cá lóc, thịt bò
    return out


def _remove_ingredient_from_name(dish_tokens, ing_tokens):
    """Remove ingredient tokens from dish name, return template string or None.
    Compares using accent-stripped forms since name_normalized has no accents
    but dish names do.
    """
    name = " ".join(dish_tokens)
    name_stripped = _strip_accents(name)
    for form in sorted(ing_tokens, key=len, reverse=True):
        form_stripped = _strip_accents(form)
        if form_stripped in name_stripped:
            # Find position in stripped string, replace in original
            idx = name_stripped.find(form_stripped)
            # Map back: count chars to find corresponding position in original
            tmpl = name[:idx].rstrip() + " _ " + name[idx + len(form_stripped):].lstrip()
            tmpl = re.sub(r"\s+", " ", tmpl).strip()
            if tmpl and tmpl != "_":
                return tmpl
    return None


def derive_substitutes(dishes, id_to_meta, name_to_id, norm_to_id):
    """
    Strategy A: For each dish, extract its primary ingredient (importance=3)
    and build a template = dish_name minus that ingredient. Group dishes by
    template → primary ingredients in the same group are substitutes.

    Filter: both ingredients must share the same top-level ontology class
    (Protein, Produce, Seasoning, Staple) if hierarchy is available,
    otherwise fall back to same flat category.
    """
    i2c, classes = load_hierarchy()

    # Build template → [(dish, primary_ingredient)] mapping
    buckets = defaultdict(list)

    for d in dishes:
        dtokens = _tokenize(d.get("name_vi", ""))
        if len(dtokens) < 2 or len(dtokens) > 10:
            continue
        # Get primary ingredients (importance=3 first, then importance=2)
        primaries = [ing for ing in d.get("ingredients", [])
                     if ing.get("importance", 0) == 3]
        if not primaries:
            primaries = [ing for ing in d.get("ingredients", [])
                         if ing.get("importance", 0) == 2]
        if not primaries:
            continue
        # Use the first primary ingredient
        main = primaries[0]
        name_forms = _ingredient_name_tokens(main)
        tmpl = _remove_ingredient_from_name(dtokens, name_forms)
        if tmpl:
            buckets[tmpl].append((d, main))

    subs = []
    seen = set()
    for tmpl, entries in buckets.items():
        if len(entries) < 2:
            continue
        # Collect unique ingredients in this template
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                di, ing_i = entries[i]
                dj, ing_j = entries[j]
                aid = ing_i["ingredient_id"]
                bid = ing_j["ingredient_id"]
                if aid == bid or di["id"] == dj["id"]:
                    continue
                a, b = sorted([aid, bid])
                key = (a, b, tmpl)
                if key in seen:
                    continue
                # Filter: same leaf class (hierarchy) or same category
                if i2c and classes:
                    cls_a = i2c.get(a)
                    cls_b = i2c.get(b)
                    if cls_a and cls_b:
                        if cls_a != cls_b:
                            continue
                    else:
                        ca = id_to_meta.get(a, {}).get("category")
                        cb = id_to_meta.get(b, {}).get("category")
                        if not ca or ca != cb:
                            continue
                else:
                    ca = id_to_meta.get(a, {}).get("category")
                    cb = id_to_meta.get(b, {}).get("category")
                    if not ca or ca != cb:
                        continue
                seen.add(key)
                subs.append({
                    "a": a,
                    "b": b,
                    "a_name": id_to_meta.get(a, {}).get("name_vi", ""),
                    "b_name": id_to_meta.get(b, {}).get("name_vi", ""),
                    "context": tmpl.replace("_", "…"),
                    "evidence": [di["id"], dj["id"]],
                })
    return subs


# ------------------------------------------------------------------
# 2. flavorComplements(A, B, npmi)
# ------------------------------------------------------------------

def derive_flavor_complements(npmi, id_to_meta, threshold=0.3):
    """
    NPMI >= threshold AND both ingredients share the same top-level ontology
    class (via hierarchy) or same flat category as fallback.
    """
    i2c, classes = load_hierarchy()
    complements = []
    seen = set()
    for a, peers in npmi.items():
        meta_a = id_to_meta.get(a)
        if not meta_a:
            continue
        for b, score in peers.items():
            if score < threshold or a == b:
                continue
            meta_b = id_to_meta.get(b)
            if not meta_b:
                continue
            # Same-class filter: hierarchy top-level or flat category
            if i2c and classes:
                cls_a = i2c.get(a)
                cls_b = i2c.get(b)
                if cls_a and cls_b:
                    if _get_parent_class(cls_a, classes) != \
                       _get_parent_class(cls_b, classes):
                        continue
                else:
                    if meta_a.get("category") != meta_b.get("category"):
                        continue
            else:
                if meta_a.get("category") != meta_b.get("category"):
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
            print(f"  {c['a_name']} + {c['b_name']} npmi={c['npmi']}")
    if conflicts:
        print("\nconflictsWith[0–2]:")
        for c in conflicts[:3]:
            print(f"  {c['a_name']} ⚠ {c['b_name']} ({c['severity']})")
    print("\nDone.")


if __name__ == "__main__":
    main()
