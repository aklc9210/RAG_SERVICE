from __future__ import annotations

from typing import List

from .config import EvaluationPaths
from .contracts import DishQueryCase, ConflictCase, ReplacementCase
from .io_jsonl import read_jsonl


def load_dish_query_cases(paths: EvaluationPaths) -> List[DishQueryCase]:
    rows = read_jsonl(paths.dish_query_in_kb) + read_jsonl(paths.dish_query_out_kb)
    return [DishQueryCase.model_validate(row) for row in rows]


def load_conflict_cases(paths: EvaluationPaths) -> List[ConflictCase]:
    rows = read_jsonl(paths.conflict_unit)
    return [ConflictCase.model_validate(row) for row in rows]


def load_replacement_cases(paths: EvaluationPaths) -> List[ReplacementCase]:
    rows = read_jsonl(paths.replacement_cases)
    return [ReplacementCase.model_validate(row) for row in rows]
