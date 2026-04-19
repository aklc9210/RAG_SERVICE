# retrieval/ontology.py
"""
Day 2 — FoodOntology API.

Unified interface over ingredient_hierarchy.json + relations.json.
Used by Task 1 (query expansion), Task 2 (substitution), Task 3 (similarity).
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Set

ROOT = Path(__file__).resolve().parent.parent
HIERARCHY_PATH = ROOT / "app" / "data" / "ontology" / "ingredient_hierarchy.json"
RELATIONS_PATH = ROOT / "app" / "data" / "ontology" / "relations.json"
IKB_PATH = ROOT / "app" / "data" / "knowledge_base" / "ingredient_knowledge_base.json"


class FoodOntology:
    """Singleton ontology backed by Day-1 artifacts."""

    _instance = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def __init__(self):
        if self._loaded:
            return
        self._load()
        self._loaded = True

    # ── loading ──────────────────────────────────────────────────

    def _load(self):
        h = json.loads(HIERARCHY_PATH.read_text("utf-8"))
        self.classes: Dict[str, dict] = h["classes"]
        self.ing_to_class: Dict[str, str] = h["ingredient_to_class"]
        self.class_members: Dict[str, List[str]] = h["class_members"]

        r = json.loads(RELATIONS_PATH.read_text("utf-8"))
        self._build_substitutes_index(r.get("substitutes", []))
        self._build_complements_index(r.get("flavorComplements", []))
        self._build_conflicts_index(r.get("conflictsWith", []))
        self.cooked_by: Dict[str, str] = {
            e["dish_id"]: e["method"] for e in r.get("cookedBy", [])
        }

        ikb = json.loads(IKB_PATH.read_text("utf-8"))
        self.ing_meta: Dict[str, dict] = {e["id"]: e for e in ikb}
        # name_vi (lowered) → id for query expansion
        self._name_to_id: Dict[str, str] = {}
        for e in ikb:
            self._name_to_id[e.get("name_vi", "").lower().strip()] = e["id"]
            for syn in e.get("synonyms") or []:
                self._name_to_id[syn.lower().strip()] = e["id"]

    def _build_substitutes_index(self, subs: list):
        """ing_id → [(other_id, context)]"""
        self._subs: Dict[str, List[dict]] = {}
        for s in subs:
            for src, tgt in [(s["a"], s["b"]), (s["b"], s["a"])]:
                self._subs.setdefault(src, []).append({
                    "id": tgt, "context": s.get("context", ""),
                })

    def _build_complements_index(self, comps: list):
        """ing_id → [(other_id, npmi)]"""
        self._comps: Dict[str, List[dict]] = {}
        for c in comps:
            for src, tgt in [(c["a"], c["b"]), (c["b"], c["a"])]:
                self._comps.setdefault(src, []).append({
                    "id": tgt, "npmi": c["npmi"],
                })

    def _build_conflicts_index(self, confs: list):
        self._confs: Dict[str, List[dict]] = {}
        for c in confs:
            if not c.get("a") or not c.get("b"):
                continue
            for src, tgt in [(c["a"], c["b"]), (c["b"], c["a"])]:
                self._confs.setdefault(src, []).append({
                    "id": tgt,
                    "severity": c.get("severity"),
                    "reason": c.get("reason"),
                })

    # ── hierarchy queries ────────────────────────────────────────

    def get_class(self, ing_id: str) -> Optional[str]:
        """Leaf class of an ingredient."""
        return self.ing_to_class.get(ing_id)

    def get_ancestors(self, ing_id: str) -> List[str]:
        """All ancestor classes from leaf up to Ingredient (exclusive)."""
        cls = self.ing_to_class.get(ing_id)
        if not cls:
            return []
        path = []
        cur = cls
        while cur and cur != "Ingredient":
            path.append(cur)
            cur = self.classes.get(cur, {}).get("parent")
        return path

    def get_descendants(self, class_id: str) -> List[str]:
        """All ingredient IDs under a class (recursive)."""
        result = list(self.class_members.get(class_id, []))
        for child in self.classes.get(class_id, {}).get("children", []):
            result.extend(self.get_descendants(child))
        return result

    def is_subclass_of(self, a: str, b: str) -> bool:
        """True if class a is a descendant of class b."""
        cur = a
        while cur:
            if cur == b:
                return True
            cur = self.classes.get(cur, {}).get("parent")
        return False

    def class_depth(self, class_id: str) -> int:
        return self.classes.get(class_id, {}).get("level", -1)

    def lowest_common_ancestor(self, cls_a: str, cls_b: str) -> Optional[str]:
        """LCA of two classes."""
        ancestors_a = set()
        cur = cls_a
        while cur:
            ancestors_a.add(cur)
            cur = self.classes.get(cur, {}).get("parent")
        cur = cls_b
        while cur:
            if cur in ancestors_a:
                return cur
            cur = self.classes.get(cur, {}).get("parent")
        return None

    # ── relation queries ─────────────────────────────────────────

    def get_substitutes(self, ing_id: str,
                        context: Optional[str] = None) -> List[dict]:
        """Substitutes for an ingredient, optionally filtered by context."""
        entries = self._subs.get(ing_id, [])
        if context:
            ctx = context.lower()
            filtered = [e for e in entries if ctx in e["context"].lower()]
            if filtered:
                return filtered
        return entries

    def get_substitutes_for_dish(
        self, dish_id: str, ing_id: str,
        constraint: Optional[str] = None,
        strategy: str = "full_ontology",
        top_k: int = 5,
    ) -> List[dict]:
        """
        Task 2: Find substitutes for `ing_id` in the context of `dish_id`.

        Strategies:
          - random_class:   random ingredients from same leaf class
          - npmi_only:      rank by NPMI with dish's other ingredients
          - full_ontology:  ontology substitutes + constraint filter + NPMI rerank

        Constraints: "vegetarian", "no_seafood", "no_meat", "no_dairy", None

        Returns: [{"id", "name", "score", "reason"}, ...]
        """
        dish_meta = self._get_dish_ingredients(dish_id)
        other_ings = [i for i in dish_meta if i != ing_id]
        ing_class = self.ing_to_class.get(ing_id)

        if strategy == "random_class":
            return self._sub_random_class(ing_id, ing_class, constraint, top_k)
        elif strategy == "npmi_only":
            return self._sub_npmi_only(ing_id, other_ings, ing_class, constraint, top_k)
        else:
            return self._sub_full_ontology(ing_id, dish_id, other_ings, ing_class, constraint, top_k)

    def _get_dish_ingredients(self, dish_id: str) -> List[str]:
        """Get ingredient IDs for a dish from KB."""
        if not hasattr(self, "_dish_kb"):
            dkb_path = ROOT / "app" / "data" / "knowledge_base" / "dish_knowledge_base.json"
            dkb = json.loads(dkb_path.read_text("utf-8"))
            self._dish_kb = {d["id"]: d for d in dkb}
        dish = self._dish_kb.get(dish_id, {})
        return [i["ingredient_id"] for i in dish.get("ingredients", [])]

    def _passes_constraint(self, cand_id: str, constraint: Optional[str]) -> bool:
        if not constraint:
            return True
        cls = self.ing_to_class.get(cand_id, "Other")
        ancestors = set()
        cur = cls
        while cur:
            ancestors.add(cur)
            cur = self.classes.get(cur, {}).get("parent")
        if constraint == "vegetarian":
            return "AnimalProtein" not in ancestors
        elif constraint == "no_seafood":
            return "Seafood" not in ancestors
        elif constraint == "no_meat":
            return "Meat" not in ancestors and "Poultry" not in ancestors
        elif constraint == "no_dairy":
            return "Dairy" not in ancestors
        return True

    def _npmi_score_with_others(self, cand_id: str, other_ings: List[str]) -> float:
        comps = {e["id"]: e["npmi"] for e in self._comps.get(cand_id, [])}
        scores = [comps.get(o, 0.0) for o in other_ings if o in comps]
        return sum(scores) / len(scores) if scores else 0.0

    def _sub_random_class(self, ing_id, ing_class, constraint, top_k):
        import random
        members = list(self.class_members.get(ing_class, []))
        members = [m for m in members if m != ing_id and self._passes_constraint(m, constraint)]
        random.shuffle(members)
        results = []
        for m in members[:top_k]:
            meta = self.ing_meta.get(m, {})
            results.append({"id": m, "name": meta.get("name_vi", ""), "score": 0.0, "reason": "random_class"})
        return results

    def _sub_npmi_only(self, ing_id, other_ings, ing_class, constraint, top_k):
        members = list(self.class_members.get(ing_class, []))
        members = [m for m in members if m != ing_id and self._passes_constraint(m, constraint)]
        scored = []
        for m in members:
            s = self._npmi_score_with_others(m, other_ings)
            scored.append((m, s))
        scored.sort(key=lambda x: -x[1])
        results = []
        for m, s in scored[:top_k]:
            meta = self.ing_meta.get(m, {})
            results.append({"id": m, "name": meta.get("name_vi", ""), "score": round(s, 4), "reason": "npmi"})
        return results

    def _sub_full_ontology(self, ing_id, dish_id, other_ings, ing_class, constraint, top_k):
        # 1. Get ontology substitutes with context
        dish_meta = self._dish_kb.get(dish_id, {})
        dish_cat = dish_meta.get("category", "")
        ont_subs = self.get_substitutes(ing_id, context=dish_cat)

        # 2. Also include same-class members as fallback
        class_members = set(self.class_members.get(ing_class, []))
        # Include sibling classes too
        parent = self.classes.get(ing_class, {}).get("parent")
        if parent:
            for sib in self.classes.get(parent, {}).get("children", []):
                class_members |= set(self.class_members.get(sib, []))

        # If constraint filters out entire class, expand to alternative classes
        if constraint == "vegetarian":
            class_members |= set(self.get_descendants("PlantProtein"))
            class_members |= set(self.get_descendants("Mushroom"))
        elif constraint == "no_seafood" and ing_class and self.is_subclass_of(ing_class, "Seafood"):
            class_members |= set(self.get_descendants("Meat"))
            class_members |= set(self.get_descendants("Poultry"))
            class_members |= set(self.get_descendants("PlantProtein"))

        candidates = set()
        for s in ont_subs:
            candidates.add(s["id"])
        candidates |= class_members
        candidates.discard(ing_id)

        # 3. Filter constraint
        candidates = {c for c in candidates if self._passes_constraint(c, constraint)}

        # 4. Score: ontology bonus + NPMI with other ingredients
        scored = []
        ont_ids = {s["id"] for s in ont_subs}
        for c in candidates:
            npmi = self._npmi_score_with_others(c, other_ings)
            ont_bonus = 0.3 if c in ont_ids else 0.0
            same_leaf = 0.2 if self.ing_to_class.get(c) == ing_class else 0.0
            total = npmi + ont_bonus + same_leaf
            scored.append((c, total))
        scored.sort(key=lambda x: -x[1])

        results = []
        for c, s in scored[:top_k]:
            meta = self.ing_meta.get(c, {})
            reason = "ontology+npmi" if c in ont_ids else "class+npmi"
            results.append({"id": c, "name": meta.get("name_vi", ""), "score": round(s, 4), "reason": reason})
        return results

    def get_complements(self, ing_id: str, top_k: int = 20) -> List[dict]:
        """Top flavor complements by NPMI."""
        entries = self._comps.get(ing_id, [])
        return sorted(entries, key=lambda e: e["npmi"], reverse=True)[:top_k]

    def get_conflicts(self, ing_id: str) -> List[dict]:
        return self._confs.get(ing_id, [])

    def get_cooking_method(self, dish_id: str) -> Optional[str]:
        return self.cooked_by.get(dish_id)

    # ── query expansion (Task 1) ─────────────────────────────────

    def expand_query(self, query: str) -> List[str]:
        """
        Expand a class-level query into ingredient names.

        Examples:
            "món protein thực vật" → all PlantProtein ingredient names
            "món hải sản"         → all Seafood ingredient names
            "món không hải sản"   → (negation handled by caller)
        """
        q = query.lower().strip()
        # Map Vietnamese terms → ontology classes
        class_map = {
            "protein thực vật": "PlantProtein",
            "protein động vật": "AnimalProtein",
            "thịt": "Meat", "hải sản": "Seafood",
            "hải sản": "Seafood", "cá": "Seafood",
            "gia cầm": "Poultry", "trứng": "Egg",
            "nội tạng": "Offal", "thịt chế biến": "CuredMeat",
            "rau": "Vegetable", "rau thơm": "Herb",
            "rau củ": "RootVeg", "nấm": "Mushroom",
            "trái cây": "FreshFruit", "trái cây khô": "DriedFruit",
            "gia vị": "Seasoning", "gia vị mặn": "SaltyUmami",
            "gia vị cay": "Spicy", "gia vị chua": "SourSeasoning",
            "gia vị ngọt": "SweetSeasoning", "gia vị thơm": "Aromatic",
            "tinh bột": "Staple", "bún phở mì": "Noodle",
            "bột": "Flour", "gạo": "Grain",
            "sữa": "Dairy", "đồ uống": "Beverage",
        }
        matched_class = None
        for term, cls in sorted(class_map.items(), key=lambda x: -len(x[0])):
            if term in q:
                matched_class = cls
                break

        if not matched_class:
            return []

        ing_ids = self.get_descendants(matched_class)
        names = []
        for iid in ing_ids:
            meta = self.ing_meta.get(iid)
            if meta:
                names.append(meta.get("name_vi", ""))
        return names

    # ── similarity helpers (Task 3) ──────────────────────────────

    def ingredient_class_overlap(self, ings_a: List[str],
                                  ings_b: List[str]) -> float:
        """
        Class-based overlap score between two ingredient lists.
        Same leaf class → 1.0, same parent → 0.5, else 0.
        Normalized by max(len(a), len(b)).
        """
        if not ings_a or not ings_b:
            return 0.0
        score = 0.0
        used_b = set()
        for a in ings_a:
            cls_a = self.ing_to_class.get(a)
            if not cls_a:
                continue
            best = 0.0
            best_j = None
            for j, b in enumerate(ings_b):
                if j in used_b:
                    continue
                cls_b = self.ing_to_class.get(b)
                if not cls_b:
                    continue
                if cls_a == cls_b:
                    s = 1.0
                elif self.classes.get(cls_a, {}).get("parent") == \
                     self.classes.get(cls_b, {}).get("parent"):
                    s = 0.5
                else:
                    continue
                if s > best:
                    best = s
                    best_j = j
            if best_j is not None:
                used_b.add(best_j)
                score += best
        return score / max(len(ings_a), len(ings_b))

    def cooking_method_match(self, dish_a: str, dish_b: str) -> float:
        """1.0 if same cooking method, else 0.0."""
        ma = self.cooked_by.get(dish_a)
        mb = self.cooked_by.get(dish_b)
        if ma and mb and ma == mb:
            return 1.0
        return 0.0
