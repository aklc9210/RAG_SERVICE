#!/usr/bin/env python3
"""Build cleaned RAG documents from raw dish/ingredient JSON files.

This script:
- Reads raw JSON files from kb_old/dishes and kb_old/ingredients
- Normalizes text and structural fields
- Audits bilingual Vietnamese-English names with conservative corrections
- Generates cleaned JSON outputs and retrieval-friendly text docs
- Writes audit reports and a concise processing summary
"""

from __future__ import annotations

import json
import re
import unicodedata
import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
RAW_ROOT = ROOT / "kb_old"
RAW_DISH_DIR = RAW_ROOT / "dishes"
RAW_INGREDIENT_DIR = RAW_ROOT / "ingredients"

PROCESSED_ROOT = ROOT / "processed"
OUT_DISH_DIR = PROCESSED_ROOT / "dishes"
OUT_INGREDIENT_DIR = PROCESSED_ROOT / "ingredients"
OUT_DOC_DISH_DIR = PROCESSED_ROOT / "docs" / "dishes"
OUT_DOC_INGREDIENT_DIR = PROCESSED_ROOT / "docs" / "ingredients"
OUT_REPORT_DIR = PROCESSED_ROOT / "reports"
OUT_AUDIT_REPORT_DIR = PROCESSED_ROOT / "audit_reports"

# High-confidence corrections where Vietnamese meaning is clear and stable.
KNOWN_VI_TO_EN: Dict[str, str] = {
    "me": "Tamarind",
    "hanh tim": "Shallot",
    "hanh la": "Scallion",
    "thi la": "Dill",
    "ngo gai": "Culantro",
    "rau ngo": "Culantro",
    "rau ram": "Vietnamese coriander",
    "kho qua": "Bitter melon",
    "muop huong": "Luffa",
    "khop qua": "Bitter melon",
    "ngheu": "Clam",
    "so diep": "Scallop",
    "he": "Garlic chives",
    "chan gio truoc": "Front pork hock",
    "chan gio": "Pork hock",
}

SEASONING_KEYWORDS = {
    "muoi", "duong", "hat nem", "nuoc mam", "nuoc tuong", "tuong", "tieu", "ot",
    "giam", "chanh", "dau an", "bot ngot", "msg", "sa te", "tuong ot", "toi",
    "hanh kho", "hanh phi", "ruou", "ngu vi huong", "dau hao", "mam ruoc",
}

MISSING_MARKERS = {"", "null", "none", "n/a", "na", "unknown", "khong ro", "-"}

VI_SPECIAL_CHAR_MAP = str.maketrans({
    "đ": "d",
    "Đ": "D",
})


@dataclass
class LoadedRecord:
    path: Path
    raw: Optional[Dict[str, Any]]
    file_type: str  # dish | ingredient | unknown
    error: Optional[str] = None


def ensure_dirs() -> None:
    for d in [
        OUT_DISH_DIR,
        OUT_INGREDIENT_DIR,
        OUT_DOC_DISH_DIR,
        OUT_DOC_INGREDIENT_DIR,
        OUT_REPORT_DIR,
        OUT_AUDIT_REPORT_DIR,
    ]:
        d.mkdir(parents=True, exist_ok=True)


def normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = normalize_unicode(str(value))
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r",\s*,+", ", ", text)
    return text.strip(" ,;")


def to_none_if_missing(text: str) -> str:
    lowered = text.strip().lower()
    if lowered in MISSING_MARKERS:
        return ""
    return text


def strip_accents(text: str) -> str:
    # Map Vietnamese special letters before removing combining marks.
    protected = text.translate(VI_SPECIAL_CHAR_MAP)
    decomposed = unicodedata.normalize("NFD", protected)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", stripped)


def build_name_normalized(name_vi: str) -> str:
    if not name_vi:
        return ""
    text = strip_accents(name_vi).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_list(values: Any) -> List[str]:
    if values is None:
        return []
    if isinstance(values, str):
        raw = re.split(r"[,;/|]", values)
    elif isinstance(values, list):
        raw = []
        for item in values:
            if isinstance(item, str):
                raw.extend(re.split(r"[,;/|]", item))
            elif item is not None:
                raw.append(str(item))
    else:
        raw = [str(values)]

    seen = set()
    out: List[str] = []
    for item in raw:
        cleaned = to_none_if_missing(clean_text(item))
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
    return out


