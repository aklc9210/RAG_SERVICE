# Kế hoạch 1 tuần — 2 người (Ontology Methodology)

> **Mục tiêu:** Nâng cấp từ "KB + Statistics" thành Ontology thực sự (hierarchy + named relations + inference) và redesign 3 evaluation tasks để isolate ontology contribution.
>
> **Ngày tạo:** 2026-04-18
> **Cập nhật lần cuối:** 2026-04-21
> **Thời lượng:** 7 ngày
> **Nhân sự:** 2 người (A + B), làm song song tối đa
>
> **TIẾN ĐỘ TỔNG QUAN:** Day 1–5 ✅ DONE | Day 6 🔄 IN PROGRESS | Day 7 ⏳ TODO

---

## Tiến độ cập nhật (2026-04-21)

### ✅ Implementation DONE (Day 1–5)
- `ingredient_hierarchy.json`: 8,112 ingredients → 49 classes, 4 levels, 38 leaves
- `relations.json`: substitutes, flavorComplements, conflictsWith, cookedBy
- `retrieval/ontology.py`: FoodOntology API (expand_query, get_substitutes_for_dish, ingredient_class_overlap, cooking_method_match)
- Task 1: 200 queries, 4 systems evaluated (BM25, BM25+Exp, RAG-only, RAG+Ontology)
- Task 2: 100 cases, 3 strategies (random_class, npmi_only, full_ontology)
- Task 3: 21,480 pairs, 4-component similarity (Jaccard + ClassOverlap + CookingMethod + Semantic)
- Phase 2 semantic enhancement: MAE -44.7% (Task 3)

### ✅ IAA Analysis DONE
- Loại Qwen2.5:7b (scoring bias: score 2 chỉ 0.8%, agreement 39–62%)
- Giữ 3 judges: Llama3.1, Gemma2, Mistral → Fleiss' κ = 0.184, pairwise 72–88%
- Task 3 GT re-aggregated với 3 judges, re-evaluated
- Backup: `task3_related_gt.4judges.bak.jsonl`

### 🔄 Paper Writing IN PROGRESS (Day 6)
| Section | File | Status |
|---|---|---|
| I. Introduction (~0.5 trang) | `paper/introduction.tex` | ✅ Done |
| II. Related Work (~0.4 trang) | `paper/related_work.tex` | ✅ Done |
| III. Methodology (~1.0 trang) | `paper/methodology.tex` | ✅ Done |
| IV. Task Definitions | `paper/experiments.tex` | ✅ Done |
| V. Experiments & Results | `paper/experiments.tex` | ✅ Done (cần update Task 3 numbers với 3-judge GT) |
| VI. Conclusion & Limitations | — | ⏳ TODO |
| Figures (Mermaid) | `paper/figures.md` | ✅ Done (Fig 1: T-box/A-box, Fig 2: Pipeline) |
| References | `paper/references.bib` | ✅ Done (25 refs) |
| IAA notes | `paper/iaa_notes.md` | ✅ Done |

### ⏳ TODO (Day 7)
- [ ] Viết Section Conclusion & Limitations
- [ ] Update Task 3 numbers trong experiments.tex (MAE 0.0809, Spearman ρ 0.70)
- [ ] Ablation table V0–V4 (chưa có đủ — chỉ có Task 1 ablation 530 queries)
- [ ] Statistical significance tests (Wilcoxon, bootstrap CI)
- [ ] Vẽ figures chính thức từ Mermaid drafts
- [ ] Cross-read, fix inconsistencies
- [ ] Final formatting cho IEEE template

---

## Nguyên tắc phân công

- **Người A** → Infrastructure, code, evaluation, metrics
- **Người B** → Ontology curation (cần domain knowledge), GT annotation, error analysis
- **Sync points:** cuối Day 2, Day 4, Day 5

---

## Day 1 — Foundation (parallel) ✅ DONE

### Người A — Relations Derivation (automated)
**Output:** `app/data/ontology/relations.json`

- [x] Derive `substitutes(A, B, context)` từ dish-name patterns
  - Script: tìm cặp dish chỉ khác 1 token ("Phở bò" vs "Phở gà") → `substitutes(bò, gà, "phở")`
- [x] Derive `flavorComplements(A, B)` từ NPMI > 0.3 + same parent class
- [x] Format `conflictsWith(A, B)` từ `app/data/conflict/` hiện có
- [x] Build `cookedBy(dish, method)` từ dish category/name patterns

### Người B — Ingredient Hierarchy (manual curation)
**Output:** `app/data/ontology/ingredient_hierarchy.json`

- [x] Design 4-level tree (Protein / Produce / Seasoning / Staple → subclasses → leaves)
- [x] Map 20 flat categories → vị trí trong tree
- [x] Manual review 100 ingredient phổ biến nhất để đảm bảo correct placement
- [x] Spot-check 50 ingredient random → fix edge cases

**Deliverable Day 1:** ✅ `relations.json` + `ingredient_hierarchy.json` version 1

