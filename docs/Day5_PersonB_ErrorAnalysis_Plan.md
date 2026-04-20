# Day 5 — Người B: Error Analysis 
## Chi Tiết Công Việc, Input, Output & Điều Kiện Tiên Quyết

---

## 📋 Tổng Quan Task

**Mục tiêu:** Phân tích 60 queries/substitutions/dishes bị fail từ 3 tasks để:
- Identify error patterns
- Root cause analysis
- Quantify ontology contribution

---

## 🎯 Chi Tiết Từng Task

### **Task 1: Class-based Query Retrieval Error Analysis**

#### Input (Phụ thuộc vào Người A Day 3)
```
evaluation/outputs/ir_task1_ontology_results.json
├─ 3 systems (BM25, RAG-only, RAG+Ontology)
├─ 200 queries
└─ Metrics: nDCG@10, MRR@10, Recall@10

evaluation/data/task1_class_queries.jsonl
├─ Query: "tổng hợp món me"
├─ Type: "single_class"
├─ classes_positive: ["SourSeasoning"]
├─ gt_dish_ids: [list of true dishes]
└─ retrieved_dish_ids: [what system returned]
```

#### Công Việc
**Step 1: Identify 20 failing queries**
```
Criteria: 
  - Rank queries by (RAG+Ontology nDCG) ascending
  - Pick bottom 20 (worst performance)
  - Focus on queries where RAG+Ontology < BM25 (regression)
```

**Step 2: Phân loại lỗi (classify into categories)**
```
Error Types:
  A. Hierarchy Miss (ontology tree incomplete)
     Example: Query asks for "vegetable" → missing class mapping
     
  B. Expansion Sai (wrong query expansion)
     Example: "protein thực vật" → expanded to wrong classes
     
  C. Relation Missing (lacking ingredient relations)
     Example: Query needs "substitute A with B" but no relation
     
  D. Precision Loss (ontology too strict)
     Example: Filter eliminates correct dishes
     
  E. Semantic Gap (LLM can't parse query intent)
     Example: "không hải sản" (no seafood) → unclear negation
```

#### Output
```json
{
  "task1_error_analysis": {
    "total_failing_queries": 20,
    "error_distribution": {
      "hierarchy_miss": 5,
      "expansion_sai": 4,
      "relation_missing": 3,
      "precision_loss": 5,
      "semantic_gap": 3
    },
    "error_details": [
      {
        "query_id": 42,
        "query_text": "tổng hợp món me",
        "error_type": "hierarchy_miss",
        "gt_dishes": 85,
        "retrieved_bm25": 12,
        "retrieved_rag_only": 8,
        "retrieved_rag_ontology": 5,
        "reason": "SourSeasoning class không fully mapped trong hierarchy"
      },
      ...
    ],
    "insights": [
      "Hierarchy chỉ cover 60% use cases, 40% cần enrichment",
      "Query expansion logic tốt nhưng semantic negation yếu"
    ]
  }
}
```

---

### **Task 2: Substitution Error Analysis**

#### Input (Phụ thuộc vào Người A Day 4)
```
evaluation/data/datasets/task2_substitution_gt.jsonl
├─ 100 test cases với:
│  ├─ dish_id, main_ingredient, substitute
│  ├─ constraint (vegetarian, no_seafood, low_sodium)
│  ├─ llm_score (0/1/2 từ GT)
│  └─ predicted_score (từ 3 baselines)
│
evaluation/outputs/task2_substitution_results.json
├─ 3 baselines:
│  ├─ V1: Random-from-category
│  ├─ V2: NPMI-only (flavor complements)
│  └─ V3: Full-ontology (relations + complements + constraints)
└─ Per-case scores
```

#### Công Việc
**Step 1: Identify 20 bad substitutions**
```
Criteria:
  - Pick cases where V3 (ontology) predicts score 2
    but GT is score 0 or 1 (false positives)
  - Pick cases where V3 predicts 0 but GT is 1 or 2 (false negatives)
  - Focus on high-confidence mistakes
```