def normalize_name_list(values: Any) -> List[str]:
    return dedupe_preserve_order([build_name_normalized(v) for v in normalize_list(values) if build_name_normalized(v)])


def safe_json_load(path: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None, "JSON root is not an object"
        return data, None
    except Exception as exc:  # pylint: disable=broad-except
        return None, f"Malformed JSON: {exc}"


def detect_type(path: Path, data: Optional[Dict[str, Any]]) -> str:
    if data:
        raw_type = clean_text(data.get("type", "")).lower()
        if raw_type in {"dish", "ingredient"}:
            return raw_type
        if "ingredients" in data and isinstance(data.get("ingredients"), list):
            return "dish"
        if "synonyms" in data or str(path.name).startswith("ingre"):
            return "ingredient"
    if path.parent.name.lower() == "dishes":
        return "dish"
    if path.parent.name.lower() == "ingredients":
        return "ingredient"
    return "unknown"


def get_name_fields(data: Dict[str, Any]) -> Tuple[str, str, str]:
    name_vi = to_none_if_missing(clean_text(data.get("name_vi", "")))
    name_en = to_none_if_missing(clean_text(data.get("name_en", "")))
    name_norm = to_none_if_missing(clean_text(data.get("name_normalized", "")))
    return name_vi, name_en, name_norm


def get_category(data: Dict[str, Any]) -> str:
    category = to_none_if_missing(clean_text(data.get("category", "")))
    if not category:
        category = to_none_if_missing(clean_text(data.get("category_id", "")))
    return category


def correction_entry(field: str, old: Any, new: Any, confidence: str, reason: str) -> Dict[str, Any]:
    return {
        "field": field,
        "old": old,
        "new": new,
        "confidence": confidence,
        "reason": reason,
    }


def audit_name_pair(
    name_vi: str,
    name_en: str,
    name_normalized: str,
    canonical_en_hint: str,
) -> Tuple[str, str, List[str], List[Dict[str, Any]], List[str]]:
    flags: List[str] = []
    corrections: List[Dict[str, Any]] = []
    uncertain_notes: List[str] = []

    vi_norm = build_name_normalized(name_vi)

    if name_normalized != vi_norm and vi_norm:
        corrections.append(
            correction_entry(
                "name_normalized",
                name_normalized,
                vi_norm,
                "high",
                "Normalized name must be deterministic from Vietnamese name.",
            )
        )
        name_normalized = vi_norm

    en_clean = clean_text(name_en)
    if "->" in en_clean:
        flags.append("needs_manual_review_translation")
        uncertain_notes.append(
            "English name contains '->' transformation marker; kept original due to non-high confidence."
        )

    known = KNOWN_VI_TO_EN.get(vi_norm)
    if known and en_clean and en_clean.lower() != known.lower():
        corrections.append(
            correction_entry(
                "name_en",
                name_en,
                known,
                "high",
                "High-confidence Vietnamese-English culinary mapping.",
            )
        )
        en_clean = known

    if known and not en_clean:
        corrections.append(
            correction_entry(
                "name_en",
                name_en,
                known,
                "high",
                "Missing English name filled from high-confidence mapping.",
            )
        )
        en_clean = known

    if canonical_en_hint and en_clean and canonical_en_hint.lower() != en_clean.lower():
        flags.append("needs_manual_review_translation")
        uncertain_notes.append(
            f"English variant '{en_clean}' differs from common mapping '{canonical_en_hint}'."
        )

    # Heuristic impossible mappings from examples.
    if vi_norm == "me" and en_clean.lower() == "mouse":
        corrections.append(
            correction_entry(
                "name_en",
                name_en,
                "Tamarind",
                "high",
                "Vietnamese 'Me' indicates tamarind; 'Mouse' is semantically impossible.",
            )
        )
        en_clean = "Tamarind"

    if vi_norm == "hanh tim" and en_clean.lower() == "green onion":
        corrections.append(
            correction_entry(
                "name_en",
                name_en,
                "Shallot",
                "high",
                "Vietnamese 'Hanh tim' corresponds to shallot, not green onion.",
            )
        )
        en_clean = "Shallot"

    if vi_norm == "sa" and en_clean.lower() == "garlic chili":
        corrections.append(
            correction_entry(
                "name_en",
                name_en,
                "Lemongrass",
                "high",
                "Vietnamese 'Sa' corresponds to lemongrass.",
            )
        )
        en_clean = "Lemongrass"

    if vi_norm == "chan gio truoc" and en_clean.lower() == "pork belly":
        corrections.append(
            correction_entry(
                "name_en",
                name_en,
                "Front pork hock",
                "high",
                "Vietnamese 'Chan gio truoc' is a pork hock cut, not pork belly.",
            )
        )
        en_clean = "Front pork hock"

    if not en_clean:
        flags.append("missing_name_en")

    return en_clean, name_normalized, flags, corrections, uncertain_notes


def canonical_en_from_counter(counter: Counter) -> str:
    if not counter:
        return ""
    return counter.most_common(1)[0][0]


def ingredient_doc(cleaned: Dict[str, Any]) -> str:
    lines = [
        "Loai: nguyen lieu",
        f"Ten nguyen lieu: {cleaned.get('name_vi', '')}",
    ]
    if cleaned.get("name_en"):
        lines.append(f"Ten tieng Anh: {cleaned['name_en']}")
    if cleaned.get("name_normalized"):
        lines.append(f"Ten chuan hoa: {cleaned['name_normalized']}")
    if cleaned.get("synonyms"):
        lines.append(f"Tu dong nghia: {', '.join(cleaned['synonyms'])}")
    if cleaned.get("category"):
        lines.append(f"Danh muc: {cleaned['category']}")
    return "\n".join(line for line in lines if line and not line.endswith(": "))


def dish_doc_identity(cleaned: Dict[str, Any]) -> str:
    lines = [
        "Loai: mon an",
        f"Ten mon: {cleaned.get('name_vi', '')}",
    ]
    if cleaned.get("name_en"):
        lines.append(f"Ten tieng Anh: {cleaned['name_en']}")
    if cleaned.get("name_normalized"):
        lines.append(f"Ten chuan hoa: {cleaned['name_normalized']}")
    if cleaned.get("category"):
        lines.append(f"Danh muc: {cleaned['category']}")
    return "\n".join(line for line in lines if line and not line.endswith(": "))


def dish_doc_ingredients(cleaned: Dict[str, Any]) -> str:
    lines = [f"Mon: {cleaned.get('name_vi', '')}"]
    main = cleaned.get("main_ingredients", [])
    sec = cleaned.get("secondary_ingredients", [])
    season = cleaned.get("seasonings", [])

    if cleaned.get("grouping_mode") == "combined" and main:
        lines.append(f"Nguyen lieu: {', '.join(main)}")
    else:
        if main:
            lines.append(f"Nguyen lieu chinh: {', '.join(main)}")
        if sec:
            lines.append(f"Nguyen lieu phu: {', '.join(sec)}")
    if season:
        lines.append(f"Gia vi: {', '.join(season)}")
    return "\n".join(lines)


def is_seasoning(name_norm: str, category: str) -> bool:
    if category.lower() == "seasonings":
        return True
    return any(keyword in name_norm for keyword in SEASONING_KEYWORDS)


def dedupe_preserve_order(items: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items:
        key = item.lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def process() -> Dict[str, Any]:
    ensure_dirs()

    dish_paths = sorted(RAW_DISH_DIR.glob("*.json"))
    ingredient_paths = sorted(RAW_INGREDIENT_DIR.glob("*.json"))
    all_paths = dish_paths + ingredient_paths

    files_processed: List[Dict[str, Any]] = []
    corrected_fields: List[Dict[str, Any]] = []
    uncertain_cases: List[Dict[str, Any]] = []
    missing_required: List[Dict[str, Any]] = []

    normalization_errors_fixed = 0
    high_confidence_english_corrections = 0

    # First pass: load all files and build Vietnamese->English frequency hints.
    vi_to_en_counter: Dict[str, Counter] = defaultdict(Counter)
    loaded: List[LoadedRecord] = []

    for path in all_paths:
        raw, err = safe_json_load(path)
        file_type = detect_type(path, raw)
        loaded.append(LoadedRecord(path=path, raw=raw, file_type=file_type, error=err))

        if err:
            files_processed.append(
                {
                    "source_file": str(path.relative_to(ROOT)).replace("\\", "/"),
                    "status": "error",
                    "error": err,
                }
            )
            continue

        if raw is None:
            continue

        name_vi, name_en, _ = get_name_fields(raw)
        vi_norm = build_name_normalized(name_vi)
        if vi_norm and name_en:
            vi_to_en_counter[vi_norm][name_en] += 1

        if file_type == "dish":
            for ing in raw.get("ingredients", []):
                if not isinstance(ing, dict):
                    continue
                ing_vi = to_none_if_missing(clean_text(ing.get("name_vi", "")))
                ing_en = to_none_if_missing(clean_text(ing.get("name_en", "")))
                ing_vi_norm = build_name_normalized(ing_vi)
                if ing_vi_norm and ing_en:
                    vi_to_en_counter[ing_vi_norm][ing_en] += 1

    doc_count = 0

    for item in loaded:
        rel_source = str(item.path.relative_to(ROOT)).replace("\\", "/")
        if item.error or not item.raw:
            continue

        raw = item.raw
        file_type = item.file_type
        name_vi, name_en, name_norm_raw = get_name_fields(raw)
        canonical_hint = canonical_en_from_counter(vi_to_en_counter[build_name_normalized(name_vi)])

        audit_flags: List[str] = []
        correction_log: List[Dict[str, Any]] = []

        name_en_clean, name_norm_clean, pair_flags, pair_corrections, uncertain_notes = audit_name_pair(
            name_vi=name_vi,
            name_en=name_en,
            name_normalized=name_norm_raw,
            canonical_en_hint=canonical_hint,
        )
        audit_flags.extend(pair_flags)
        correction_log.extend(pair_corrections)

        for note in uncertain_notes:
            uncertain_cases.append(
                {
                    "source_file": rel_source,
                    "field": "name_en",
                    "name_vi": name_vi,
                    "current_value": name_en,
                    "note": note,
                }
            )

        category = get_category(raw)
        record_id = to_none_if_missing(clean_text(raw.get("id", "")))

        if not record_id:
            missing_required.append(
                {
                    "source_file": rel_source,
                    "missing_fields": ["id"],
                }
            )
            record_id = item.path.stem

        if not name_vi:
            audit_flags.append("missing_name_vi")
            missing_required.append(
                {
                    "source_file": rel_source,
                    "missing_fields": ["name_vi"],
                }
            )

        if file_type == "ingredient":
            synonyms = normalize_list(raw.get("synonyms", []))
            synonyms_normalized = normalize_name_list(synonyms)

            cleaned = {
                "id": record_id,
                "type": "ingredient",
                "source_file": rel_source,
                "name_vi": name_vi,
                "name_en": name_en_clean,
                "name_normalized": name_norm_clean,
                "synonyms": synonyms,
                "synonyms_normalized": synonyms_normalized,
                "category": category,
                "audit_flags": dedupe_preserve_order(audit_flags),
                "correction_log": correction_log,
            }

            out_json = OUT_INGREDIENT_DIR / f"{item.path.stem}.json"
            out_doc = OUT_DOC_INGREDIENT_DIR / f"{item.path.stem}.txt"
            out_json.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
            out_doc.write_text(ingredient_doc(cleaned), encoding="utf-8")
            doc_count += 1

            files_processed.append(
                {
                    "source_file": rel_source,
                    "type": "ingredient",
                    "status": "processed",
                    "output_json": str(out_json.relative_to(ROOT)).replace("\\", "/"),
                    "output_docs": [str(out_doc.relative_to(ROOT)).replace("\\", "/")],
                    "audit_flags": cleaned["audit_flags"],
                }
            )

        elif file_type == "dish":
            ingredients = raw.get("ingredients", [])
            if not isinstance(ingredients, list):
                ingredients = []

            main: List[str] = []
            secondary: List[str] = []
            seasonings: List[str] = []
            ingredient_ids: List[str] = []
            ingredient_names_vi: List[str] = []
            ingredient_names_en: List[str] = []
            ingredient_names_normalized: List[str] = []

            non_seasoning_items = 0
            split_was_confident = True

            for ing in ingredients:
                if not isinstance(ing, dict):
                    continue

                ing_id = to_none_if_missing(clean_text(ing.get("ingredient_id", "")))
                ing_vi = to_none_if_missing(clean_text(ing.get("name_vi", "")))
                ing_en = to_none_if_missing(clean_text(ing.get("name_en", "")))
                ing_norm_raw = to_none_if_missing(clean_text(ing.get("name_normalized", "")))
                ing_cat = to_none_if_missing(clean_text(ing.get("category", "")))
                importance = ing.get("importance")

                canonical_ing_hint = canonical_en_from_counter(vi_to_en_counter[build_name_normalized(ing_vi)])
                ing_en_clean, ing_norm_clean, ing_flags, ing_corrections, ing_uncertain = audit_name_pair(
                    name_vi=ing_vi,
                    name_en=ing_en,
                    name_normalized=ing_norm_raw,
                    canonical_en_hint=canonical_ing_hint,
                )

                for corr in ing_corrections:
                    corr_with_context = dict(corr)
                    corr_with_context["field"] = f"ingredients[].{corr['field']}"
                    corr_with_context["ingredient_name_vi"] = ing_vi
                    correction_log.append(corr_with_context)

                for flag in ing_flags:
                    if flag == "needs_manual_review_translation":
                        audit_flags.append("needs_manual_review_translation")

                for note in ing_uncertain:
                    uncertain_cases.append(
                        {
                            "source_file": rel_source,
                            "field": "ingredients[].name_en",
                            "name_vi": ing_vi,
                            "current_value": ing_en,
                            "note": note,
                        }
                    )

                if ing_id:
                    ingredient_ids.append(ing_id)
                if ing_vi:
                    ingredient_names_vi.append(ing_vi)
                if ing_en_clean:
                    ingredient_names_en.append(ing_en_clean)
                if ing_norm_clean:
                    ingredient_names_normalized.append(ing_norm_clean)

                if not ing_vi:
                    continue

                if is_seasoning(ing_norm_clean or build_name_normalized(ing_vi), ing_cat):
                    seasonings.append(ing_vi)
                    continue

                non_seasoning_items += 1
                # Use importance when present; fallback to category/name heuristics.
                if isinstance(importance, (int, float)):
                    if float(importance) >= 3:
                        main.append(ing_vi)
                    elif float(importance) == 2:
                        secondary.append(ing_vi)
                    else:
                        secondary.append(ing_vi)
                else:
                    split_was_confident = False
                    secondary.append(ing_vi)

            main = dedupe_preserve_order(main)
            secondary = dedupe_preserve_order(secondary)
            seasonings = dedupe_preserve_order(seasonings)
            ingredient_ids = dedupe_preserve_order(ingredient_ids)
            ingredient_names_vi = dedupe_preserve_order(ingredient_names_vi)
            ingredient_names_en = dedupe_preserve_order(ingredient_names_en)
            ingredient_names_normalized = dedupe_preserve_order(ingredient_names_normalized)

            grouping_mode = "split"
            if non_seasoning_items > 1 and (not main or not split_was_confident):
                combined = dedupe_preserve_order(main + secondary)
                main = combined
                secondary = []
                grouping_mode = "combined"
                audit_flags.append("ingredient_grouping_low_confidence")

            cleaned = {
                "id": record_id,
                "type": "dish",
                "source_file": rel_source,
                "name_vi": name_vi,
                "name_en": name_en_clean,
                "name_normalized": name_norm_clean,
                "category": category,
                "main_ingredients": main,
                "secondary_ingredients": secondary,
                "seasonings": seasonings,
                "ingredient_ids": ingredient_ids,
                "ingredient_names_vi": ingredient_names_vi,
                "ingredient_names_en": ingredient_names_en,
                "ingredient_names_normalized": ingredient_names_normalized,
                "grouping_mode": grouping_mode,
                "audit_flags": dedupe_preserve_order(audit_flags),
                "correction_log": correction_log,
            }

            out_json = OUT_DISH_DIR / f"{item.path.stem}.json"
            out_doc_a = OUT_DOC_DISH_DIR / f"{item.path.stem}_a_identity.txt"
            out_doc_b = OUT_DOC_DISH_DIR / f"{item.path.stem}_b_ingredients.txt"
            out_json.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
            out_doc_a.write_text(dish_doc_identity(cleaned), encoding="utf-8")
            out_doc_b.write_text(dish_doc_ingredients(cleaned), encoding="utf-8")
            doc_count += 2

            files_processed.append(
                {
                    "source_file": rel_source,
                    "type": "dish",
                    "status": "processed",
                    "output_json": str(out_json.relative_to(ROOT)).replace("\\", "/"),
                    "output_docs": [
                        str(out_doc_a.relative_to(ROOT)).replace("\\", "/"),
                        str(out_doc_b.relative_to(ROOT)).replace("\\", "/"),
                    ],
                    "audit_flags": cleaned["audit_flags"],
                }
            )

        else:
            files_processed.append(
                {
                    "source_file": rel_source,
                    "status": "skipped",
                    "reason": "Unable to detect type",
                }
            )

        for corr in correction_log:
            corrected_fields.append({"source_file": rel_source, **corr})
            if "name_normalized" in str(corr.get("field", "")):
                normalization_errors_fixed += 1
            if str(corr.get("field", "")).endswith("name_en") and corr.get("confidence") == "high":
                high_confidence_english_corrections += 1

    # Reports
    report_payloads = {
        "files_processed.json": files_processed,
        "corrected_fields.json": corrected_fields,
        "uncertain_cases.json": uncertain_cases,
        "missing_required_fields.json": missing_required,
    }

    for name, payload in report_payloads.items():
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        (OUT_REPORT_DIR / name).write_text(text, encoding="utf-8")
        (OUT_AUDIT_REPORT_DIR / name).write_text(text, encoding="utf-8")

    num_dishes = sum(1 for x in files_processed if x.get("type") == "dish" and x.get("status") == "processed")
    num_ingredients = sum(1 for x in files_processed if x.get("type") == "ingredient" and x.get("status") == "processed")
    corrected_en_count = sum(1 for x in corrected_fields if x.get("field", "").endswith("name_en"))
    uncertain_count = len(uncertain_cases)
    missing_files = len({x["source_file"] for x in missing_required})
    files_flagged_manual_review = sum(
        1
        for x in files_processed
        if x.get("status") == "processed" and "needs_manual_review_translation" in x.get("audit_flags", [])
    )

    issue_counter = Counter()
    for fp in files_processed:
        for flag in fp.get("audit_flags", []):
            issue_counter[flag] += 1

    common_issues = "\n".join(
        f"- {name}: {count}" for name, count in issue_counter.most_common(10)
    ) or "- Khong phat hien co loi co co tan suat cao"

    summary_md = (
        "# Dataset Summary\n\n"
        f"- Number of dish files: {num_dishes}\n"
        f"- Number of ingredient files: {num_ingredients}\n"
        f"- Number of corrected English names: {corrected_en_count}\n"
        f"- Number of high-confidence English corrections: {high_confidence_english_corrections}\n"
        f"- Number of uncertain translations: {uncertain_count}\n"
        f"- Number of normalization errors fixed: {normalization_errors_fixed}\n"
        f"- Number of files flagged for manual translation review: {files_flagged_manual_review}\n"
        f"- Number of files with missing fields: {missing_files}\n\n"
        "## Common Data Quality Problems\n"
        f"{common_issues}\n"
    )

    (OUT_REPORT_DIR / "dataset_summary.md").write_text(summary_md, encoding="utf-8")
    (OUT_AUDIT_REPORT_DIR / "dataset_summary.md").write_text(summary_md, encoding="utf-8")

    return {
        "files_processed": len([x for x in files_processed if x.get("status") == "processed"]),
        "documents_generated": doc_count,
        "corrections_made": len(corrected_fields),
        "uncertain_cases": uncertain_count,
        "normalization_errors_fixed": normalization_errors_fixed,
        "high_confidence_english_corrections": high_confidence_english_corrections,
        "files_flagged_manual_review": files_flagged_manual_review,
    }


def run_normalization_smoke_test() -> None:
    samples = {
        "đường": "duong",
        "ĐƯỜNG": "duong",
        "đu đủ": "du du",
        "bí đỏ": "bi do",
    }
    print("Normalization smoke test:")
    for source, expected in samples.items():
        actual = build_name_normalized(source)
        status = "OK" if actual == expected else "FAIL"
        print(f"- {source} -> {actual} (expected: {expected}) [{status}]")
        if actual != expected:
            raise ValueError(f"Normalization failed for '{source}': got '{actual}', expected '{expected}'")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build cleaned RAG documents and audit reports.")
    parser.add_argument(
        "--sample-test-only",
        action="store_true",
        help="Run normalization smoke test only.",
    )
    args = parser.parse_args()

    run_normalization_smoke_test()
    if args.sample_test_only:
        print("Sample normalization test completed. Skipping full pipeline.")
        return

    result = process()
    print("Processing complete")
    print(f"Total files processed: {result['files_processed']}")
    print(f"Total documents generated: {result['documents_generated']}")
    print(f"Total corrections made: {result['corrections_made']}")
    print(f"Total uncertain cases flagged: {result['uncertain_cases']}")
    print(f"Total normalization errors fixed: {result['normalization_errors_fixed']}")
    print(f"Total high-confidence English corrections: {result['high_confidence_english_corrections']}")
    print(f"Total files flagged for manual review: {result['files_flagged_manual_review']}")


if __name__ == "__main__":
    main()
