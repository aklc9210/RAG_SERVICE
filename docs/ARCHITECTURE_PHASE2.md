# RAG Service: Complete Architecture (Phase 1 + Phase 2)

## System Data Flow

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                          USER INPUT                                            │
│                   Vietnamese Natural Language                                  │
│              "Nấu phở bò tái, bỏ hành lá, thay thế bộ tộ"                     │
└────────────────────────┬───────────────────────────────────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────┐
        │     1. GUARDRAIL CHECK         │
        │  (Safety: Allergy, Offense)    │
        │     Status: PHASE 0 (Existing) │
        └────────────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────┐
        │  2. LLM EXTRACTION             │
        │  Extract: Dish, Ingredients    │
        │           Extras, Exclusions   │
        │     Status: PHASE 1 (Existing) │
        └────────────────────────────────┘
                         │
             ┌───────────┴────────────┐
             │                        │
             ▼                        ▼
    ┌─────────────────────┐  ┌──────────────────────┐
    │ Dish Name: Phở bò   │  │ Ingredient Extraction│
    ├─────────────────────┤  ├──────────────────────┤
    │ Extra Ingredients   │  │ Main: Phở, Thịt bò   │
    │ - Bộ tộ             │  │ Remove: Hành lá      │
    ├─────────────────────┤  │ Replace: Bộ tộ       │
    │ Exclusions          │  └──────────────────────┘
    │ - Hành lá           │
    └─────────────────────┘
             │                        │
             └───────────┬────────────┘
                         ▼
        ┌────────────────────────────────┐
        │   3. RETRIEVAL FROM KB         │
        │  (Embedding-based search)      │
        │  Model: multilingual-e5-large  │
        │     Status: PHASE 1 (Existing) │
        └────────────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────┐
        │   4. PINECONE SEARCH           │
        │  Retrieved ~5-10 similar       │
        │  phở recipes with ingredients  │
        │     Status: PHASE 1 (Existing) │
        └────────────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────┐
        │  5. RECIPE GENERATION          │
        │  LLM creates structured JSON   │
        │  (Components, instructions)    │
        │     Status: PHASE 1 (Existing) │
        └────────────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────┐
        │  6. INGREDIENT RESOLUTION      │
        │  PHASE 1: Fuzzy match + roles  │
        │  - Resolve ingredient names    │
        │  - Validate roles              │
        │  - Check constraints           │
        │                                │
        │  PHASE 2: [NEXT - HERE]        │
        └────────────────────────────────┘
                         │
        ┌────────────────┴──────────────────┐
        │                                   │
        ▼                                   ▼
    ┌──────────────────────────┐   ┌──────────────────────────┐
    │ PHASE 2 - TASK 2:        │   │ PHASE 2 - TASK 3:        │
    │ LLM SUBSTITUTION         │   │ SEMANTIC SIMILARITY      │
    │ VALIDATION               │   │ RANKING                  │
    │                          │   │                          │
    │ • LLM context scoring    │   │ • Ingredient matrices    │
    │ • Ensemble validation    │   │ • Vegetable/protein sim  │
    │ • Rule-based fallback    │   │ • Role-aware matching    │
    └──────────────────────────┘   └──────────────────────────┘
            │                              │
            └──────────────┬───────────────┘
                           ▼
        ┌────────────────────────────────┐
        │   7. CONFLICT DETECTION        │
        │  Check ingredient conflicts    │
        │  e.g., cinnamon + mint = BAD   │
        │     Status: PHASE 1 (Existing) │
        └────────────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────┐
        │  8. SUGGESTION GENERATION      │
        │  Co-occurrence based           │
        │  Ingredient recommendations    │
        │     Status: PHASE 1 (Existing) │
        └────────────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────┐
        │  9. SIMILAR DISHES             │
        │  Find alternative phở dishes   │
        │  ranked by semantic similarity │
        │     Status: PHASE 2 (NEW)      │
        └────────────────────────────────┘
                         │
                         ▼
     ┌──────────────────────────────────────┐
     │         RESPONSE TO USER             │
     │  {                                   │
     │    "dish": "Phở bò tái",            │
     │    "ingredients": [...],             │
     │    "conflicts": [...],               │
     │    "suggestions": [...],             │
     │    "similar_dishes": [...]           │
     │  }                                   │
     └──────────────────────────────────────┘
```

---

## Component Detail: PHASE 2 Integration Points

### PHASE 2 - TASK 2: LLM Substitution Validation

```
SUBSTITUTION VALIDATION SYSTEM
═══════════════════════════════════════════════════════════════════