**Step 2: Compare NPMI-only vs Ontology**
```
For each bad case, analyze:

Case 1: Thay tôm bằng cua (trong "canh tôm")
  ├─ NPMI(tôm, cua) = 0.65 → suggest NPMI-based would rank high
  ├─ Ontology: both Seafood class → rank high
  ├─ GT: score 1 (acceptable but changes flavor significantly)
  ├─ Lesson: NPMI + class match không đủ → need flavor profiling
  
Case 2: Thay nước mắm bằng tương (constraint: low-sodium)
  ├─ NPMI(nước mắm, tương) = 0.8 → high complement
  ├─ Ontology: constraint filter blocks tương (high salt)
  ├─ GT: score 0 (violates low-sodium)
  ├─ Lesson: Ontology constraint filtering worked! ✓
```

**Step 3: Root cause classification**
```
Error Types:
  A. Constraint Violation
     - Ontology blocked → but LLM still scored high (error in LLM judge)
     - Ontology passed → but violates constraint (filter too loose)
     
  B. Missing Flavor Profile
     - NPMI high but flavor incompatible (NPMI ≠ substituability)
     - Need semantic taste dimension
     
  C. Context Dependency
     - Works in some dishes, fails in others
     - Substitute relationship depends on dish type
     
  D. Semantic Mismatch
     - Ontology classes don't capture nuance
     - E.g., "thịt heo" vs "thịt bò" same class but very different in bánh mì
```

#### Output
```json
{
  "task2_error_analysis": {
    "total_bad_substitutions": 20,
    "error_distribution": {
      "constraint_violation": 6,
      "missing_flavor_profile": 5,
      "context_dependency": 5,
      "semantic_mismatch": 4
    },
    "comparison_npmi_vs_ontology": {
      "cases_where_npmi_better": 3,
      "cases_where_ontology_better": 8,
      "cases_equivalent": 9,
      "npmi_avg_score": 0.25,
      "ontology_avg_score": 0.32
    },
    "error_details": [
      {
        "case_id": 15,
        "dish": "Canh tôm",
        "main_ing": "tôm",
        "substitute": "cua",
        "error_type": "missing_flavor_profile",
        "npmi_score": 0.65,
        "ontology_score": 2,
        "gt_score": 1,
        "reason": "NPMI high + same class → predicted 2, but flavor different"
      },
      ...
    ],
    "insights": [
      "Ontology outperforms NPMI in 8/20 (40%), especially with constraints",
      "Flavor profiling missing → next iteration should add taste dimensions",
      "Constraint enforcement works well (6 violations prevented)"
    ]
  }
}
```

---

### **Task 3: Related Dish Similarity Error Analysis**

#### Input (Phụ thuộc vào Người B Day 3 output)
```
evaluation/outputs/task3_hierarchy_similarity_results.json
├─ 21,480 dish pairs
├─ Predicted similarity: α*IDF-Jaccard + β*ClassOverlap + γ*CookingMatch
├─ GT similarity: LLM-judged relatedness scores
└─ Metrics: Pearson r=0.7577, MAE=0.0945

evaluation/data/datasets/task3_related_gt.jsonl
├─ Ground truth related dishes
└─ Per-pair components
```

#### Công Việc
**Step 1: Identify 20 worst predictions**
```
Criteria:
  - Calculate |predicted - gt| for all pairs
  - Pick top 20 by error magnitude (prediction very wrong)
  - Should include both over-predictions and under-predictions
```

**Step 2: Analyze missing relations**
```
For each bad pair, check:

Pair 1: "Phở bò" vs "Phở gà"
  ├─ Predicted: 0.82 (high similarity)
  ├─ GT: 0.45 (moderate - they're different dishes)
  ├─ IDF-Jaccard: 0.33 (few shared ingredients)
  ├─ ClassOverlap: 0.95 (same protein class)
  ├─ CookingMatch: 1.0 (both "nước")
  ├─ Problem: ClassOverlap too strong (thịt bò ≠ thịt gà in flavor)
  ├─ Missing: Ingredient-specific relations (beef.flavor ≠ chicken.flavor)
  
Pair 2: "Canh chua cá" vs "Canh chua cà chua"
  ├─ Predicted: 0.35 (low similarity)
  ├─ GT: 0.68 (high - both "canh chua")
  ├─ IDF-Jaccard: 0.12 (few shared ingredients)
  ├─ ClassOverlap: 0.5 (cá vs cà chua different classes)
  ├─ Problem: Missing "canh chua" dish type relation
  ├─ Lesson: Need dish-level relations, not just ingredient-level
```

