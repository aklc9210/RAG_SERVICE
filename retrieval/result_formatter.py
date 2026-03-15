"""
Result formatting utilities for the retrieval stage.

Provides:
- format_flat()    : human-readable console output for flat matches
- format_grouped() : human-readable console output for grouped matches
- build_report()   : serialisable dict for JSON export
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Console formatters
# ---------------------------------------------------------------------------

_SEP = "-" * 60


def format_flat(matches: List[Dict[str, Any]], query_info: Dict[str, str]) -> str:
    """Format a flat list of Pinecone match dicts for console output."""
    lines: List[str] = []
    lines.append(_SEP)
    lines.append(f"Query : {query_info.get('cleaned', '')}")
    lines.append(f"Intent: {query_info.get('intent') or 'both'}")
    lines.append(f"Hits  : {len(matches)}")
    lines.append(_SEP)

    for i, m in enumerate(matches, 1):
        lines.append(
            f"{i:>3}. [{m.get('type', '?'):10s}] {m.get('name_vi', m.get('id', ''))}"
        )
        lines.append(
            f"       id={m.get('id', '')}  score={m.get('score', 0):.4f}"
        )
        lines.append(
            f"       doc_type={m.get('doc_type', '')}  category={m.get('category', '')}"
        )
        text_preview = (m.get("text") or "")[:120].replace("\n", " ")
        if text_preview:
            lines.append(f"       text: {text_preview}…")
        lines.append("")

    return "\n".join(lines)


def format_grouped(
    groups: List[Dict[str, Any]], query_info: Dict[str, str]
) -> str:
    """Format a grouped result list (output of search_grouped) for console output."""
    lines: List[str] = []
    lines.append(_SEP)
    lines.append(f"Query : {query_info.get('cleaned', '')}")
    lines.append(f"Intent: {query_info.get('intent') or 'both'}")
    lines.append(f"Entities returned: {len(groups)}")
    lines.append(_SEP)

    for i, g in enumerate(groups, 1):
        lines.append(
            f"{i:>3}. entity_id : {g.get('entity_id', '')}"
        )
        lines.append(f"       type      : {g.get('type', '')}")
        lines.append(f"       name_vi   : {g.get('name_vi', '')}")
        name_en = g.get("name_en", "")
        if name_en:
            lines.append(f"       name_en   : {name_en}")
        lines.append(f"       category  : {g.get('category', '')}")
        lines.append(f"       best_score: {g.get('best_score', 0):.4f}")
        lines.append(f"       matched_docs ({len(g.get('matched_docs', []))}):")
        for doc in g.get("matched_docs", []):
            text_preview = (doc.get("text") or "")[:100].replace("\n", " ")
            lines.append(
                f"         - doc_type={doc.get('doc_type', '')}  score={doc.get('score', 0):.4f}"
            )
            if text_preview:
                lines.append(f"           text: {text_preview}…")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON report builder
# ---------------------------------------------------------------------------


def build_report(
    query_info: Dict[str, str],
    raw_matches: List[Dict[str, Any]],
    grouped_matches: Optional[List[Dict[str, Any]]],
    filters: Dict[str, Optional[str]],
    top_k: int,
    grouped: bool,
) -> Dict[str, Any]:
    """Build a serialisable report dict for writing to retrieval_preview.json."""
    return {
        "query": query_info,
        "settings": {
            "top_k": top_k,
            "grouped": grouped,
            "type_filter": filters.get("type"),
            "category_filter": filters.get("category"),
        },
        "raw_matches_count": len(raw_matches),
        "raw_matches": raw_matches,
        "grouped_count": len(grouped_matches) if grouped_matches is not None else None,
        "grouped_matches": grouped_matches,
    }