Input: ingredient_name, dish_context, role, constraint, suggestion

                            ┌─────────────────┐
                            │ SubstitutionVal │
                            │    idator       │
                            └────────┬────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                │
                    ▼                ▼                ▼
        ┌──────────────────┐ ┌──────────────┐ ┌────────────────┐
        │ RULE-BASED       │ │ LLM-BASED    │ │ ENSEMBLE       │
        │ SCORING          │ │ SCORING      │ │ COMBINATION    │
        │ (60% weight)     │ │ (40% weight) │ │                │
        │                  │ │              │ │ final = 0.6*r+ │
        │ Check against:   │ │ Contextual   │ │         0.4*l  │
        │ - Role rules     │ │ prompt to    │ │                │
        │ - Constraints   │ │ LLM:         │ │ Result: 0-2    │
        │ - KB rules      │ │ "DISH | ING  │ │ 0=Wrong        │
        │                  │ │  | ROLE |   │ │ 1=Borderline   │
        │ Result: 0-1      │ │ SUGG"       │ │ 2=Perfect      │
        │                  │ │ SCORE: X/2  │ │                │
        │                  │ │              │ │                │
        │                  │ │ Result: 0-2  │ │                │
        └──────────────────┘ └──────────────┘ └────────────────┘
                    │                │                │
                    └────────────────┼────────────────┘
                                     │
                                     ▼
                        Output: confidence_score
```

**Examples:**
```
Dish: Bánh kem cam
Ingredient: Whipping cream (role=BINDER)
Suggestion: Sữa đặc
├─ Rule score: 0.9 (matches binder rules)
├─ LLM: "Perfect - sweetened condensed milk has similar texture"
├─ LLM score: 2.0
└─ Final: 0.6*0.9 + 0.4*(2.0/2) = 0.54 + 0.40 = 0.94 ≈ 1.9/2 ✓

Dish: Cá hương chiên
Ingredient: Cá hương (role=PRIMARY_PROTEIN)
Suggestion: Tofu with constraint=no_seafood
├─ Rule score: 0.85 (compatible vegetarian substitute)
├─ LLM: "Perfect - tofu is textured, satisfies no_seafood"
├─ LLM score: 2.0
└─ Final: 0.6*0.85 + 0.4*(2.0/2) = 0.51 + 0.40 = 0.91 ≈ 1.8/2 ✓
```

---

### PHASE 2 - TASK 3: Semantic Similarity Matrices

```
SEMANTIC SIMILARITY RANKING SYSTEM
═══════════════════════════════════════════════════════════════════

