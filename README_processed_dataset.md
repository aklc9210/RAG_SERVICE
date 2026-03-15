# RAG Dataset Processing

This workspace includes a processing script to transform raw recipe entity JSON into cleaned structured files and retrieval-friendly text documents.

## Script

- `build_rag_documents.py`

## How to run

```bash
python build_rag_documents.py
```

The script reads from:

- `kb_old/dishes`
- `kb_old/ingredients`

And writes to:

- `processed/dishes` (cleaned dish JSON)
- `processed/ingredients` (cleaned ingredient JSON)
- `processed/docs/dishes` (dish retrieval docs)
- `processed/docs/ingredients` (ingredient retrieval docs)
- `processed/reports` (audit reports)
- `processed/audit_reports` (same audit reports for compatibility)

## Output behavior

- Raw files are never overwritten.
- Malformed JSON files are skipped and logged in reports.
- Unicode and whitespace are normalized.
- `name_normalized` is rebuilt deterministically from Vietnamese names.
- Duplicate synonyms and ingredient names are deduplicated.

## Automatic corrections vs manual review

Automatic corrections are only applied when confidence is high (or medium with clear signals), including:

- Deterministic normalization mismatch (`name_normalized`)
- Known high-confidence Vietnamese-English mappings (for common culinary terms)
- Clearly impossible mappings from known error patterns

Manual review is flagged when confidence is limited, including:

- Conflicting English values for the same Vietnamese name across dataset
- Translation ambiguity not safely resolvable by rules

Such cases are recorded in:

- `processed/reports/uncertain_cases.json`
- `processed/reports/corrected_fields.json`
- `processed/reports/missing_required_fields.json`
- `processed/reports/dataset_summary.md`

## Final console summary

After completion, the script prints:

- total files processed
- total documents generated
- total corrections made
- total uncertain cases flagged