---

## Day 2 — Ontology Integration + Task Design ✅ DONE

### Người A — Ontology API
**Output:** `retrieval/ontology.py` ✅

```python
class FoodOntology:
    def get_ancestors(ing_id) -> List[str]
    def get_descendants(class_id) -> List[str]
    def get_substitutes(ing_id, context=None) -> List[str]
    def get_complements(ing_id) -> List[str]
    def is_subclass_of(a, b) -> bool
    def expand_query(query) -> List[str]  # "món protein thực vật" → [đậu hũ, ...]
```

- [x] Implement API trên
- [x] Unit test mỗi method

### Người B — GT cho Task 1 + Dish Hierarchy

- [x] Build dish hierarchy (25 dish categories → byType × byMethod matrix)
- [x] Generate 200 class-level queries cho Task 1:
  - "Món protein thực vật" → GT: dishes có main_ingredient ∈ descendants(PlantProtein)
  - "Món rau thơm" → GT: dishes có ingredient ∈ Herb
  - "Món không hải sản" → GT: dishes không có ingredient ∈ Seafood
  - Mix: 50 multi-class, 50 negation, 50 cooking-method, 50 region-like
- [x] Manual validate 20 queries ngẫu nhiên

**🔔 Sync end of Day 2:** ✅ Review ontology + task queries cùng nhau

---

## Day 3 — Task 1 + Task 3 Implementation (parallel) ✅ DONE

### Người A — Task 1: Class-based Retrieval

- [x] Implement query expansion: "món protein thực vật" → retrieve với expanded terms
- [x] 3 systems: BM25 / RAG-only / RAG+Ontology (with expansion)
- [x] Run on 200 queries → initial numbers
- [x] Save `evaluation/outputs/ir_task1_ontology_results.json`

### Người B — Task 3: Hierarchy-aware Similarity

- [x] Extend `get_related_dishes()`:
  ```
  Sim(A, B) = α·IDF-Jaccard + β·ClassOverlap + γ·CookingMethodMatch
  ```
- [x] ClassOverlap: 2 ingredient cùng subclass tính 0.5; cùng leaf tính 1.0
- [x] Tuning α, β, γ trên 50 cases
- [x] Run on existing 200-dish LLM-judge subset

**Deliverable Day 3:** ✅ Task 1 + Task 3 có initial results

---

## Day 4 — Task 2 (Substitution) ✅ DONE

### Người A — Substitution Logic

- [x] Implement `get_substitutes(dish, ingredient, constraint)`:
  1. Lookup `substitutes` relation với context = dish category
  2. Filter theo constraint (vegetarian → PlantProtein only)
  3. Rank bằng flavor compatibility với các ingredient còn lại trong dish
- [x] 3 baselines: Random-from-category / NPMI-only / Full-ontology

### Người B — GT cho Task 2 via LLM-Judge

- [x] Select 100 substitution test cases:
  - 50 dishes × 2 ingredient replacement each
  - Mix constraints: vegetarian, no-seafood, low-sodium
- [x] Run LLM-judge (reuse existing qwen / llama / gemma / mistral setup) với prompt:
  > "Is [X] an acceptable substitute for [Y] in [dish]? Score 0/1/2"
- [x] Aggregate mean score as GT

**🔔 Sync end of Day 4:** ✅ Tất cả 3 tasks có initial results

---

## Day 5 — Evaluation + Ablation (parallel) ✅ DONE

### Người A — Ablation Study

Cho mỗi task, run 5 variants:

| Variant | Components |
|---|---|
| V0 | RAG-only |
| V1 | + flat KB |
| V2 | + hierarchy |
| V3 | + relations (substitutes / complements) |
| V4 | + inference rules |

- [x] Build ablation table (partial — Task 1 only, 530 queries)
- [ ] Statistical test: paired Wilcoxon giữa V0 ↔ V4 ⚠️ TODO
- [ ] Bootstrap 95% CI cho mỗi metric ⚠️ TODO

### Người B — Error Analysis

- [x] Task 1: 20 queries fail → phân loại lỗi (hierarchy miss, expansion sai, ...)
- [x] Task 2: 20 substitution bad → so NPMI-only vs Ontology, tìm lý do
- [x] Task 3: 20 related dish sai → thiếu relation nào

**Deliverable Day 5:** ✅ Bảng kết quả cuối + error patterns (ablation chưa đầy đủ)

---

## Day 6 — Writeup (parallel) 🔄 IN PROGRESS

### Người A

- [x] **Section 3: Methodology** → `paper/methodology.tex`
  - 3.1 Formal definition (T-box, A-box, 7 relations)
  - 3.2 Ingredient hierarchy (4-level, 49 classes) + Dish taxonomy
  - 3.3 Relation derivation (substitutes, NPMI, conflicts, cookedBy)
  - 3.4 Ontology integration (3 injection points)
