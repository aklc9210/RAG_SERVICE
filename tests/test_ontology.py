"""Unit tests for retrieval.ontology.FoodOntology."""
import pytest
from retrieval.ontology import FoodOntology


@pytest.fixture(scope="module")
def ont():
    FoodOntology._instance = None
    return FoodOntology()


# ── Hierarchy ────────────────────────────────────────────────────

class TestGetClass:
    def test_known_ingredient(self, ont):
        assert ont.get_class("ingre01625") == "Seafood"  # cá thu

    def test_unknown_returns_none(self, ont):
        assert ont.get_class("ingre99999") is None


class TestGetAncestors:
    def test_seafood_chain(self, ont):
        anc = ont.get_ancestors("ingre01625")  # cá thu
        assert anc[0] == "Seafood"
        assert "Protein" in anc
        assert "Ingredient" not in anc

    def test_unknown_returns_empty(self, ont):
        assert ont.get_ancestors("ingre99999") == []


class TestGetDescendants:
    def test_seafood_nonempty(self, ont):
        descs = ont.get_descendants("Seafood")
        assert len(descs) > 100

    def test_protein_includes_seafood(self, ont):
        protein = set(ont.get_descendants("Protein"))
        seafood = set(ont.get_descendants("Seafood"))
        assert seafood.issubset(protein)

    def test_leaf_class_returns_members(self, ont):
        members = ont.get_descendants("Egg")
        assert len(members) > 0

    def test_nonexistent_class_empty(self, ont):
        assert ont.get_descendants("FakeClass") == []


class TestIsSubclassOf:
    def test_true(self, ont):
        assert ont.is_subclass_of("Seafood", "Protein") is True

    def test_reflexive(self, ont):
        assert ont.is_subclass_of("Meat", "Meat") is True

    def test_false(self, ont):
        assert ont.is_subclass_of("Seafood", "Produce") is False


class TestLowestCommonAncestor:
    def test_siblings(self, ont):
        assert ont.lowest_common_ancestor("Seafood", "Meat") == "AnimalProtein"

    def test_cross_branch(self, ont):
        assert ont.lowest_common_ancestor("Seafood", "Vegetable") == "Ingredient"

    def test_same_class(self, ont):
        assert ont.lowest_common_ancestor("Herb", "Herb") == "Herb"


class TestClassDepth:
    def test_root(self, ont):
        assert ont.class_depth("Ingredient") == 0

    def test_leaf(self, ont):
        assert ont.class_depth("Seafood") == 3

    def test_nonexistent(self, ont):
        assert ont.class_depth("FakeClass") == -1


# ── Relations ────────────────────────────────────────────────────

class TestGetSubstitutes:
    def test_returns_list(self, ont):
        subs = ont.get_substitutes("ingre01625")  # cá thu
        assert isinstance(subs, list)

    def test_has_id_and_context(self, ont):
        subs = ont.get_substitutes("ingre01625")
        if subs:
            assert "id" in subs[0]
            assert "context" in subs[0]

    def test_context_filter(self, ont):
        all_subs = ont.get_substitutes("ingre01625")
        kho_subs = ont.get_substitutes("ingre01625", context="kho")
        assert len(kho_subs) <= len(all_subs)
        for s in kho_subs:
            assert "kho" in s["context"].lower()

    def test_unknown_returns_empty(self, ont):
        assert ont.get_substitutes("ingre99999") == []


class TestGetComplements:
    def test_returns_sorted_by_npmi(self, ont):
        comps = ont.get_complements("ingre01625", top_k=5)
        if len(comps) >= 2:
            assert comps[0]["npmi"] >= comps[1]["npmi"]

    def test_top_k_limit(self, ont):
        assert len(ont.get_complements("ingre01625", top_k=3)) <= 3


class TestGetConflicts:
    def test_returns_list(self, ont):
        assert isinstance(ont.get_conflicts("ingre01625"), list)


class TestGetCookingMethod:
    def test_known_dish(self, ont):
        method = ont.get_cooking_method("dish0001")
        assert method is not None
        assert isinstance(method, str)

    def test_unknown_dish(self, ont):
        assert ont.get_cooking_method("dish99999") is None


# ── Task helpers ─────────────────────────────────────────────────

class TestExpandQuery:
    def test_hai_san(self, ont):
        names = ont.expand_query("món hải sản")
        assert len(names) > 100

    def test_protein_thuc_vat(self, ont):
        names = ont.expand_query("món protein thực vật")
        assert len(names) > 0

    def test_unknown_returns_empty(self, ont):
        assert ont.expand_query("món xyz không tồn tại") == []


class TestIngredientClassOverlap:
    def test_identical_lists(self, ont):
        a = ["ingre01625", "ingre01354"]
        assert ont.ingredient_class_overlap(a, a) == 1.0

    def test_empty_lists(self, ont):
        assert ont.ingredient_class_overlap([], ["ingre01625"]) == 0.0

    def test_range(self, ont):
        a = ["ingre01625", "ingre01354"]  # Seafood, Vegetable
        b = ["ingre01485", "ingre02768"]  # Seafood, Vegetable
        score = ont.ingredient_class_overlap(a, b)
        assert 0.0 <= score <= 1.0


class TestCookingMethodMatch:
    def test_same_method(self, ont):
        # dish0001 and dish0002 are both "mon canh" → Boil
        assert ont.cooking_method_match("dish0001", "dish0002") == 1.0

    def test_unknown_dish(self, ont):
        assert ont.cooking_method_match("dish0001", "dish99999") == 0.0
