# Kế hoạch 1 tuần — 2 người (Ontology Methodology)

> **Mục tiêu:** Nâng cấp từ "KB + Statistics" thành Ontology thực sự (hierarchy + named relations + inference) và redesign 3 evaluation tasks để isolate ontology contribution.
>
> **Ngày tạo:** 2026-04-18
> **Thời lượng:** 7 ngày
> **Nhân sự:** 2 người (A + B), làm song song tối đa

---

## Nguyên tắc phân công

- **Người A** → Infrastructure, code, evaluation, metrics
- **Người B** → Ontology curation (cần domain knowledge), GT annotation, error analysis
- **Sync points:** cuối Day 2, Day 4, Day 5

---

## Day 1 — Foundation (parallel)

### Người A — Relations Derivation (automated)
**Output:** `app/data/ontology/relations.json`

- [ ] Derive `substitutes(A, B, context)` từ dish-name patterns
  - Script: tìm cặp dish chỉ khác 1 token ("Phở bò" vs "Phở gà") → `substitutes(bò, gà, "phở")`
- [ ] Derive `flavorComplements(A, B)` từ NPMI > 0.3 + same parent class
- [ ] Format `conflictsWith(A, B)` từ `app/data/conflict/` hiện có
- [ ] Build `cookedBy(dish, method)` từ dish category/name patterns

### Người B — Ingredient Hierarchy (manual curation)
**Output:** `app/data/ontology/ingredient_hierarchy.json`

- [ ] Design 4-level tree (Protein / Produce / Seasoning / Staple → subclasses → leaves)
- [ ] Map 20 flat categories → vị trí trong tree
- [ ] Manual review 100 ingredient phổ biến nhất để đảm bảo correct placement
- [ ] Spot-check 50 ingredient random → fix edge cases

**Deliverable Day 1:** `relations.json` + `ingredient_hierarchy.json` version 1

---

## Day 2 — Ontology Integration + Task Design

### Người A — Ontology API
**Output:** `retrieval/ontology.py` (class mới)

```python
class FoodOntology:
    def get_ancestors(ing_id) -> List[str]
    def get_descendants(class_id) -> List[str]
    def get_substitutes(ing_id, context=None) -> List[str]
    def get_complements(ing_id) -> List[str]
    def is_subclass_of(a, b) -> bool
    def expand_query(query) -> List[str]  # "món protein thực vật" → [đậu hũ, ...]
```

- [ ] Implement API trên
- [ ] Unit test mỗi method

### Người B — GT cho Task 1 + Dish Hierarchy

- [ ] Build dish hierarchy (25 dish categories → byType × byMethod matrix)
- [ ] Generate 200 class-level queries cho Task 1:
  - "Món protein thực vật" → GT: dishes có main_ingredient ∈ descendants(PlantProtein)
  - "Món rau thơm" → GT: dishes có ingredient ∈ Herb
  - "Món không hải sản" → GT: dishes không có ingredient ∈ Seafood
  - Mix: 50 multi-class, 50 negation, 50 cooking-method, 50 region-like
- [ ] Manual validate 20 queries ngẫu nhiên

**🔔 Sync end of Day 2:** Review ontology + task queries cùng nhau

---

## Day 3 — Task 1 + Task 3 Implementation (parallel)

### Người A — Task 1: Class-based Retrieval

- [ ] Implement query expansion: "món protein thực vật" → retrieve với expanded terms
- [ ] 3 systems: BM25 / RAG-only / RAG+Ontology (with expansion)
- [ ] Run on 200 queries → initial numbers
- [ ] Save `evaluation/outputs/ir_task1_ontology_results.json`

### Người B — Task 3: Hierarchy-aware Similarity

- [ ] Extend `get_related_dishes()`:
  ```
  Sim(A, B) = α·IDF-Jaccard + β·ClassOverlap + γ·CookingMethodMatch
  ```
