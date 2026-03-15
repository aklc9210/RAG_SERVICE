"""
Query normalization utilities.

Rules applied (deterministic, no LLM):
1. Trim whitespace
2. Keep original form
3. Lower-case for the normalized variant
4. Strip Vietnamese diacritics → ASCII normalized form
5. Detect simple intent heuristics → suggested Pinecone filter
"""

import re
import unicodedata
from typing import Dict, Optional

# ---------------------------------------------------------------------------
# Accent stripping (Vietnamese → ASCII)
# ---------------------------------------------------------------------------

_VI_EXTRA = str.maketrans(
    "đĐ",
    "dD",
)


def strip_accents(text: str) -> str:
    """Convert Vietnamese text to no-accent ASCII form."""
    text = text.translate(_VI_EXTRA)
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# ---------------------------------------------------------------------------
# Intent heuristics
# ---------------------------------------------------------------------------

# Patterns that strongly suggest the user wants INGREDIENT info
_INGREDIENT_PATTERNS = [
    r"\blà gì\b",
    r"\bwhat is\b",
    r"\bnguyên liệu\b",
    r"\bnguyen lieu\b",
    r"\bnguyên liệu\s+\w",
    r"\bla gi\b",
    r"\btác dụng\b",
    r"\bcông dụng\b",
    r"\btac dung\b",
    r"\bcong dung\b",
    r"\bgia vị\b",
    r"\bgia vi\b",
]

# Patterns that strongly suggest the user wants DISH info
_DISH_PATTERNS = [
    r"\bmón nào\b",
    r"\bmon nao\b",
    r"\bdish with\b",
    r"\bcanh nào\b",
    r"\bcanh nao\b",
    r"\bnấu\b",
    r"\bnau\b",
    r"\bcách làm\b",
    r"\bcach lam\b",
    r"\bcông thức\b",
    r"\bcong thuc\b",
    r"\bthực đơn\b",
    r"\bthuc don\b",
    r"\bmón ăn\b",
    r"\bmon an\b",
]


def detect_intent(query: str) -> Optional[str]:
    """
    Return 'ingredient', 'dish', or None (search both).
    """
    q_lower = query.lower()
    q_norm = strip_accents(q_lower)

    for pattern in _INGREDIENT_PATTERNS:
        if re.search(pattern, q_lower) or re.search(pattern, q_norm):
            return "ingredient"

    for pattern in _DISH_PATTERNS:
        if re.search(pattern, q_lower) or re.search(pattern, q_norm):
            return "dish"

    return None


# ---------------------------------------------------------------------------
# Main normalizer
# ---------------------------------------------------------------------------


def normalize_query(query: str) -> Dict[str, str]:
    """
    Normalize a user query and return a dict with:
        original        — raw user input
        cleaned         — trimmed original
        lowercased      — lowercase form of cleaned
        normalized      — no-accent lowercase (best for Pinecone filter matching)
        intent          — 'dish' | 'ingredient' | None
    """
    original = query
    cleaned = query.strip()
    lowercased = cleaned.lower()
    normalized = strip_accents(lowercased)
    intent = detect_intent(cleaned)

    return {
        "original": original,
        "cleaned": cleaned,
        "lowercased": lowercased,
        "normalized": normalized,
        "intent": intent,
    }
