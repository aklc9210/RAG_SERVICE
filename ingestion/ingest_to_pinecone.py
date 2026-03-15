#!/usr/bin/env python3
"""
Pinecone embedding + ingestion pipeline for Vietnamese food RAG service.

Usage:
    python ingestion/ingest_to_pinecone.py                     # full ingest
    python ingestion/ingest_to_pinecone.py --dry-run           # embed but do not upsert
    python ingestion/ingest_to_pinecone.py --limit 100         # process first 100 docs only
    python ingestion/ingest_to_pinecone.py --sample-test-only  # 5 docs of each type, print preview

Output reports written to processed/reports/:
    ingestion_summary.json
    failed_ingestion.json
    pinecone_preview.json  (first 10 records, no embedding values)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DOCS_DISHES = WORKSPACE_ROOT / "processed" / "docs" / "dishes"
PROCESSED_DOCS_INGREDIENTS = WORKSPACE_ROOT / "processed" / "docs" / "ingredients"
PROCESSED_JSON_DISHES = WORKSPACE_ROOT / "processed" / "dishes"
PROCESSED_JSON_INGREDIENTS = WORKSPACE_ROOT / "processed" / "ingredients"
REPORTS_DIR = WORKSPACE_ROOT / "processed" / "reports"


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Embed processed docs and upsert to Pinecone."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Embed and build metadata but do not upsert to Pinecone.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit total number of docs to process (across all types).",
    )
    parser.add_argument(
        "--sample-test-only",
        action="store_true",
        help=(
            "Process 5 docs of each sub-type (a_identity, b_ingredients, ingredient_doc) "
            "and write preview; does not upsert to Pinecone."
        ),
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Document discovery
# ---------------------------------------------------------------------------


def discover_dish_docs() -> List[Tuple[Path, Path, str]]:
    """
    Discover all dish doc files.
    Returns list of (doc_path, json_path, doc_type) tuples,
    sorted by entity_id, with a_identity docs before b_ingredients.
    """
    results = []
    for doc_path in sorted(PROCESSED_DOCS_DISHES.glob("dish*_a_identity.txt")):
        entity_id = doc_path.stem.replace("_a_identity", "")
        json_path = PROCESSED_JSON_DISHES / f"{entity_id}.json"
        results.append((doc_path, json_path, "a_identity"))
    for doc_path in sorted(PROCESSED_DOCS_DISHES.glob("dish*_b_ingredients.txt")):
        entity_id = doc_path.stem.replace("_b_ingredients", "")
        json_path = PROCESSED_JSON_DISHES / f"{entity_id}.json"
        results.append((doc_path, json_path, "b_ingredients"))
    return results


def discover_ingredient_docs() -> List[Tuple[Path, Path, str]]:
    """
    Discover all ingredient doc files.
    Returns list of (doc_path, json_path, doc_type) tuples.
    """
    results = []
    for doc_path in sorted(PROCESSED_DOCS_INGREDIENTS.glob("ingre*.txt")):
        entity_id = doc_path.stem  # e.g. "ingre00006"
        json_path = PROCESSED_JSON_INGREDIENTS / f"{entity_id}.json"
        results.append((doc_path, json_path, "ingredient_doc"))
    return results


# ---------------------------------------------------------------------------
# Record building
# ---------------------------------------------------------------------------


def load_text(doc_path: Path) -> str:
    with open(doc_path, encoding="utf-8") as f:
        return f.read().strip()


def build_all_records(
    docs: List[Tuple[Path, Path, str]],
) -> Tuple[List[Dict], List[Dict]]:
    """
    Read each doc file and build a record dict.

    Returns:
        records  — list of {"id": str, "text": str, "metadata": dict}
        failures — list of {"doc": str, "error": str}
    """
    from ingestion.metadata_builder import build_dish_metadata, build_ingredient_metadata

    records: List[Dict] = []
    failures: List[Dict] = []

    for doc_path, json_path, doc_type in docs:
        try:
            text = load_text(doc_path)
            if not text:
                failures.append({"doc": str(doc_path), "error": "Empty document"})
                continue

            vector_id = doc_path.stem  # e.g. "dish6674_a_identity" or "ingre00006"

            if doc_path.stem.startswith("dish"):
                metadata = build_dish_metadata(doc_path, json_path, text, doc_type)
            else:
                metadata = build_ingredient_metadata(doc_path, json_path, text, doc_type)

            records.append({"id": vector_id, "text": text, "metadata": metadata})

        except Exception as e:
            failures.append({"doc": str(doc_path), "error": str(e)})

    return records, failures


# ---------------------------------------------------------------------------
# Embedding + upsert
# ---------------------------------------------------------------------------


def embed_and_upsert(
    records: List[Dict],
    embedding_model,
    pinecone_client,
    batch_size: int,
    dry_run: bool,
) -> Tuple[int, int, List[Dict]]:
    """
    Embed records in batches and optionally upsert to Pinecone.

    Returns:
        success_count  — number of vectors successfully processed
        failure_count  — number of vectors that failed
        failed_list    — list of {"doc": str, "error": str}
    """
    success = 0
    failure_count = 0
    failed: List[Dict] = []

    total_batches = (len(records) + batch_size - 1) // batch_size

    for batch_idx, i in enumerate(range(0, len(records), batch_size)):
        batch_records = records[i : i + batch_size]
        batch_texts = [r["text"] for r in batch_records]

        print(f"  Batch {batch_idx + 1}/{total_batches}: embedding {len(batch_records)} docs...", end="", flush=True)

        try:
            embeddings = embedding_model.embed_documents(batch_texts)
        except Exception as e:
            print(f" FAILED (embedding): {e}")
            for r in batch_records:
                failed.append({"doc": r["id"], "error": f"Embedding failed: {e}"})
                failure_count += 1
            continue

        vectors = [
            {"id": r["id"], "values": emb, "metadata": r["metadata"]}
            for r, emb in zip(batch_records, embeddings)
        ]

        if dry_run:
            success += len(vectors)
            print(f" [dry-run] OK")
        else:
            try:
                pinecone_client.upsert_batch(vectors)
                success += len(vectors)
                print(f" upserted OK")
            except Exception as e:
                print(f" FAILED (upsert): {e}")
                for v in vectors:
                    failed.append({"doc": v["id"], "error": f"Upsert failed: {e}"})
                    failure_count += 1

    return success, failure_count, failed


# ---------------------------------------------------------------------------
# Report writing
# ---------------------------------------------------------------------------


def write_reports(
    summary: Dict,
    failed: List[Dict],
    preview: List[Dict],
) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    with open(REPORTS_DIR / "ingestion_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nWrote: processed/reports/ingestion_summary.json")

    with open(REPORTS_DIR / "failed_ingestion.json", "w", encoding="utf-8") as f:
        json.dump(failed, f, ensure_ascii=False, indent=2)
    print(f"Wrote: processed/reports/failed_ingestion.json  ({len(failed)} failures)")

    with open(REPORTS_DIR / "pinecone_preview.json", "w", encoding="utf-8") as f:
        json.dump(preview, f, ensure_ascii=False, indent=2)
    print(f"Wrote: processed/reports/pinecone_preview.json  ({len(preview)} sample records)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    args = parse_args()

    # --sample-test-only always runs in dry-run mode (no upsert to Pinecone)
    dry_run: bool = args.dry_run or args.sample_test_only

    print("=== Pinecone Ingestion Pipeline ===")
    if args.sample_test_only:
        mode_label = "sample-test-only (dry-run, 5 per sub-type)"
    elif dry_run:
        mode_label = "dry-run (embed only, no upsert)"
    else:
        mode_label = "full-ingest"
    print(f"Mode  : {mode_label}")
    print(f"Limit : {args.limit if args.limit else 'none'}")

    # --- Discover docs ---
    print("\nDiscovering documents...")
    dish_docs = discover_dish_docs()
    ingredient_docs = discover_ingredient_docs()
    print(
        f"  Dish docs     : {len(dish_docs)} "
        f"({len([d for d in dish_docs if d[2]=='a_identity'])} identity + "
        f"{len([d for d in dish_docs if d[2]=='b_ingredients'])} ingredients)"
    )
    print(f"  Ingredient docs: {len(ingredient_docs)}")

    # --- Select docs ---
    if args.sample_test_only:
        a_docs = [d for d in dish_docs if d[2] == "a_identity"][:5]
        b_docs = [d for d in dish_docs if d[2] == "b_ingredients"][:5]
        ingre_docs = ingredient_docs[:5]
        all_docs = a_docs + b_docs + ingre_docs
    else:
        all_docs = dish_docs + ingredient_docs

    if args.limit is not None:
        all_docs = all_docs[: args.limit]

    n_dish = sum(1 for d in all_docs if d[0].stem.startswith("dish"))
    n_ingre = sum(1 for d in all_docs if d[0].stem.startswith("ingre"))
    print(f"\nTotal docs selected: {len(all_docs)}  (dish: {n_dish}, ingredient: {n_ingre})")

    if not all_docs:
        print("No documents found. Exiting.")
        sys.exit(0)

    # --- Build records ---
    print("\nBuilding records and loading metadata...")
    records, build_failures = build_all_records(all_docs)
    print(f"  Records built   : {len(records)}")
    print(f"  Build failures  : {len(build_failures)}")

    # --- Load embedding model ---
    print("\nLoading embedding model...")
    from ingestion.embedding import EmbeddingModel

    embedding_model = EmbeddingModel()
    dim = embedding_model.get_dimension()
    print(f"  Model     : {embedding_model.model_name}")
    print(f"  Dimension : {dim}")

    # --- Connect to Pinecone (unless dry-run) ---
    pinecone_client = None
    if not dry_run:
        print("\nConnecting to Pinecone...")
        from ingestion.pinecone_utils import PineconeClient

        pinecone_client = PineconeClient()
        stats = pinecone_client.describe_index_stats()
        print(f"  Index     : {pinecone_client.index_name}")
        print(f"  Stats     : {stats}")

    # --- Embed + upsert ---
    batch_size = int(os.getenv("BATCH_SIZE", "32"))
    action = "upserting" if not dry_run else "previewing (dry-run)"
    print(f"\nEmbedding and {action} (batch_size={batch_size})...")
    success, fail_count, upsert_failures = embed_and_upsert(
        records, embedding_model, pinecone_client, batch_size, dry_run
    )

    all_failures = build_failures + upsert_failures

    # --- Build preview (no embedding values stored) ---
    preview_records = [
        {
            "id": r["id"],
            "metadata": r["metadata"],
            "text_snippet": r["text"][:300],
        }
        for r in records[:10]
    ]

    # --- Summary ---
    summary = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": mode_label,
        "limit": args.limit,
        "total_docs_discovered": len(dish_docs) + len(ingredient_docs),
        "total_docs_selected": len(all_docs),
        "records_built": len(records),
        "build_failures": len(build_failures),
        "vectors_upserted": success if not dry_run else 0,
        "vectors_dry_run_processed": success if dry_run else 0,
        "upsert_failures": fail_count,
        "total_failures": len(all_failures),
        "embedding_model": embedding_model.model_name,
        "embedding_dimension": dim,
        "dry_run": dry_run,
    }

    print(f"\n=== Run Summary ===")
    print(f"  Records built           : {summary['records_built']}")
    if dry_run:
        print(f"  Vectors processed (dry) : {summary['vectors_dry_run_processed']}")
    else:
        print(f"  Vectors upserted        : {summary['vectors_upserted']}")
    print(f"  Total failures          : {summary['total_failures']}")

    write_reports(summary, all_failures, preview_records)
    print("\nDone.")


if __name__ == "__main__":
    main()
