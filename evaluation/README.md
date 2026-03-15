# Evaluation Module (rag_service)

This module is a redesigned, maintainable replacement for the old notebook-heavy
`AI_Service/evaluation` workflow.

## Goals

- Preserve evaluation architecture and data flow from old module.
- Separate orchestration, data loading, adapters, metrics, and reporting.
- Keep the module extensible for future metrics or evaluation modes.

## Structure

- `config.py`: evaluation paths and file locations.
- `contracts.py`: pydantic schemas for dataset records and artifact contracts.
- `io_jsonl.py`: JSON/JSONL readers and writers.
- `loaders.py`: typed dataset loaders.
- `adapters.py`: interfaces and live adapter to `app` services/pipeline.
- `metrics/`: metric calculators by layer.
- `reporting.py`: artifact writers.
- `runners.py`: orchestration of Layer A/B/C and overall summary.
- `cli.py`: command line entrypoint.

## Data layout

Expected dataset paths:

- `evaluation/data/datasets/dish_query_set/dish_queries_in_kb.jsonl`
- `evaluation/data/datasets/dish_query_set/dish_queries_out_kb.jsonl`
- `evaluation/data/datasets/conflict_unit_set/conflict_unit_tests.jsonl`
- `evaluation/data/datasets/replacement_constraint_set/replacement_cases.jsonl`

Outputs are written to:

- `evaluation/outputs/layerA_results.jsonl`
- `evaluation/outputs/layerB_results.jsonl`
- `evaluation/outputs/layerC_results.jsonl`
- `evaluation/outputs/layerA_summary.json`
- `evaluation/outputs/layerB_summary.json`
- `evaluation/outputs/layerC_summary.json`
- `evaluation/outputs/overall_summary.json`

## Run

From `rag_service/`:

```bash
python -m evaluation.cli
```

Or from workspace root:

```bash
python rag_service/evaluation/cli.py --repo-root rag_service
```