- [ ] ClassOverlap: 2 ingredient cùng subclass tính 0.5; cùng leaf tính 1.0
- [ ] Tuning α, β, γ trên 50 cases
- [ ] Run on existing 200-dish LLM-judge subset

**Deliverable Day 3:** Task 1 + Task 3 có initial results

---

## Day 4 — Task 2 (Substitution)

### Người A — Substitution Logic

- [ ] Implement `get_substitutes(dish, ingredient, constraint)`:
  1. Lookup `substitutes` relation với context = dish category
  2. Filter theo constraint (vegetarian → PlantProtein only)
  3. Rank bằng flavor compatibility với các ingredient còn lại trong dish
- [ ] 3 baselines: Random-from-category / NPMI-only / Full-ontology

### Người B — GT cho Task 2 via LLM-Judge

- [ ] Select 100 substitution test cases:
  - 50 dishes × 2 ingredient replacement each
  - Mix constraints: vegetarian, no-seafood, low-sodium
- [ ] Run LLM-judge (reuse existing qwen / llama / gemma / mistral setup) với prompt:
  > "Is [X] an acceptable substitute for [Y] in [dish]? Score 0/1/2"
- [ ] Aggregate mean score as GT

**🔔 Sync end of Day 4:** Tất cả 3 tasks có initial results

---

## Day 5 — Evaluation + Ablation (parallel)

### Người A — Ablation Study

Cho mỗi task, run 5 variants:

| Variant | Components |
|---|---|
| V0 | RAG-only |
| V1 | + flat KB |
| V2 | + hierarchy |
| V3 | + relations (substitutes / complements) |
| V4 | + inference rules |

- [ ] Build ablation table
- [ ] Statistical test: paired Wilcoxon giữa V0 ↔ V4
- [ ] Bootstrap 95% CI cho mỗi metric

### Người B — Error Analysis

- [ ] Task 1: 20 queries fail → phân loại lỗi (hierarchy miss, expansion sai, ...)
- [ ] Task 2: 20 substitution bad → so NPMI-only vs Ontology, tìm lý do
- [ ] Task 3: 20 related dish sai → thiếu relation nào

**Deliverable Day 5:** Bảng kết quả cuối + error patterns

---

## Day 6 — Writeup (parallel)

### Người A

- [ ] **Section 3: Methodology**
  - 3.1 Ontology construction (từ dataset hiện có → hierarchy + relations)
  - 3.2 Formal definition (T-box, A-box, relations)
  - 3.3 Task-specific ontology usage (query expansion / substitution / similarity)
- [ ] **Section 5: Experimental Setup** — Dataset, splits, metrics, baselines
- [ ] **Tables** (results + ablation)

### Người B

- [ ] **Section 4: Tasks**
  - Task 1 / 2 / 3 định nghĩa + motivation
  - GT construction + validation
- [ ] **Section 6: Results & Discussion**
  - Per-task analysis
  - Ablation interpretation
  - Error analysis
- [ ] **Section 7: Limitations**

---

## Day 7 — Polish (together)

- [ ] **Figures:**
  - Fig 1: Ontology structure diagram (class hierarchy + relations)
  - Fig 2: Query expansion example (visualize cho Task 1)
  - Fig 3: Ablation bar chart
- [ ] Cross-read sections, fix inconsistencies
- [ ] Abstract + Intro + Conclusion
- [ ] Reference check
- [ ] Final submit prep

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

- [ ] `ingredient_hierarchy.json` (4-level, 8,112 ingredients)
- [ ] `relations.json` (substitutes, complements, conflicts, cookedBy)
- [ ] `task1_class_queries.jsonl` (200 queries)
- [ ] `task2_substitution_cases.jsonl` (100 cases + LLM-judge GT)
- [ ] `task3_hierarchy_sim.json` (200 dishes)
- [ ] `ablation_table.json` (3 tasks × 5 variants)
- [ ] Paper draft 6–8 trang

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
