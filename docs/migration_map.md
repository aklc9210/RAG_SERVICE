# Migration Map: AI_service → rag_service

Generated: 2026-03-15

This document maps every relevant module from `AI_service/` to its fate in `rag_service/`.

---

## Legend

| Classification | Meaning |
|---|---|
| **keep** | Logic preserved as-is, imports adjusted |
| **adapt** | Business logic preserved, AWS/Bedrock coupling removed |
| **replace** | Entire responsibility replaced by new implementation |
| **drop** | No longer needed in new architecture |

---

## Module Classification Table

### Core Runtime / Orchestration

| Old path (`AI_service/`) | Responsibility | Classification | Target (`rag_service/`) | Reason |
|---|---|---|---|---|
| `app/main_optimized.py` | Main pipeline: extract → retrieve → assemble → respond | adapt | `app/pipeline.py` | Business logic kept; Bedrock KB + model calls replaced with Pinecone + new LLM |
| `app/rabbitmq/processor.py` | Request parsing, validation, pipeline dispatch | adapt | `app/processor.py` | Orchestration logic kept; S3 image service removed; schema imports adjusted |
| `app/rabbitmq/consumer.py` | RabbitMQ RPC consumer | keep | `app/rabbitmq/consumer.py` *(future optional)* | Pure infrastructure; unchanged if RabbitMQ transport is adopted |
| `app/rabbitmq/config.py` | RabbitMQ connection config | keep | `app/rabbitmq/config.py` *(future optional)* | Pure config; unchanged |
| `app/schemas.py` | Pydantic request/response schemas | keep | `app/schemas.py` | Same response contract preserved |

### Bedrock-Specific (Replaced)

| Old path (`AI_service/`) | Responsibility | Classification | Target (`rag_service/`) | Reason |
|---|---|---|---|---|
| `app/services/bedrock_client.py` | GuardrailedBedrockClient wrapping boto3 | replace | `app/services/llm_client.py` | All AWS SDK calls removed; replaced with provider-agnostic HTTP/OpenAI-style client |
| `app/services/invoke_model_service.py` | BedrockModelService: dish extraction + image extraction via Bedrock LLM | replace | `app/services/llm_model_service.py` | Prompts kept; model invocation replaced with new LLM client |
| `app/services/bedrock_kb_service.py` | BedrockKBService: Bedrock Agent Runtime KB retrieval + Nova LLM generate | replace | `app/services/pinecone_kb_service.py` | Pinecone retrieval replaces Bedrock KB; recipe generation prompt kept; LLM invocation replaced |
| `app/services/s3_image_service.py` | S3 image download as base64 | drop | — | New architecture does not require S3 image ingestion; image path can be added later via URL fetch |
| `app/services/guardrails/aws_guardrail_handler.py` | AWS Bedrock Guardrails input/output check | drop | — | AWS Bedrock Guardrails API removed; local policy evaluator covers the same need |
| `app/services/guardrails/safe_completion_generator.py` | Uses Bedrock Claude to generate safe completion text | adapt | *(built into `app/services/llm_model_service.py`)* | LLM call re-targeted to new provider; same prompt contract |

### Reusable Business Logic (Kept / Adapted)

| Old path (`AI_service/`) | Responsibility | Classification | Target (`rag_service/`) | Reason |
|---|---|---|---|---|
| `app/services/ontology_service.py` | Ingredient/dish KB lookup, similar dish search, role/coverage scoring | adapt | `app/services/ontology_service.py` | Singleton pattern preserved; data path adjusted for new project layout |
| `app/services/conflict_service.py` | Ingredient conflict detection with replacement suggestions | adapt | `app/services/conflict_service.py` | Full logic kept; data path adjusted |
| `app/services/ingredient_resolver.py` | Fuzzy name→ID resolution with token matching | keep | `app/services/ingredient_resolver.py` | Pure algorithm; no AWS dependency |
| `app/services/suggestion_service.py` | PMI-based ingredient suggestions and similar dish search | keep | `app/services/suggestion_service.py` | Pure business logic; no AWS dependency |
| `app/services/unit_converter_service.py` | Weight/volume/count unit normalization for Vietnamese recipes | keep | `app/services/unit_converter_service.py` | Pure conversions; no AWS dependency |
| `app/services/validation_service.py` | Co-occurrence matrix PMI scoring, missing ingredient check | adapt | `app/services/validation_service.py` | Data path adjusted; no AWS dependency |

### Guardrails

| Old path (`AI_service/`) | Responsibility | Classification | Target (`rag_service/`) | Reason |
|---|---|---|---|---|
| `app/guardrails/policies.py` | GuardrailPolicyEvaluator: regex/keyword/allergy rule evaluation | keep | `app/guardrails/policies.py` | Pure local logic; no AWS dependency |
| `app/guardrails/policy_handler.py` → `app/services/guardrails/policy_handler.py` | Apply policies to model response | adapt | `app/services/guardrail_service.py` | AWS-dependent parts removed; local-only policy application |
| `app/guardrails/ethics_policy.yaml` | Extreme edge-case ethical rules | keep | `app/guardrails/ethics_policy.yaml` | YAML data; no Bedrock dependency |
| `app/guardrails/pii_policy.yaml` | PII detection/redaction rules | keep | `app/guardrails/pii_policy.yaml` | YAML data; no Bedrock dependency |
| `app/guardrails/keywords_vi.json` | Vietnamese keyword blocklist | keep | `app/guardrails/keywords_vi.json` | JSON data file |
| `app/guardrails/__init__.py` | Exports GuardrailPolicyEvaluator | keep | `app/guardrails/__init__.py` | |