**Step 3: Identify missing relation types**
```
Missing Relation Analysis:
  A. Ingredient-specific relations
     - Different beef cuts should have high substitutability
     - ClassOverlap treats all "Meat" same
     
  B. Dish-type relations
     - All "Phở" should cluster together
     - Hierarchy doesn't capture dish type similarity
     
  C. Regional/cultural relations
     - Northern vs Southern variants
     - Ontology lacks regional dimension
     
  D. Flavor/texture dimensions
     - "Phở bò nóng" vs "Bánh mì thịt bò" share beef
     - But very different dishes (not just ingredient overlap)
```

#### Output
```json
{
  "task3_error_analysis": {
    "total_worst_predictions": 20,
    "error_distribution": {
      "overpredicted_similarity": 11,
      "underpredicted_similarity": 9
    },
    "missing_relations": {
      "ingredient_specific": 7,
      "dish_type": 6,
      "regional": 4,
      "flavor_texture": 3
    },
    "error_details": [
      {
        "pair_id": 123,
        "dish_a": "Pho Bo",
        "dish_b": "Pho Ga",
        "predicted": 0.82,
        "gt": 0.45,
        "error": 0.37,
        "error_type": "overpredicted",
        "missing_relation": "ingredient_specific",
        "reason": "ClassOverlap treats beef=chicken, but flavor significantly different"
      },
      ...
    ],
    "insights": [
      "55% errors due to ingredient-specific variations not captured",
      "30% errors due to missing dish-type clustering",
      "Adding regional dimension could improve ~10%"
    ]
  }
}
```

---

## 🔗 Phụ Thuộc & Điều Kiện Tiên Quyết

### **Input Dependencies (Người B cần có)**

| Input | Source | Status | Tiên Quyết |
|-------|--------|--------|-----------|
| Task 1 results | Người A Day 3 | ✓ Ready | `ir_task1_ontology_results.json` |
| Task 1 queries | Người B Day 2 | ✓ Ready | `task1_class_queries.jsonl` |
| Task 2 GT | Người B Day 4 | ✓ Ready | `task2_substitution_gt.jsonl` |
| Task 2 predictions | Người A Day 4 | ⏳ Need | `task2_substitution_results.json` |
| Task 3 results | Người B Day 3 | ✓ Ready | `task3_hierarchy_similarity_results.json` |
| Task 3 GT | Existed | ✓ Ready | `task3_related_gt.jsonl` |

---

## 📊 Công Việc Parallel (Day 5 Người A vs B)

```
Day 5 Timeline:
  
  Người A (Ablation):
    ├─ V0: RAG-only       (baseline)
    ├─ V1: + flat KB      (1-2 hours)
    ├─ V2: + hierarchy    (1-2 hours)
    ├─ V3: + relations    (1-2 hours)
    ├─ V4: + inference    (1-2 hours)
    └─ Statistical tests  (1 hour)
    Total: 6-8 hours
    
  Người B (Error Analysis):
    ├─ Task 1 analysis    (1-2 hours)
    ├─ Task 2 analysis    (1-2 hours)
    ├─ Task 3 analysis    (1-2 hours)
    ├─ Root cause doc     (1 hour)
    └─ Synthesis report   (1 hour)
    Total: 5-7 hours

  SYNC POINT: End of Day 5
  ├─ Person A: Ablation table + statistical test results
  └─ Person B: Error patterns + insight summary
```

---

## 📝 Final Output (Day 5 Deliverable)

**Người B phải deliver:**

```
evaluation/analysis/day5_error_analysis.json
├─ Task 1 error patterns
├─ Task 2 error patterns  
├─ Task 3 error patterns
└─ Cross-task insights

docs/error_analysis_report.md
├─ Executive summary
├─ Detailed findings per task
├─ Root cause analysis
├─ Recommendations for next iteration
└─ Quantitative breakdown
```

---

## ✅ Checklist Day 5 Người B

- [ ] Task 1: Select 20 failing queries, classify errors
- [ ] Task 1: Document hierarchy gaps + expansion issues
- [ ] Task 2: Analyze 20 bad substitutions vs NPMI baseline
- [ ] Task 2: Constraint violation patterns
- [ ] Task 3: Identify 20 worst dish pairs
- [ ] Task 3: Map to missing relation types
- [ ] Synthesis: Cross-task pattern summary
- [ ] Report: Error analysis markdown document
- [ ] Commit: All results + analysis