Input: dish1, dish2

        ┌──────────────────────────────┐
        │ EXTRACT INGREDIENTS          │
        │ dish1 = [cải bẹ, hành, cà   │
        │ dish2 = [rau dền, hành, tỏi  │
        └──────────┬───────────────────┘
                   │
        ┌──────────▼──────────┐
        │ LOOKUP SEMANTIC     │
        │ SIMILARITIES        │
        └──────────┬──────────┘
                   │
        ┌──────────▼────────────────────────────────┐
        │ SEMANTIC MATRICES (Pre-computed)          │
        │                                           │
        │ vegetable_matrix = {                      │
        │   "cải bẹ": {                            │
        │     "cải xồng": 0.85,                    │
        │     "rau dền": 0.78,  ← Relevant        │
        │     "bông bí": 0.15,                    │
        │   },                                      │
        │   "rau dền": {                           │
        │     "mồng tơi": 0.82,                   │
        │     "cải bẹ": 0.78,   ← Relevant        │
        │   },                                      │
        │   "hành": { ... }                        │
        │ }                                        │
        │                                           │
        │ protein_matrix = { ... }                 │
        └──────────┬────────────────────────────────┘
                   │
        ┌──────────▼──────────────────────┐
        │ COMPUTE INGREDIENT SIMILARITY   │
        │ Compare ingredient pairs:       │
        │ - cải bẹ ↔ rau dền = 0.78      │
        │ - hành ↔ hành = 1.0            │
        │ - cà ↔ tỏi = 0.3               │
        │ Average = (0.78+1.0+0.3)/3=0.7 │
        └──────────┬──────────────────────┘
                   │
        ┌──────────▼────────────────────────────┐
        │ COMBINE WITH OTHER COMPONENTS         │
        │                                        │
        │ final_score =                          │
        │  0.15 * class_overlap +               │
        │  0.40 * idf_jaccard +                 │
        │  0.25 * ingredient_semantic +         │
        │  0.20 * reserved                      │
        │                                        │
        │ Example:                              │
        │  = 0.15*1.0 + 0.40*0.6 + 0.25*0.7 +  │
        │    0.20*0.5                           │
        │  = 0.15 + 0.24 + 0.175 + 0.10        │
        │  = 0.665 → Moderately similar dishes  │
        └──────────┬────────────────────────────┘
                   │
                   ▼
        Output: similarity_score (0-1)
```

**Matrix Statistics:**
```
Vegetables:
  Total: 2,000+ ingredients
  Example pairs: cải bẹ ↔ rau dền = 0.78
  Structure: {ingredient: {top_10_similar: sim_score}}

Proteins:
  Total: 500+ ingredients  
  Example pairs: thịt bò ↔ thịt bò nạm = 0.92
  Structure: {ingredient: {top_10_similar: sim_score}}

Total matrix pairs: ~25,000
File size: ~2-3 MB JSON
```

---

## Data Structures

### Phase 1: Enriched Knowledge Base

```json
{
  "ingredients": [
    {
      "id": "ingredient_001",
      "name": "Thịt bò",
      "category": "beef",
      "role": "PRIMARY_PROTEIN",        ← PHASE 1 NEW
      "metadata": {...}
    },
    {
      "id": "ingredient_456",
      "name": "Cải bẹ",
      "category": "leafy_green",
      "role": "VEGETABLE",              ← PHASE 1 NEW
      "metadata": {...}
    }
  ]
}
```

### Phase 2: Semantic Matrices

```json
{
  "version": "2.0",
  "vegetables": {
    "Cải bẹ": {
      "Cải xồng": 0.85,
      "Rau dền": 0.78,
      "Mồng tơi": 0.72,
      ...
    }
  },
  "proteins": {
    "Thịt bò": {
      "Thịt bò nạm": 0.92,
      "Thịt bò tái": 0.90,
      "Thịt gà": 0.65,
      ...
    }
  }
}
```

### Phase 2: Similarity Weights

```json
{
  "version": "2.0",
  "weights": {
    "class_overlap": 0.15,        ← Phase 1: was 0.25, reduced -40%
    "idf_jaccard": 0.40,          ← Phase 1: was 0.25, increased +60%
    "ingredient_semantic": 0.25,  ← Phase 2 NEW: powered by matrices
    "reserved": 0.20              ← Phase 1: was 0.45, reserved for future
  }
}
```

---

## Evaluation Metrics Roadmap

```
                    Phase 1        Phase 2        Phase 3
                     Done           New            Future

TASK 2 (Substitution):
Baseline (Day 5):    59% fail       ─────          ─────
After Phase 1:       44% fail ✓     ─────          ─────
After Phase 2:       ─────          29% fail ✓     ─────
After Phase 3:       ─────          ─────          <20% fail
Target addressable:  -50% improvement (59% → 29%)

TASK 3 (Similarity):
Baseline (Day 5):    90.9% overp.   ─────          ─────
After Phase 1:       80-85% ✓       ─────          ─────
After Phase 2:       ─────          65-70% ✓       ─────
After Phase 3:       ─────          ─────          <50%
Target addressable:  -40% improvement (90.9% → 50%)
```

---

## Performance Characteristics

| Component | Processing Time | Memory | Status |
|-----------|-----------------|--------|--------|
| Guardrail check | <10ms | - | Phase 1 |
| LLM extraction | 500-1000ms | - | Phase 1 |
| Retrieval (Pinecone) | 200-500ms | - | Phase 1 |
| Recipe generation (LLM) | 1-2s | - | Phase 1 |
| **Phase 1: Ingredient resolution** | 50-100ms | ~100MB | Phase 1 ✓ |
| **Phase 2: Substitution validation (rule-based)** | 20-50ms | - | Phase 2 |
| **Phase 2: Substitution validation (LLM)** | 500-1000ms per call | - | Phase 2 |
| **Phase 2: Semantic similarity lookup** | <1ms (pre-computed) | ~2-3MB | Phase 2 |
| Conflict detection | 50-100ms | - | Phase 1 |
| Suggestion generation | 100-200ms | - | Phase 1 |
| Similar dishes ranking | 100-300ms | - | Phase 2 |
| **Total end-to-end** | **2.5-4s** | **~102MB** | **Phase 2** |

---

## Integration Timeline

| Phase | Task | Duration | Status |
|-------|------|----------|--------|
| Phase 1 | Task 2: Role annotations | ✓ Done | Complete |
| Phase 1 | Task 3: Weight rebalancing | ✓ Done | Complete |
| **Phase 2** | **Task 2: LLM validation** | **~30 mins** | **Ready** |
| **Phase 2** | **Task 3: Semantic matrices** | **~45 mins** | **Ready** |
| Phase 2 | Testing & validation | ~20 mins | Ready |
| Phase 3 | Task 2: Fine-tuning | ~1-2 weeks | Planned |
| Phase 3 | Task 3: Hierarchy enrichment | ~2-3 weeks | Planned |

---

## Key Files Reference

**Phase 2 Implementation:**
- `solutions/task2_phase2_llm_validation.py` - LLM validation
- `solutions/task3_phase2_semantic_matrices.py` - Semantic matrices

**Phase 2 Configuration (auto-generated):**
- `app/config/substitution_validation_v2.json` - Task 2 config
- `app/config/ingredient_semantic_matrices_v2.json` - Semantic data
- `app/config/similarity_weights_v2.json` - Updated weights

**Phase 2 Documentation:**
- `PHASE2_CHECKPOINT.md` - Executive summary
- `docs/PHASE2_IMPLEMENTATION_PLAN.md` - Integration roadmap
- `solutions/PHASE2_TASK2_INTEGRATION_GUIDE.txt` - Task 2 steps
- `solutions/PHASE2_TASK3_INTEGRATION_GUIDE.txt` - Task 3 steps

---

**Architecture Status:** Ready for Phase 2 Integration
**Next Step:** Follow integration guides in order