### Utilities

| Old path (`AI_service/`) | Responsibility | Classification | Target (`rag_service/`) | Reason |
|---|---|---|---|---|
| `app/utils/text_match.py` | Accent stripping, token-set scoring, fuzzy_score | keep | `app/utils/text_match.py` | Pure algorithm |
| `app/utils/string_utils.py` | norm_text, strip_accents, similarity_ratio | keep | `app/utils/string_utils.py` | Pure algorithm |
| `app/utils/number_utils.py` | parse_number, parse_quantity | keep | `app/utils/number_utils.py` | Pure algorithm |
| `app/utils/json_utils.py` | parse_json_content, extract_textual_content, extract_prompt_from_body + S3 read | adapt | `app/utils/json_utils.py` | S3/boto3 function removed; rest kept |

### Data Files (Copied)

| Old path (`AI_service/`) | Target (`rag_service/`) | Notes |
|---|---|---|
| `app/data/knowledge_base/ingredient_knowledge_base.json` | `app/data/knowledge_base/ingredient_knowledge_base.json` | Required by OntologyService |
| `app/data/knowledge_base/dish_knowledge_base.json` | `app/data/knowledge_base/dish_knowledge_base.json` | Required by OntologyService |
| `app/data/conflict/ingredient_conflict.json` | `app/data/conflict/ingredient_conflict.json` | Required by ConflictDetectionService |
| `app/data/cooccurrence/matrix.json` | `app/data/cooccurrence/matrix.json` | Required by ValidationService |
| `app/data/cooccurrence/frequency.json` | `app/data/cooccurrence/frequency.json` | Required by ValidationService |
| `app/data/cooccurrence/metadata.json` | `app/data/cooccurrence/metadata.json` | Required by ValidationService |

---

## New Modules Created in rag_service

These have no direct counterpart in AI_service — they are new implementations to replace Bedrock.

| New path (`rag_service/`) | Purpose |
|---|---|
| `app/services/llm_client.py` | Provider-agnostic LLM HTTP client (OpenAI-compatible API) |
| `app/services/llm_model_service.py` | LLM-based dish extraction service (replaces BedrockModelService) |
| `app/services/pinecone_kb_service.py` | Pinecone retrieval + LLM recipe generation (replaces BedrockKBService) |
| `app/services/guardrail_service.py` | Local-only guardrail policy application (no AWS SDK) |
| `app/pipeline.py` | Full replacement pipeline: extract → Pinecone retrieve → LLM generate → downstream → respond |
| `app/processor.py` | Request processor that dispatches to Pipeline |
| `app/schemas.py` | Pydantic request/response schemas (identical to AI_service) |

---

## Dropped Modules

| Old path (`AI_service/`) | Reason Dropped |
|---|---|
| `app/services/bedrock_client.py` | All Bedrock runtime calls removed |
| `app/services/s3_image_service.py` | S3 infrastructure not available in new stack |
| `app/services/guardrails/aws_guardrail_handler.py` | AWS Bedrock Guardrails API not needed |
| `app/services/guardrails/safe_completion_generator.py` | Bedrock-specific; inlined into llm_model_service with new provider |
| `app/rabbitmq/worker_threaded.py` | Infrastructure; can be adopted verbatim if needed later |
| `app/scripts/` | One-off build scripts; not runtime |

---

## Conceptual Flow Mapping

```
OLD (AI_service):
  user_input
    → GuardrailedBedrockClient.check_raw_input()   [AWS Bedrock Guardrail]
    → BedrockModelService.extract_dish_name()       [AWS Bedrock LLM]
    → OntologyService / IngredientResolver           [local]
    → BedrockKBService.get_dish_recipe()            [AWS Bedrock KB + Nova LLM]
    → UnitConverterService                           [local]
    → ConflictDetectionService                       [local]
    → SuggestionService / ValidationService          [local]
    → _build_response()                              [local]

NEW (rag_service):
  user_input
    → GuardrailPolicyEvaluator.evaluate()           [local policy rules - no AWS]
    → LLMModelService.extract_dish_name()           [new LLM provider - OpenAI API compat]
    → OntologyService / IngredientResolver           [local - same as before]
    → PineconeKBService.get_dish_recipe()           [Pinecone retrieve + new LLM generate]
    → UnitConverterService                           [local - same as before]
    → ConflictDetectionService                       [local - same as before]
    → SuggestionService / ValidationService          [local - same as before]
    → _build_response()                              [local - same structure as before]
```
