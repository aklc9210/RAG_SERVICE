# PHASE 3 PLANNING: Advanced Enhancements

**Planning Stage:** Pre-implementation (awaiting Phase 2 validation)  
**Estimated Duration:** 2-3 weeks  
**Target Improvements:** -15% each (continuing from Phase 2)

---

## Phase 3 Objectives

### Overall Goal
Achieve cumulative 70% improvement across Task 2 and Task 3 by implementing advanced context-aware and hierarchy-aware features.

### Targeted Improvements
- **Task 2:** 29% → <20% fail rate (Phase 2 baseline)
- **Task 3:** 65-70% → <50% overprediction (Phase 2 baseline)

---

## Task 2: Phase 3 - LLM Fine-tuning & Context Learning

### Problem Analysis (To Be Conducted After Phase 2)
After Phase 2 evaluation, analyze:
- [ ] Which substitution types are still failing?
- [ ] Are there dish-specific patterns in failures?
- [ ] What constraints are hardest to validate?
- [ ] Where does LLM scoring diverge from rules?

### Solution Components

#### 3.2.1: Negative Example Dataset
**Goal:** Build LLM training dataset from failures

**Approach:**
1. Extract Phase 2 failing cases
2. Categorize by failure type:
   - Missed good substitutions
   - Accepted bad substitutions
   - Constraint misunderstandings
   - Context-specific failures

3. Create annotated dataset:
```python
negative_examples = [
    {
        "dish": "Phở bò",
        "ingredient": "Thịt bò tái",
        "suggestion": "Thịt đã nấu",
        "correct_score": 0,
        "reason": "Raw meat required for phở"
    },
    {
        "dish": "Bánh kem",
        "ingredient": "Sữa tươi",
        "suggestion": "Sữa dừa",
        "correct_score": 1,
        "reason": "Borderline - affects flavor"
    }
]
```

**Deliverable:** `app/data/llm_training_examples.json`

#### 3.2.2: LLM Fine-tuning
**Goal:** Adapt LLM for Vietnamese cuisine context

**Approach:**
1. Use Ollama fine-tuning (if supported) or:
2. Build dish-specific prompts with in-context examples:
```python
SYSTEM_PROMPT = """You are a Vietnamese cuisine expert specialized in ingredient substitutions.

Key principles:
1. Phở and canh require fresh, delicate ingredients
2. Fried dishes accept textured substitutes
3. Raw constraints are CRITICAL for phở, bánh mì
4. Cultural authenticity matters for traditional dishes
"""

EXAMPLES = [
    ("Phở bò", "Thịt bò tái", "Tofu", "no_meat", 2),  # Good
    ("Phở bò", "Thịt bò tái", "Thịt nấu", None, 0),     # Bad
]
```

3. Test on validation set
4. Iterate based on results

**Deliverable:** `app/config/dish_substitution_prompts.json`

#### 3.2.3: Ensemble Refinement
**Goal:** Optimize rule + LLM combination

**Approach:**
1. Analyze Phase 2 confidence scores
2. Adjust weights: currently 60% rule / 40% LLM
3. Test variations:
   - 50/50 (rule + LLM equal)
   - 40/60 (LLM-dominant)
   - Dish-specific weights
   - Role-specific weights

4. Choose configuration with highest accuracy

**Deliverable:** `app/config/substitution_ensemble_weights.json`

#### 3.2.4: Dish-Specific Rules
**Goal:** Handle special cases and exceptions

**Approach:**
1. Identify dishes with unique constraints:
   - Phở: Raw meat required
   - Bánh mì: Crusty bread essential
   - Canh: Light broth, fresh greens
   - Cơm: Rice as base

2. Create special rule sets:
```python
DISH_RULES = {
    "Phở bò": {
        "preserved_roles": ["PRIMARY_PROTEIN"],
        "texture_requirement": "tender_raw",
        "required_freshness": "high",
        "substitutable": ["aromatic", "vegetable"],
    },
    "Bánh mì": {
        "critical_elements": ["bread", "pâté"],
        "flexible": ["pickled_vegetables", "seasoning"],
    }
}
```

3. Apply dish rules before LLM scoring

**Deliverable:** `app/config/dish_specific_rules.json`

### Phase 3 Task 2 Milestones

| Week | Milestone | Deliverable |
|------|-----------|-------------|
| 1 | Failure analysis | `llm_training_examples.json` |
| 1-2 | LLM fine-tuning | `dish_substitution_prompts.json` |
| 2 | Ensemble optimization | `substitution_ensemble_weights.json` |
| 2-3 | Dish-specific rules | `dish_specific_rules.json` |
| 3 | Validation & tuning | Final metrics |

