# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this service does

RAG Service is a Vietnamese food knowledge retrieval service. Given a natural-language user query (e.g. "Nấu phở bò tái, bỏ hành lá"), it:
1. Runs local guardrail checks on the input
2. Extracts dish name, extra ingredients, and exclusions via an Ollama LLM
3. Retrieves relevant dish documents from Pinecone using `multilingual-e5-large` embeddings
4. Generates a structured recipe JSON via LLM
5. Resolves ingredients against a local ontology KB
6. Returns a shopping cart with conflict detection, suggestions, and similar dishes

## Required environment variables

```
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=vn-food-rag         # default
OLLAMA_BASE_URL=http://localhost:11434/api  # default
OLLAMA_TEXT_MODEL=qwen2.5:7b             # default
LLM_TIMEOUT=120                          # seconds
EMBEDDING_MODEL_NAME=intfloat/multilingual-e5-large  # default
```

Optional tuning vars: `RECIPE_TOP_K`, `RECIPE_CONTEXT_CHARS`, `RECIPE_MAX_TOKENS`, `EXTRACT_MAX_TOKENS`, `RECIPE_CACHE_TTL`, `OPTIMIZED_MAX_WORKERS`, `BATCH_SIZE`.

## Commands

```bash
# Run smoke tests (unit + optional integration)
python tests/smoke_test.py

# Run end-to-end pipeline test against a live Ollama instance
python tests/test_pipeline_ollama.py
# With full step-by-step debug output:
TEST_DEBUG_STEPS=1 python tests/test_pipeline_ollama.py

# Run the evaluation suite
python -m evaluation.cli

# Build/rebuild processed documents from raw KB data
python build_rag_documents.py

# Ingest processed documents into Pinecone
python ingestion/ingest_to_pinecone.py
python ingestion/ingest_to_pinecone.py --dry-run        # embed only, no upsert
python ingestion/ingest_to_pinecone.py --limit 100      # partial run
python ingestion/ingest_to_pinecone.py --sample-test-only
```

## Architecture

### Request flow

```
user text → RecipeAnalysisProcessor (app/processor.py)
              └── ShoppingCartPipeline (app/pipeline.py)
                    ├── LLMModelService     → guardrail check + dish/ingredient extraction via Ollama
                    ├── PineconeKBService   → Pinecone retrieval + LLM recipe generation
                    ├── OntologyService     → local JSON KB for ingredient/dish lookups
                    ├── IngredientResolver  → fuzzy name→ID resolution
                    ├── ConflictDetectionService → ingredient conflict rules
                    ├── SuggestionService   → co-occurrence-based ingredient suggestions
                    ├── UnitConverterService → quantity/unit normalisation
                    └── ValidationService   → co-occurrence matrix validation
```

### Key modules

| Path | Role |
|---|---|
| `app/pipeline.py` | `ShoppingCartPipeline` — main orchestrator with TTL caches and ThreadPoolExecutor for parallel conflict/suggestion/similar-dish calls |
| `app/processor.py` | `RecipeAnalysisProcessor` — thin wrapper that validates Pydantic request/response and delegates to the pipeline |
| `app/services/llm_client.py` | Ollama `/api/chat` client; configured via env vars |
| `app/services/llm_model_service.py` | Dish extraction prompt + local guardrail pre-check |
| `app/services/pinecone_kb_service.py` | Pinecone search + LLM recipe JSON generation; shares a singleton `Retriever` via `REUSE_SHARED_RETRIEVER` env var |
| `app/services/ontology_service.py` | Loads `app/data/knowledge_base/` JSON files into memory |
| `app/guardrails/policies.py` | `GuardrailPolicyEvaluator` — loads `*_policy.yaml` files, supports regex/keyword/allergy rule types |
| `ingestion/embedding.py` | `EmbeddingModel` wrapping `multilingual-e5-large` via `sentence-transformers`; uses `passage:` prefix for documents, `query:` for queries |
| `ingestion/ingest_to_pinecone.py` | Ingestion pipeline: discover docs → build metadata → embed → upsert to Pinecone |
| `retrieval/retriever.py` | `Retriever` wrapping Pinecone `index.query()`; supports `search_basic`, `search_filtered`, `search_grouped` |
| `evaluation/` | Three-layer evaluation framework (Layer A: dish accuracy, Layer B: conflict detection, Layer C: replacement suggestions) |

### Data layout

- `app/data/knowledge_base/` — local ingredient and dish KB (JSON)
- `app/data/conflict/` — ingredient conflict rules
- `app/data/cooccurrence/` — co-occurrence matrix used by `ValidationService` and `SuggestionService`
- `app/guardrails/` — policy YAML files + Vietnamese keyword blocklist
- `processed/` — output of `build_rag_documents.py` (cleaned JSON + retrieval text docs)
- `evaluation/data/datasets/` — JSONL test sets for each evaluation layer
- `evaluation/outputs/` — evaluation result JSONs

### Evaluation layers

- **Layer A** (dish query): measures `dish_accuracy`, `macro_f1_all`, `macro_f1_core` split by `in_kb` / `out_kb`
- **Layer B** (conflict unit): measures `macro_f1` for conflict pair detection; `in_kb` rows with `f1_all <= 0.65` are filtered when averaging Layer A `in_kb` metrics
- **Layer C** (replacement constraint): measures `overall_valid_rate_mean`, `coverage_rate`, `category_match_rate`

Do not release if Layer B drops significantly (safety risk). Warn if Layer A `out_kb` drops while `in_kb` improves (overfitting signal).
