# FoodOntology API Reference

> `retrieval/ontology.py` — Unified interface over ingredient hierarchy + named relations.

## Quick Start

```python
from retrieval.ontology import FoodOntology

ont = FoodOntology()  # singleton, loads once
```

Data sources (auto-loaded):
- `app/data/ontology/ingredient_hierarchy.json` — 8,112 ingredients → 49 classes
- `app/data/ontology/relations.json` — substitutes, complements, conflicts, cookedBy
- `app/data/knowledge_base/ingredient_knowledge_base.json` — ingredient metadata

---

## Hierarchy Queries

### `get_class(ing_id) → str | None`

Leaf class of an ingredient.

```python
ont.get_class("ingre01625")  # "Seafood"
ont.get_class("ingre07583")  # "SweetSeasoning"
```

### `get_ancestors(ing_id) → List[str]`

Class chain from leaf → root (exclusive of "Ingredient").

```python
ont.get_ancestors("ingre01625")
# ["Seafood", "AnimalProtein", "Protein"]
```

### `get_descendants(class_id) → List[str]`

All ingredient IDs under a class (recursive).

```python
ids = ont.get_descendants("Seafood")     # 519 ingredient IDs
ids = ont.get_descendants("Protein")     # all Protein descendants (Meat + Seafood + Egg + ...)
ids = ont.get_descendants("PlantProtein") # 69 IDs
```

### `is_subclass_of(a, b) → bool`

Check if class `a` is a descendant of class `b`.

```python
ont.is_subclass_of("Seafood", "Protein")   # True
ont.is_subclass_of("Seafood", "Produce")   # False
ont.is_subclass_of("Meat", "Meat")         # True (reflexive)
```

### `lowest_common_ancestor(cls_a, cls_b) → str | None`

```python
ont.lowest_common_ancestor("Seafood", "Meat")       # "AnimalProtein"
ont.lowest_common_ancestor("Seafood", "Vegetable")   # "Ingredient"
ont.lowest_common_ancestor("Herb", "Vegetable")      # "Produce"
```

### `class_depth(class_id) → int`

```python
ont.class_depth("Ingredient")    # 0
ont.class_depth("Protein")       # 1
ont.class_depth("AnimalProtein") # 2
ont.class_depth("Seafood")       # 3
```

---

## Relation Queries

### `get_substitutes(ing_id, context=None) → List[dict]`

Ingredients that can replace `ing_id`. Optional `context` filters by dish template.

```python
# All substitutes for cá thu
ont.get_substitutes("ingre01625")
# [{"id": "ingre01485", "context": "canh … nấu ngót"}, ...]

# Only substitutes in "kho" dishes
ont.get_substitutes("ingre01625", context="kho")
# [{"id": "ingre01469", "context": "… kho tiêu"}, ...]
```

### `get_complements(ing_id, top_k=20) → List[dict]`

Top flavor-complementing ingredients by NPMI score.

```python
ont.get_complements("ingre01625", top_k=3)
# [
#   {"id": "ingre06349", "npmi": 0.5392},  # thịt tôm
#   {"id": "ingre06349", "npmi": 0.3524},  # thịt cua
#   ...
# ]
```

### `get_conflicts(ing_id) → List[dict]`

Nutritional/medical conflicts.

```python
ont.get_conflicts("ingre02124")
# [{"id": "ingre...", "severity": "medium", "reason": "..."}, ...]
```

### `get_cooking_method(dish_id) → str | None`

```python
ont.get_cooking_method("dish0001")  # "Boil"
ont.get_cooking_method("dish3188")  # "NoodleSoup"
```

---

## Task-specific Methods

### Task 1: Query Expansion

#### `expand_query(query) → List[str]`

Expands a Vietnamese class-level query into ingredient names.

```python
ont.expand_query("món hải sản")
# ["ba ba", "ba khía", "cá basa", ...] — 519 names

ont.expand_query("món protein thực vật")
# ["đậu hũ", "đậu phộng", ...] — 69 names

ont.expand_query("món rau thơm")
# ["basil", "bạc hà", "húng quế", ...] — 402 names
```

Supported terms: `hải sản`, `thịt`, `gia cầm`, `trứng`, `nội tạng`, `protein thực vật`, `protein động vật`, `rau`, `rau thơm`, `rau củ`, `nấm`, `trái cây`, `trái cây khô`, `gia vị`, `gia vị mặn`, `gia vị cay`, `gia vị chua`, `gia vị ngọt`, `gia vị thơm`, `tinh bột`, `bún phở mì`, `bột`, `gạo`, `sữa`, `đồ uống`.

Negation (e.g. "món không hải sản") is handled by the caller — expand the positive class, then exclude.

### Task 3: Similarity Helpers

#### `ingredient_class_overlap(ings_a, ings_b) → float`

Class-based overlap between two ingredient lists. Greedy matching:
- Same leaf class → 1.0
- Same parent class → 0.5
- Else → 0

Normalized by `max(len(a), len(b))`.

```python
a = ["ingre01625", "ingre01354", "ingre02673"]  # cá thu, cà chua, hành lá
b = ["ingre01485", "ingre01354", "ingre02768"]  # cá chim, cà chua, hành tím
ont.ingredient_class_overlap(a, b)  # 1.0 (all same leaf class)
```

#### `cooking_method_match(dish_a, dish_b) → float`

```python
ont.cooking_method_match("dish0001", "dish0002")  # 1.0 (both Boil)
ont.cooking_method_match("dish0001", "dish3188")  # 0.0 (Boil vs NoodleSoup)
```

---

## Class Hierarchy Overview

```
Ingredient (8,112)
├── Protein (1,273)
│   ├── AnimalProtein
│   │   ├── Seafood (519)    ├── Meat (333)
│   │   ├── CuredMeat (165)  ├── Poultry (85)
│   │   ├── Offal (72)       └── Egg (46)
│   └── PlantProtein (69)
├── Produce (1,834)
│   ├── Vegetable (591)  ├── FreshFruit (441)  ├── Herb (402)
│   ├── DriedFruit (175) ├── RootVeg (139)     └── Mushroom (87)
├── Seasoning (2,508)
│   ├── OtherSeasoning (942) ├── SaltyUmami (546) ├── Aromatic (335)
│   ├── Spicy (291)          ├── SourSeasoning (234) └── SweetSeasoning (160)
├── Staple (571)
│   ├── Flour (269) ├── Noodle (144) ├── Grain (137) └── Bread (21)
├── Processed (585)  ├── Dairy (186)  ├── Sweet (464)
├── Beverage (264)   └── Other (427)
```

---

## Maintenance

Fix misclassifications:

```bash
# Add to MANUAL dict in scripts/fix_hierarchy.py, then:
python scripts/fix_hierarchy.py          # dry-run
python scripts/fix_hierarchy.py --apply  # write
```

Rebuild relations after hierarchy changes:

```bash
python scripts/build_ontology_relations.py
```