**Expected Result:** 29% → <20% fail rate

---

## Task 3: Phase 3 - Hierarchy & Regional Enrichment

### Problem Analysis (To Be Conducted After Phase 2)
After Phase 2 evaluation, analyze:
- [ ] Where do semantic matrices fail?
- [ ] Are there regional dish variations?
- [ ] What ingredient categories are most confused?
- [ ] Missing ingredient type distinctions?

### Solution Components

#### 3.3.1: Ingredient Type Hierarchy
**Goal:** Add sub-category similarity computation

**Current State:** Only vegetable/protein distinction  
**Target State:** Fine-grained ingredient families

**Approach:**
1. Create hierarchy:
```json
{
  "VEGETABLE": {
    "leafy_green": ["cải bẹ", "rau dền", "mồng tơi"],
    "gourd": ["bông bí", "bí xanh", "mướp"],
    "root": ["cà rốt", "khoai tây"],
    "flower": ["nụ hoa chuối", "hoa bí"],
  },
  "PRIMARY_PROTEIN": {
    "beef": ["thịt bò", "thịt bò nạm"],
    "chicken": ["thịt gà", "gà luộc"],
    "seafood": ["cá", "tôm", "mực"],
  }
}
```

2. Compute within-family similarity (high)
3. Compute cross-family similarity (low)
4. Weight by family match

**Deliverable:** `app/data/ingredient_family_hierarchy.json`

#### 3.3.2: Regional Dish Variants
**Goal:** Distinguish regional cooking styles

**Approach:**
1. Add region metadata to dishes:
```json
{
  "dish_id": "phở_bò_001",
  "name_vi": "Phở bò",
  "regions": ["Hà Nội", "TP.HCM", "Huế"],
  "variant_info": {
    "Hà Nội": {
      "broth": "light",
      "spices": "minimal",
      "noodles": "thin"
    },
    "TP.HCM": {
      "broth": "rich",
      "spices": "moderate",
      "noodles": "medium"
    }
  }
}
```

2. Penalize similarity if regions differ
3. Consider "adaptable" dishes (work in multiple regions)

**Deliverable:** `app/data/regional_dish_variants.json`

#### 3.3.3: Ingredient-Type Semantic Matrix
**Goal:** Compute similarity within ingredient types

**Approach:**
1. Use embeddings to compute more precise similarities:
```
# Instead of: cải bẹ ↔ bông bí = 0.15
# Compute:    cải bẹ ↔ bông bí = 0.08 (very different types)
# And:        cải bẹ ↔ rau dền = 0.82 (same family)
```

2. Build per-family matrices
3. Combine with type hierarchy
4. Use in ingredient_semantic component

**Deliverable:** `app/config/ingredient_family_matrices.json`

#### 3.3.4: Cross-Category Fallback Rules
**Goal:** Handle ingredient mismatches gracefully

**Approach:**
1. Define fallback similarities:
   - Same family: high (0.8-0.95)
   - Different family, same category: medium (0.4-0.6)
   - Different category: low (0.1-0.3)

2. Create substitution matrix:
```
vegetable → vegetable:     0.8+
vegetable → protein:       0.2 (rarely acceptable)
protein → protein:         0.75+
protein → vegetable:       0.1 (only tofu)
aromatic → aromatic:       0.85+
```

3. Apply with constraint checking

**Deliverable:** `app/config/cross_category_fallbacks.json`

#### 3.3.5: Update Weights for Phase 3
**Goal:** Optimize weights with new components

**Proposal:**
```json
{
  "class_overlap": 0.10,                    // Reduced further
  "cooking_method_match": 0.15,             // Reduced
  "idf_jaccard": 0.40,                      // Stable
  "ingredient_semantic": 0.20,              // Reduced (more precise)
  "ingredient_family": 0.10,                // NEW
  "regional_adaptation": 0.05,              // NEW
}
```

**Deliverable:** `app/config/similarity_weights_v3.json`

### Phase 3 Task 3 Milestones

| Week | Milestone | Deliverable |
|------|-----------|-------------|
| 1 | Ingredient families | `ingredient_family_hierarchy.json` |
| 1-2 | Regional variants | `regional_dish_variants.json` |
| 2 | Refined matrices | `ingredient_family_matrices.json` |
| 2-3 | Fallback rules | `cross_category_fallbacks.json` |
| 3 | Weight optimization | `similarity_weights_v3.json` |

**Expected Result:** 65-70% → <50% overprediction

---

## System Performance Optimization (Phase 3)

### 3.4.1: LLM Call Optimization
- Batch LLM calls for multiple substitutions
- Increase caching TTL for common queries
- Pre-compute common substitutions

