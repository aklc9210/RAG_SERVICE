from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EvaluationPaths:
    repo_root: Path
    evaluation_root: Path
    datasets_root: Path
    outputs_root: Path

    @property
    def dish_query_in_kb(self) -> Path:
        return self.datasets_root / "dish_query_set" / "dish_queries_in_kb.jsonl"

    @property
    def dish_query_out_kb(self) -> Path:
        return self.datasets_root / "dish_query_set" / "dish_queries_out_kb.jsonl"

    @property
    def conflict_unit(self) -> Path:
        return self.datasets_root / "conflict_unit_set" / "conflict_unit_tests.jsonl"

    @property
    def replacement_cases(self) -> Path:
        return self.datasets_root / "replacement_constraint_set" / "replacement_cases.jsonl"


def build_default_paths(repo_root: Path) -> EvaluationPaths:
    evaluation_root = repo_root / "evaluation"
    return EvaluationPaths(
        repo_root=repo_root,
        evaluation_root=evaluation_root,
        datasets_root=evaluation_root / "data" / "datasets",
        outputs_root=evaluation_root / "outputs",
    )
