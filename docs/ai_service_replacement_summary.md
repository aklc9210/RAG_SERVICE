# AI Service → RAG Service Migration Summary

## Overview

This document describes how `AI_service/` (AWS Bedrock-based) was replaced by
`rag_service/` (Pinecone + custom LLM stack).

---

## 1. Stack Comparison

| Concern | AI_service (old) | rag_service (new) |
|---|---|---|
| LLM calls | AWS Bedrock runtime (boto3) | OpenAI-compat HTTP API (`httpx`) |
| Knowledge base retrieval | Bedrock Agent Runtime KB | Pinecone index `vn-food-rag` |
| Embedding model | (Bedrock managed) | `intfloat/multilingual-e5-large` |
| Guardrails | AWS Guardrail API | Local YAML policy evaluation |
| Image processing | AWS S3 + Bedrock Vision | **Dropped** (out of scope) |
| Transport | RabbitMQ (pika) | RabbitMQ (optional); or direct call |
| Cloud SDK | boto3 | none |

---

## 2. Module-by-Module Mapping

### Dropped (no replacement needed)

| AI_service module | Reason |
|---|---|
| `app/services/bedrock_client.py` | All Bedrock SDK calls removed |
| `app/services/s3_image_service.py` | Image ingestion not in scope |
| `app/services/guardrails/policy_handler.py` | Replaced by local `guardrail_service.py` |
| `app/services/guardrails/safe_completion_generator.py` | Inlined into `llm_model_service.py` |
| `app/rabbitmq/consumer.py` | Consumer re-uses existing RabbitMQ infra; not duplicated |
| `app/rabbitmq/config.py` | Same |
| `app/main_optimized.py` | Replaced by `app/pipeline.py` |

### Replaced (new implementation)

| AI_service module | New module | Notes |
|---|---|---|
| `app/services/invoke_model_service.py` (`BedrockModelService`) | `app/services/llm_model_service.py` (`LLMModelService`) | Same prompt, new transport |
| `app/services/bedrock_kb_service.py` (`BedrockKBService`) | `app/services/pinecone_kb_service.py` (`PineconeKBService`) | Pinecone retriever + LLM |

### Kept / Adapted (business logic preserved)

| Module | Changes |
|---|---|
| `app/services/ontology_service.py` | Data path fixed to file-relative `Path(__file__).parent` |
| `app/services/conflict_service.py` | Same; added `vietnamese_name` field lookup |
| `app/services/ingredient_resolver.py` | Checks `name_vi` **and** `vietnamese_name` fields |
| `app/services/unit_converter_service.py` | Import path updated only |
| `app/services/validation_service.py` | Data path fixed |
| `app/services/suggestion_service.py` | Category set extended for Vietnamese KB |
| `app/guardrails/policies.py` | Verbatim copy (no AWS dependency) |
| `app/utils/*.py` | Verbatim copies; S3 helper removed from `json_utils.py` |
| `app/schemas.py` | Verbatim copy; `s3_url` / `image_s3_url` fields removed |

### New (no AI_service equivalent)

| New module | Purpose |
|---|---|
| `app/services/llm_client.py` | Provider-agnostic httpx LLM client |
| `app/services/guardrail_service.py` | Local guardrail wrapper (no AWS SDK) |
| `app/pipeline.py` | Orchestration (replaces `main_optimized.py`) |
| `app/processor.py` | Request dispatcher (replaces `rabbitmq/processor.py`) |
| `app/schemas.py` | Pydantic models (adapted from `AI_service/app/schemas.py`) |

---

## 3. Environment Variables

Add these to `rag_service/.env`:

```dotenv
# LLM provider (OpenAI-compatible)
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
LLM_TIMEOUT=60

# Pinecone
PINECONE_API_KEY=...
PINECONE_INDEX=vn-food-rag
PINECONE_NAMESPACE=          # optional, defaults to empty

# Pipeline tuning (optional)
RECIPE_CACHE_TTL=3600
OPTIMIZED_MAX_WORKERS=3
```

---

## 4. Data Files

All data files copied from `AI_service/` / `vietnamese_recipe_dataset/` to:

```
rag_service/app/data/
  knowledge_base/
    ingredient_knowledge_base.json
    dish_knowledge_base.json
  conflict/
    ingredient_conflict.json
  cooccurrence/
    matrix.json
    frequency.json
    metadata.json

rag_service/app/guardrails/
  ethics_policy.yaml
  pii_policy.yaml
  keywords_vi.json
```

---

## 5. Response Shape

The response schema is **backward-compatible** with `AI_service`.
All fields from `RecipeAnalysisResponse` are preserved.

The only removed field is `s3_url` in the request (`RecipeAnalysisRequest`),
because image processing is not in scope.

---

## 6. Known Gaps / TODOs

| Gap | Notes |
|---|---|
| `_apply_contextual_grounding()` | Was Bedrock-specific; removed. Pinecone retrieval results are already contextually relevant. |
| Image processing (`s3_url`) | Requires a separate vision pipeline; not in scope. |
| RabbitMQ consumer wiring | `app/processor.py` is a drop-in; caller (consumer) must be updated to import from `app.processor` instead of `app.rabbitmq.processor`. |
| LLM provider lock-in | `llm_client.py` uses OpenAI-compat format. Any provider (Together, Groq, Ollama, Azure) works with `LLM_BASE_URL` / `LLM_API_KEY`. |

---

## 7. Quick Start

```bash
# 1. Install dependencies
pip install -r rag_service/requirements.txt

# 2. Configure .env
cp rag_service/.env.example rag_service/.env  # then fill in keys

# 3. Run smoke test
python rag_service/tests/smoke_test.py
```
