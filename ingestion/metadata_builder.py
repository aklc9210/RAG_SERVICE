"""
Metadata builders for Pinecone vector records.

Dish metadata fields:
    entity_id, type="dish", doc_type, name_vi, name_en, name_normalized,
    category, source_file, ingredient_names_flat, audit_flags, text

Ingredient metadata fields:
    entity_id, type="ingredient", doc_type, name_vi, name_en, name_normalized,
    category, source_file, synonyms, synonyms_normalized, audit_flags, text

List fields are comma-joined strings to stay within Pinecone's metadata limits.
text is truncated to MAX_TEXT_LENGTH characters.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

MAX_TEXT_LENGTH = 4000  # characters; well within Pinecone's ~40 KB metadata limit


def _load_json(json_path: Path) -> Optional[Dict]:
    try:
        with open(json_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _flatten_list(lst: list) -> str:
    return ", ".join(str(x) for x in lst if x)


def build_dish_metadata(
    doc_path: Path,
    json_path: Path,
    text: str,
    doc_type: str,  # "a_identity" or "b_ingredients"
) -> Dict[str, Any]:
    """
    Build Pinecone metadata dict for a dish document.

    doc_path  — path to the .txt doc file
    json_path — path to the corresponding processed dish JSON
    text      — full document text
    doc_type  — "a_identity" or "b_ingredients"
    """
    data = _load_json(json_path) or {}
    stem = doc_path.stem  # e.g. "dish6674_a_identity"
    entity_id = data.get("id") or stem.rsplit("_", 2)[0]  # fallback: "dish6674"

    return {
        "entity_id": entity_id,
        "type": "dish",
        "doc_type": doc_type,
        "name_vi": data.get("name_vi", ""),
        "name_en": data.get("name_en", ""),
        "name_normalized": data.get("name_normalized", ""),
        "category": data.get("category", ""),
        "source_file": data.get("source_file", ""),
        "ingredient_names_flat": _flatten_list(data.get("ingredient_names_vi", [])),
        "audit_flags": _flatten_list(data.get("audit_flags", [])),
        "text": text[:MAX_TEXT_LENGTH],
    }


def build_ingredient_metadata(
    doc_path: Path,
    json_path: Path,
    text: str,
    doc_type: str = "ingredient_doc",
) -> Dict[str, Any]:
    """
    Build Pinecone metadata dict for an ingredient document.

    doc_path  — path to the .txt doc file
    json_path — path to the corresponding processed ingredient JSON
    text      — full document text
    doc_type  — always "ingredient_doc"
    """
    data = _load_json(json_path) or {}
    stem = doc_path.stem  # e.g. "ingre00006"
    entity_id = data.get("id", stem)

    return {
        "entity_id": entity_id,
        "type": "ingredient",
        "doc_type": doc_type,
        "name_vi": data.get("name_vi", ""),
        "name_en": data.get("name_en", ""),
        "name_normalized": data.get("name_normalized", ""),
        "category": data.get("category", ""),
        "source_file": data.get("source_file", ""),
        "synonyms": _flatten_list(data.get("synonyms", [])),
        "synonyms_normalized": _flatten_list(data.get("synonyms_normalized", [])),
        "audit_flags": _flatten_list(data.get("audit_flags", [])),
        "text": text[:MAX_TEXT_LENGTH],
    }
