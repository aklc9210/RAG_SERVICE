#!/usr/bin/env python3
"""Verify paper claims against actual data files."""
import json, re

BASE = "app/data"
ONT = f"{BASE}/ontology"

rel = json.load(open(f"{ONT}/relations.json"))
hier = json.load(open(f"{ONT}/dish_hierarchy.json"))
ing_hier = json.load(open(f"{ONT}/ingredient_hierarchy.json"))
dishes = json.load(open(f"{BASE}/knowledge_base/dish_knowledge_base.json"))

def check(label, claimed, actual):
    status = "✅ MATCH" if claimed == actual else "❌ MISMATCH"
    print(f"  {label:30s} | CLAIM: {claimed:>6} | ACTUAL: {actual:>6} | {status}")

print("=" * 80)
print("PAPER CLAIMS vs ACTUAL DATA")
print("=" * 80)

# 1. hasIngredient count (paper says 10,741 = number of dishes that have ingredients)
dishes_with_ingredients = sum(1 for d in dishes if d.get("ingredients"))
print("\n[1] hasIngredient (dish × ing) — paper: 10,741 dishes")
check("hasIngredient (dishes w/ ings)", 10741, dishes_with_ingredients)

# 2. mainIngredient count (paper says 10,741 = dishes with importance >= 3)
dishes_with_main = sum(1 for d in dishes if any(i.get("importance", 0) >= 3 for i in d.get("ingredients", [])))
print("\n[2] mainIngredient (importance >= 3) — paper: 10,741 dishes")
check("mainIngredient (dishes w/ imp≥3)", 10741, dishes_with_main)

# 3. substitutes pairs (paper says 5,407)
actual_subs = len(rel["substitutes"])
meta_subs = rel["metadata"]["counts"]["substitutes"]
print("\n[3] substitutes pairs — paper: 5,407")
check("substitutes (array length)", 5407, actual_subs)
check("substitutes (metadata count)", 5407, meta_subs)

# 4. flavorComplements pairs (paper says 15,119)
actual_comp = len(rel["flavorComplements"])
meta_comp = rel["metadata"]["counts"]["flavorComplements"]
print("\n[4] flavorComplements pairs — paper: 15,119")
check("flavorComplements (array len)", 15119, actual_comp)
check("flavorComplements (metadata)", 15119, meta_comp)

# 5. conflictsWith rules (paper says 139)
actual_conf = len(rel["conflictsWith"])
meta_conf = rel["metadata"]["counts"]["conflictsWith"]
print("\n[5] conflictsWith rules — paper: 139")
check("conflictsWith (array length)", 139, actual_conf)
check("conflictsWith (metadata count)", 139, meta_conf)

# 6. cookedBy count (paper says 10,741)
actual_cooked = len(rel["cookedBy"])
meta_cooked = rel["metadata"]["counts"]["cookedBy"]
print("\n[6] cookedBy (dish × method) — paper: 10,741")
check("cookedBy (array length)", 10741, actual_cooked)
check("cookedBy (metadata count)", 10741, meta_cooked)

# 7. NAMED RELATIONS: paper says 7
paper_relations = [
    "hasIngredient", "mainIngredient", "subClassOf",
    "substitutes", "flavorComplements", "conflictsWith", "cookedBy"
]
# Relations in relations.json (explicit keys minus metadata)
rel_keys = [k for k in rel.keys() if k != "metadata"]
# subClassOf lives in ingredient_hierarchy, hasIngredient/mainIngredient in dish KB
all_actual = set(rel_keys)
if "classes" in ing_hier:
    all_actual.add("subClassOf")
all_actual.add("hasIngredient")   # from dish KB ingredients list
all_actual.add("mainIngredient")  # from dish KB importance >= 3

print("\n[7] Named relation types — paper: 7")
check("Named relation count", 7, len(all_actual))
print(f"  Paper lists:  {paper_relations}")
print(f"  Actual found: {sorted(all_actual)}")
missing = set(paper_relations) - all_actual
extra = all_actual - set(paper_relations)
if missing: print(f"  ⚠️  Missing: {missing}")
if extra:   print(f"  ⚠️  Extra:   {extra}")

# 8. NPMI threshold 0.3 for complements
actual_threshold = rel["metadata"].get("npmi_threshold")
print("\n[8] NPMI threshold for flavorComplements — paper: 0.3")
check("NPMI threshold (metadata)", 0.3, actual_threshold)

# Also check subClassOf count = 49 classes
num_classes = len(ing_hier.get("classes", {}))
print("\n[BONUS] subClassOf class count — paper: 49")
check("subClassOf (num classes)", 49, num_classes)

# Source dishes and ingredients from metadata
print("\n[BONUS] Source counts from metadata")
check("source_dishes", 10741, rel["metadata"]["source_dishes"])
check("source_ingredients", 8112, rel["metadata"]["source_ingredients"])

print("\n" + "=" * 80)
print("VERIFICATION COMPLETE")
print("=" * 80)
