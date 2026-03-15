from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Set, Tuple

from tqdm import tqdm

from .adapters import LiveRAGAdapter, parse_conflict_pairs
from .config import EvaluationPaths
from .loaders import load_conflict_cases, load_dish_query_cases, load_replacement_cases
from .metrics.layer_a import compute_layer_a_case_metrics, summarize_layer_a
from .metrics.layer_b import compute_layer_b_case_metrics, summarize_layer_b
from .metrics.layer_c import compute_layer_c_case_metrics, summarize_layer_c
from .reporting import ReportWriter


@dataclass
class EvaluationRunResult:
    overall_summary: Dict[str, Any]
    output_files: List[str]


@dataclass
class EvaluationCoordinator:
    paths: EvaluationPaths

    def __post_init__(self) -> None:
        self._layer_a_details: List[Dict[str, Any]] = []

    def run_all(self) -> EvaluationRunResult:
        adapter = LiveRAGAdapter.build_default()
        writer = ReportWriter(self.paths.outputs_root)

        # Incremental persistence: clear output files at run start, then append per-case.
        writer.reset_layer_rows("layerA_results.jsonl")
        writer.reset_layer_rows("layerB_results.jsonl")
        writer.reset_layer_rows("layerC_results.jsonl")
        writer.reset_layer_rows("layerA_detailed_output.jsonl")

        layer_a_rows = self._run_layer_a(adapter, writer)
        layer_b_rows = self._run_layer_b(adapter, writer)
        layer_c_rows = self._run_layer_c(adapter, writer)

        summary_a = summarize_layer_a(layer_a_rows)
        summary_b = summarize_layer_b(layer_b_rows)
        summary_c = summarize_layer_c(layer_c_rows)

        output_files: List[str] = []
        output_files.append(str(self.paths.outputs_root / "layerA_results.jsonl"))
        output_files.append(str(self.paths.outputs_root / "layerB_results.jsonl"))
        output_files.append(str(self.paths.outputs_root / "layerC_results.jsonl"))
        output_files.append(str(self.paths.outputs_root / "layerA_detailed_output.jsonl"))

        output_files.append(str(writer.write_layer_summary("layerA_summary.json", summary_a)))
        output_files.append(str(writer.write_layer_summary("layerB_summary.json", summary_b)))
        output_files.append(str(writer.write_layer_summary("layerC_summary.json", summary_c)))

        overall = {
            "layerA": summary_a,
            "layerB": summary_b,
            "layerC": summary_c,
        }
        output_files.append(str(writer.write_overall_summary("overall_summary.json", overall)))

        return EvaluationRunResult(overall_summary=overall, output_files=output_files)

    def _run_layer_a(self, adapter: LiveRAGAdapter, writer: ReportWriter) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for case in tqdm(load_dish_query_cases(self.paths), desc="Evaluation Layer A", unit="case"):
            try:
                response = adapter.run_text(case.user_input)
                row = compute_layer_a_case_metrics(case, response)
                detail_row = {
                    "case_id": case.case_id,
                    "split": case.split,
                    "user_input": case.user_input,
                    "expected": case.expected.model_dump(),
                    "response": response,
                    "retrieval_output": adapter.get_last_retrieval_trace(),
                    "metrics": row,
                }
            except Exception as exc:
                row = {
                    "case_id": case.case_id,
                    "split": case.split,
                    "tags": ",".join(case.tags),
                    "dish_ok": 0,
                    "precision_all": 0.0,
                    "recall_all": 0.0,
                    "f1_all": 0.0,
                    "precision_core": 0.0,
                    "recall_core": 0.0,
                    "f1_core": 0.0,
                    "excluded_ok": None,
                    "extra_ok": None,
                    "gt_count": len(case.expected.gt_ingredient_ids),
                    "pred_count": 0,
                    "error": str(exc),
                }
                detail_row = {
                    "case_id": case.case_id,
                    "split": case.split,
                    "user_input": case.user_input,
                    "expected": case.expected.model_dump(),
                    "response": None,
                    "retrieval_output": adapter.get_last_retrieval_trace(),
                    "metrics": row,
                }
            rows.append(row)
            self._layer_a_details.append(detail_row)
            writer.append_layer_row("layerA_results.jsonl", row)
            writer.append_layer_row("layerA_detailed_output.jsonl", detail_row)
        return rows

    def _run_layer_b(self, adapter: LiveRAGAdapter, writer: ReportWriter) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for case in tqdm(load_conflict_cases(self.paths), desc="Evaluation Layer B", unit="case"):
            name_to_id: Dict[str, str] = {}
            for item in case.input_ingredients.items:
                name = str(item.get("name_vi") or item.get("name") or "").strip().lower()
                ing_id = str(item.get("ingredient_id") or "").strip()
                if name and ing_id:
                    name_to_id[name] = ing_id

            try:
                conflict_rows = adapter.detect_conflicts(case.input_ingredients.items)
                pred_pairs: Set[Tuple[str, str]] = parse_conflict_pairs(conflict_rows, name_to_id)
                row = compute_layer_b_case_metrics(case, pred_pairs)
            except Exception as exc:
                row = {
                    "case_id": case.case_id,
                    "format": case.input_ingredients.format,
                    "tags": ",".join(case.tags),
                    "gt_conflicts": len(case.expected.conflict_pairs),
                    "pred_conflicts": 0,
                    "precision": 0.0,
                    "recall": 0.0,
                    "f1": 0.0,
                    "error": str(exc),
                }
            rows.append(row)
            writer.append_layer_row("layerB_results.jsonl", row)
        return rows

    def _run_layer_c(self, adapter: LiveRAGAdapter, writer: ReportWriter) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        id_to_category = {
            ing_id: ing.get("category")
            for ing_id, ing in adapter.ontology_service.ingredients.items()
        }

        for case in tqdm(load_replacement_cases(self.paths), desc="Evaluation Layer C", unit="case"):
            target_id = case.context.target_replace_id
            target_category = case.context.target_category or id_to_category.get(target_id)
            exclude_ids = set(case.context.exclude_ids)
            max_suggestions = case.constraints.max_suggestions

            try:
                suggestions = adapter.suggest_replacements(target_id, exclude_ids, max_suggestions)
                suggestion_ids = [s.get("ingredient_id") for s in suggestions if s.get("ingredient_id")]
                row = compute_layer_c_case_metrics(
                    case_id=case.case_id,
                    target_id=target_id,
                    target_category=target_category,
                    exclude_ids=exclude_ids,
                    max_suggestions=max_suggestions,
                    suggestion_ids=suggestion_ids,
                    id_to_category=id_to_category,
                )
            except Exception as exc:
                row = {
                    "case_id": case.case_id,
                    "target_replace_id": target_id,
                    "target_category": target_category,
                    "n_suggestions": 0,
                    "cap_ok": 0,
                    "overall_valid_rate": 0.0,
                    "coverage": 0,
                    "category_match_rate": 0.0,
                    "exclusion_compliance_rate": 0.0,
                    "uniqueness_rate": 0.0,
                    "error": str(exc),
                }
            rows.append(row)
            writer.append_layer_row("layerC_results.jsonl", row)
        return rows