- [x] **Section 5: Experimental Setup + Results** → `paper/experiments.tex`
- [x] **Tables** (Task 1/2/3 results)
- [x] **IAA analysis** → `paper/iaa_notes.md` (loại Qwen, κ=0.184)
- [x] **Re-evaluate Task 3** với 3-judge GT (MAE=0.0809, Spearman ρ=0.70)

### Người B

- [x] **Section 1: Introduction** → `paper/introduction.tex` (~0.5 trang)
- [x] **Section 2: Related Work** → `paper/related_work.tex` (~0.4 trang)
- [x] **Section 4: Task Definitions** → `paper/experiments.tex`
- [x] **Figures (Mermaid drafts)** → `paper/figures.md` (T-box/A-box + Pipeline)
- [x] **References** → `paper/references.bib` (25 refs)
- [ ] **Section 6: Conclusion & Limitations** ⏳ TODO

---

## Day 7 — Polish (together) ⏳ TODO

- [ ] Viết Section Conclusion & Limitations
- [ ] Update Task 3 numbers trong experiments.tex (MAE 0.0809, Spearman ρ 0.70)
- [ ] Ablation table V0–V4 đầy đủ 3 tasks (hiện chỉ có Task 1)
- [ ] Statistical significance tests (Wilcoxon, bootstrap CI)
- [ ] Vẽ figures chính thức từ Mermaid drafts (Fig 1: T-box/A-box, Fig 2: Pipeline)
- [ ] Cross-read sections, fix inconsistencies
- [ ] Abstract + final Intro polish
- [ ] Reference check
- [ ] Final IEEE template formatting

---

## Risk & Mitigation

| Risk | Mitigation |
|---|---|
| Hierarchy curation chậm hơn dự kiến | Day 1 chỉ làm 4-level cho **top 500 ingredient phổ biến**, others = `Other_<category>` |
| LLM-judge bị rate limit | Dùng 200 cases thay vì 100 × 2 (giảm còn 1 replacement/dish) |
| Task 2 substitution logic phức tạp | Fallback: chỉ dùng `substitutes` relation thuần, bỏ constraint filter |
| Numbers không impressive | Paper vẫn có ablation + error analysis → defensible về methodology |

---

## Checklist tổng — cuối Day 7

- [x] `ingredient_hierarchy.json` (4-level, 8,112 ingredients)
- [x] `relations.json` (substitutes, complements, conflicts, cookedBy)
- [x] `task1_class_queries.jsonl` (200 queries)
- [x] `task2_substitution_cases.jsonl` (100 cases + LLM-judge GT)
- [x] `task3_hierarchy_sim.json` (200 dishes, re-evaluated with 3 judges)
- [ ] `ablation_table.json` (3 tasks × 5 variants) ⚠️ Partial
- [ ] Paper draft 6–8 trang ⚠️ 5/6 sections done, missing Conclusion

---

## Pre-start checklist

1. [ ] Confirm phân công Người A / Người B có phù hợp không?
2. [ ] Scope từng task đã đồng ý?
3. [ ] Generate script skeleton cho Day 1 (relations derivation + hierarchy template)?
4. [ ] Venue submit — cần điều chỉnh formal level không?

---

## Appendix: Cấu trúc Ontology đề xuất

### Ingredient taxonomy (4 levels)

```
Ingredient
├── Protein
│   ├── AnimalProtein
│   │   ├── Meat      → thịt heo, thịt bò, thịt gà...
│   │   ├── Seafood   → nghêu, tôm, cá...
│   │   └── Egg       → trứng gà, trứng vịt...
│   └── PlantProtein  → đậu hũ, đậu phộng...
├── Produce
│   ├── Herb          → thì là, húng quế, ngò
│   ├── Vegetable     → cải, bí, mướp
│   ├── RootVeg       → khoai tây, cà rốt, củ cải
│   └── Fruit         → chanh, khế, cà chua
├── Seasoning
│   ├── SaltyUmami    → muối, nước mắm, tương
│   ├── Sweet         → đường, mật ong
│   ├── Sour          → giấm, chanh
│   └── Spicy         → ớt, tiêu
└── Staple            → gạo, bún, phở, mì
```

### Dish taxonomy (2 axes)

```
Dish
├── byType:   MonNuoc, MonKho, MonXao, MonCanh, MonLau, ...
└── byMethod: Boil, Fry, Grill, Steam, Stew
```

### Named relations

| Relation | Derivation | Source |
|---|---|---|
| `hasIngredient(dish, ing)` | Direct | `dish_kb` |
| `mainIngredient(dish, ing)` | importance ≥ 3 | `dish_kb` |
| `subClassOf(A, B)` | Manual hierarchy | new |
| `flavorComplements(A, B)` | NPMI > 0.3 + category filter | `npmi` + `KB` |
| `substitutes(A, B, context)` | Same subclass + dish-pattern match | derived |
| `conflictsWith(A, B)` | Existing rules | `conflict_rules` |
| `cookedBy(dish, method)` | From dish name/category | pattern match |