### 3.4.2: Semantic Matrix Performance
- Use approximate nearest neighbors for large matrices
- Consider vector database if matrices grow
- Profile memory usage

### 3.4.3: Evaluation Efficiency
- Cache component computations
- Parallelize similarity calculations
- Use multiprocessing for evaluation

---

## Phase 3 Implementation Timeline

### Week 1: Analysis & Planning
- [ ] Phase 2 evaluation complete
- [ ] Failure analysis for both tasks
- [ ] Prioritize Phase 3 improvements
- [ ] Create detailed implementation specs

### Week 2: Core Implementation
- [ ] LLM fine-tuning (Task 2)
- [ ] Hierarchy enrichment (Task 3)
- [ ] Configuration files created
- [ ] Initial testing

### Week 3: Refinement & Optimization
- [ ] Ensemble weight tuning
- [ ] Regional adaptation testing
- [ ] Performance optimization
- [ ] Final validation

### Week 4: Documentation & Release
- [ ] Complete Phase 3 checkpoint
- [ ] Update all documentation
- [ ] Prepare for production
- [ ] Plan Phase 4 if needed

---

## Success Criteria for Phase 3

### Task 2 Success
- [ ] Fail rate < 20% (target: -15% from Phase 2)
- [ ] LLM accuracy > 85%
- [ ] All dish-specific rules validated
- [ ] No regressions in Phase 1/2

### Task 3 Success
- [ ] Overprediction < 50% (target: -15% from Phase 2)
- [ ] Ingredient families properly weighted
- [ ] Regional variants handled correctly
- [ ] No regressions in Phase 1/2

### System Success
- [ ] All components integrated
- [ ] Performance within SLA
- [ ] Documentation complete
- [ ] Ready for production deployment

---

## Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| LLM over-fitting | Medium | High | Use diverse validation set |
| Regional conflicts | Low | High | Clear priority rules |
| Performance degradation | Low | Medium | Caching + optimization |
| Integration complexity | Medium | Medium | Phased approach |

---

## Phase 4 Planning (If Time Permits)

Potential enhancements:
- Multi-dish recipe optimization
- Seasonal ingredient availability
- Cultural authenticity scoring
- Nutritional profile matching
- Cost optimization

---

## Files to Create (Phase 3)

```
app/data/
├── llm_training_examples.json
├── ingredient_family_hierarchy.json
├── regional_dish_variants.json

app/config/
├── dish_substitution_prompts.json
├── substitution_ensemble_weights.json
├── dish_specific_rules.json
├── ingredient_family_matrices.json
├── cross_category_fallbacks.json
├── similarity_weights_v3.json

docs/
├── PHASE3_ANALYSIS.md
├── PHASE3_IMPLEMENTATION_PLAN.md

scripts/
├── phase3_failure_analysis.py
├── phase3_ensemble_tuning.py
├── phase3_hierarchy_builder.py
```

---

## Decision Points Before Phase 3

**Before starting Phase 3, answer:**

1. **Phase 2 Success?**
   - [ ] YES - Proceed with Phase 3
   - [ ] PARTIAL - Iterate Phase 2
   - [ ] NO - Debug Phase 2 issues

2. **Task 2 Focus?**
   - [ ] YES - Deep LLM fine-tuning
   - [ ] NO - Light touch, maintain Phase 2

3. **Task 3 Focus?**
   - [ ] YES - Full hierarchy enrichment
   - [ ] NO - Light touch, maintain Phase 2

4. **Timeline Feasible?**
   - [ ] YES - 2-3 week Phase 3
   - [ ] NO - Defer to Phase 4

5. **Resources Available?**
   - [ ] YES - Full team
   - [ ] NO - Scaled approach

---

## Success Metric Summary

### Cumulative Improvements After Phase 3

```
Task 2:
  Day 5 Baseline:     59% fail
  After Phase 1:      44% fail (-15%)
  After Phase 2:      29% fail (-15%)
  After Phase 3:      <20% fail (-15%)
  Total:              -67% improvement

Task 3:
  Day 5 Baseline:     90.9% overprediction
  After Phase 1:      80-85% (-15%)
  After Phase 2:      65-70% (-15%)
  After Phase 3:      <50% (-15%)
  Total:              -45% improvement
```

---

## Next Actions

1. ✅ Phase 2 Implementation - COMPLETE
2. ⏳ Phase 2 Evaluation - IN PROGRESS
3. ⏳ Phase 2 Metrics Validation - PENDING
4. 📋 Phase 3 Analysis - READY (awaiting Phase 2 data)
5. 📋 Phase 3 Implementation - QUEUED

---

**Status:** Phase 3 Planning Document Created - Ready for Post-Phase-2 Execution

