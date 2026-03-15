"""
CLI entry point for the retrieval stage.

Usage examples
--------------
python -m retrieval.retrieve_from_pinecone --query "món canh nào có me và cà chua"
python -m retrieval.retrieve_from_pinecone --query "me là gì" --type ingredient
python -m retrieval.retrieve_from_pinecone --query "ba chỉ bò" --top-k 10
python -m retrieval.retrieve_from_pinecone --query "món có sả" --group-results true
python -m retrieval.retrieve_from_pinecone --test-mode
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Ensure project root is importable when running as a module
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ingestion.embedding import EmbeddingModel
from pinecone import Pinecone

from retrieval.query_normalizer import normalize_query
from retrieval.result_formatter import build_report, format_flat, format_grouped
from retrieval.retriever import Retriever

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPORT_PATH = _ROOT / "processed" / "reports" / "retrieval_preview.json"

TEST_QUERIES = [
    "món canh nào có me và cà chua",
    "hành tím là gì",
    "món nào có sả",
    "ba chỉ bò",
    "nguyên liệu rau răm",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bool_arg(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "y"}


def _connect(index_name: str) -> Any:
    """Return an authenticated Pinecone Index object."""
    api_key = os.environ.get("PINECONE_API_KEY")
    if not api_key:
        raise EnvironmentError("PINECONE_API_KEY is not set in the environment.")
    pc = Pinecone(api_key=api_key)
    return pc.Index(index_name)


def _save_report(report: Dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(f"\n[report] Saved → {REPORT_PATH}")


# ---------------------------------------------------------------------------
# Core run logic
# ---------------------------------------------------------------------------


def run_query(
    retriever: Retriever,
    query: str,
    top_k: int = 10,
    type_filter: Optional[str] = None,
    category_filter: Optional[str] = None,
    group_results: bool = False,
) -> Dict[str, Any]:
    """
    Normalise query, select retrieval mode, return a report dict.
    Prints formatted results to stdout.
    """
    query_info = normalize_query(query)

    # If caller hasn't forced a type, use intent detection
    effective_type = type_filter or query_info["intent"]  # type: ignore[assignment]

    raw_matches: List[Dict[str, Any]] = []
    grouped_matches: Optional[List[Dict[str, Any]]] = None

    if group_results:
        grouped_matches = retriever.search_grouped(
            query_info["cleaned"], top_k=top_k, type_filter=effective_type
        )
        # Also fetch raw matches for the report
        raw_matches = retriever.search_filtered(
            query_info["cleaned"],
            top_k=top_k * 4,
            type_filter=effective_type,
            category_filter=category_filter,
        )
        print(format_grouped(grouped_matches, query_info))
    else:
        raw_matches = retriever.search_filtered(
            query_info["cleaned"],
            top_k=top_k,
            type_filter=effective_type,
            category_filter=category_filter,
        )
        print(format_flat(raw_matches, query_info))

    filters = {"type": effective_type, "category": category_filter}
    return build_report(
        query_info=query_info,
        raw_matches=raw_matches,
        grouped_matches=grouped_matches,
        filters=filters,
        top_k=top_k,
        grouped=group_results,
    )


def run_test_mode(retriever: Retriever, top_k: int = 10) -> None:
    """Run all TEST_QUERIES, print results, save combined report."""
    all_reports: List[Dict[str, Any]] = []
    for q in TEST_QUERIES:
        print(f"\n{'='*60}")
        print(f"TEST QUERY: {q}")
        print(f"{'='*60}")
        report = run_query(retriever, q, top_k=top_k, group_results=True)
        all_reports.append(report)

    _save_report({"mode": "test", "queries": all_reports})


# ---------------------------------------------------------------------------
# Argument parsing & main
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m retrieval.retrieve_from_pinecone",
        description="Query the Vietnamese food RAG Pinecone index.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--query", "-q", type=str, help="Query text (Vietnamese or English).")
    parser.add_argument(
        "--type",
        "-t",
        choices=["dish", "ingredient"],
        default=None,
        help="Filter by entity type. If omitted, intent detection is used.",
    )
    parser.add_argument(
        "--category",
        "-c",
        type=str,
        default=None,
        help="Filter by category metadata field.",
    )
    parser.add_argument(
        "--top-k",
        "-k",
        type=int,
        default=10,
        dest="top_k",
        help="Number of results to return (default: 10).",
    )
    parser.add_argument(
        "--group-results",
        "-g",
        type=_bool_arg,
        default=False,
        metavar="true|false",
        dest="group_results",
        help="Group results by entity_id (default: false).",
    )
    parser.add_argument(
        "--test-mode",
        action="store_true",
        dest="test_mode",
        help="Run preset test queries and save a preview report.",
    )
    parser.add_argument(
        "--index",
        type=str,
        default="vn-food-rag",
        help="Pinecone index name (default: vn-food-rag).",
    )
    return parser


def main() -> None:
    load_dotenv()

    parser = _build_parser()
    args = parser.parse_args()

    if not args.test_mode and not args.query:
        parser.error("Either --query or --test-mode is required.")

    print("[init] Loading embedding model…")
    embed_model = EmbeddingModel()
    print(f"[init] Embedding model ready (dim={embed_model.get_dimension()})")

    print(f"[init] Connecting to Pinecone index '{args.index}'…")
    index = _connect(args.index)
    print("[init] Connected.")

    retriever = Retriever(embed_model, index)

    if args.test_mode:
        run_test_mode(retriever, top_k=args.top_k)
    else:
        report = run_query(
            retriever,
            query=args.query,
            top_k=args.top_k,
            type_filter=args.type,
            category_filter=args.category,
            group_results=args.group_results,
        )
        _save_report(report)


if __name__ == "__main__":
    main()
