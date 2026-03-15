# Evaluation Migration Report

## A. Overview of the old evaluation module in AI_service

Observed source of truth:
- `AI_Service/evaluation/evaluation.ipynb`
- `AI_Service/evaluation/01_build_eval_datasets.ipynb`
- `AI_Service/evaluation/datasets/*`
- `AI_Service/evaluation/outputs/*`

### Purpose
The old module evaluates three layers of behavior:
1. Layer A: dish query -> pipeline output quality
2. Layer B: conflict detection quality
3. Layer C: replacement suggestion constraint satisfaction

### Major components in old module
- API/routes: none. Notebook execution only.
- Service layer (imported):
  - `app.main_optimized.OptimizedShoppingCartPipeline`
  - `app.services.ontology_service.OntologyService`
  - `app.services.conflict_service.ConflictDetectionService`
- Utility helpers in notebook:
  - JSONL loading, text normalization, PR/F1 helpers, pair matching helpers
- Metrics computation:
  - set-based PR/F1 (Layer A)
  - pair-based PR/F1 (Layer B)
  - constraint validation rates (Layer C)
- Dataset / GT / predictions loaders:
  - JSONL from `evaluation/datasets/...`
  - live predictions by calling pipeline/service methods
- Output/report generation:
  - JSONL details + CSV-like per-case outputs + JSON summaries in `evaluation/outputs`

### End-to-end workflow in old module
Input accepted:
- Dish query dataset records (in-kb/out-kb)
- Conflict unit dataset records
- Replacement constraint dataset records

Files/data read:
- `dish_queries_in_kb.jsonl`
- `dish_queries_out_kb.jsonl`
- `conflict_unit_tests.jsonl`
- `replacement_cases.jsonl`

Pipeline executed:
- Layer A: `pipeline.process(user_input)` for each case
- Layer B: `conflict_service.check_conflicts("", items)`
- Layer C: `ontology.get_replacement_suggestions(...)`

Metrics computed:
- Layer A: dish accuracy, macro F1 (all/core), excluded_ok, extra_ok, error rate
- Layer B: pair PR/F1, macro F1, F1 by input format
- Layer C: valid-rate, coverage, category/exclusion/uniqueness rates

Artifacts written:
- Per-case result files (`layerA_*`, `conflict_unit_results`, `replacement_results`)
- Layer summaries (`layerA_summary.json`, `layerC_summary.json`)
- `overall_summary.json`

Response/output returned:
- notebook cell outputs + written artifacts, no service API contract.

## B. Structural/logical elements worth preserving

Preserve:
- Three-layer evaluation split (A/B/C)
- Dataset-driven execution with strict JSONL contracts
- Separation between per-case metrics and aggregate summaries
- Artifact-first outputs (detailed rows + compact summary)
- Deterministic offline dataset generation strategy (from old builder notebook)

Do not preserve as-is:
- Notebook-centric orchestration
- Inline helper sprawl with side effects and mutable global state
- Tight assumptions about old pipeline internals

## C. Proposed evaluation structure for rag_service

Placement:
- `rag_service/evaluation/` (package)

Implemented structure:
- `evaluation/config.py` -> paths and location policy
- `evaluation/contracts.py` -> pydantic schemas for datasets/artifacts
- `evaluation/io_jsonl.py` -> JSONL/JSON readers and writers
- `evaluation/loaders.py` -> typed dataset loading
- `evaluation/adapters.py` -> adapter interfaces + live rag adapter
- `evaluation/metrics/common.py` -> shared metric primitives
- `evaluation/metrics/layer_a.py` -> Layer A scoring + summary
- `evaluation/metrics/layer_b.py` -> Layer B scoring + summary
- `evaluation/metrics/layer_c.py` -> Layer C scoring + summary
- `evaluation/reporting.py` -> artifact writing abstraction
- `evaluation/runners.py` -> orchestration coordinator
- `evaluation/cli.py` -> command-line entrypoint
- `evaluation/README.md` -> usage and structure

Data location (new):
- `evaluation/data/datasets/...`

Outputs location (new):
- `evaluation/outputs/...`

## D. Mapping old AI_service components to new rag_service components

- `evaluation.ipynb` orchestration -> `evaluation/runners.py::EvaluationCoordinator`
- Notebook utility functions -> `evaluation/io_jsonl.py` + `evaluation/metrics/common.py`
- Layer A notebook block -> `evaluation/metrics/layer_a.py` + runner layer A method
- Layer B notebook block -> `evaluation/metrics/layer_b.py` + runner layer B method
- Layer C notebook block -> `evaluation/metrics/layer_c.py` + runner layer C method
- Pipeline/service direct calls in notebook -> `evaluation/adapters.py::LiveRAGAdapter`
- Summary/overall JSON writes -> `evaluation/reporting.py`

## E. Minimal skeleton code for each proposed file

The skeleton has been implemented directly in:
- `evaluation/config.py`
- `evaluation/contracts.py`
- `evaluation/io_jsonl.py`
- `evaluation/loaders.py`
- `evaluation/adapters.py`
- `evaluation/metrics/common.py`
- `evaluation/metrics/layer_a.py`
- `evaluation/metrics/layer_b.py`
- `evaluation/metrics/layer_c.py`
- `evaluation/reporting.py`
- `evaluation/runners.py`
- `evaluation/cli.py`

## F. Migration notes, risks, and implementation priorities

### Notes
- Old workflow is preserved at architecture/data-flow level, not code-level copy.
- New module uses package boundaries and typed contracts to reduce coupling.

### Risks
1. Live evaluation runtime depends on configured LLM/Pinecone env vars.
2. Dataset schema drift can break strict pydantic validation.
3. Old outputs mixed CSV/JSONL formats; new module currently standardizes row outputs to JSONL.

### Priorities
1. Add replay mode adapter (evaluate saved prediction files without live model calls).
2. Add per-layer command filters in CLI (`--layer A|B|C|all`).
3. Add optional pandas CSV exporter if downstream tooling still expects CSV.
4. Add dataset-builder scripts (python modules) replacing `01_build_eval_datasets.ipynb`.
5. Add test suite for metric invariants and sample-case contract tests.
