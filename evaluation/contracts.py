from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ExcludedExpected(BaseModel):
    names: List[str] = Field(default_factory=list)
    ingredient_ids: List[str] = Field(default_factory=list)


class ExtraExpected(BaseModel):
    names: List[str] = Field(default_factory=list)
    ingredient_ids: List[str] = Field(default_factory=list)


class DishExpected(BaseModel):
    dish_id: Optional[str] = None
    dish_name_vi: str = ""
    gt_ingredient_ids: List[str] = Field(default_factory=list)
    gt_core_ingredient_ids: List[str] = Field(default_factory=list)
    excluded: ExcludedExpected = Field(default_factory=ExcludedExpected)
    extra: ExtraExpected = Field(default_factory=ExtraExpected)


class DishQueryCase(BaseModel):
    case_id: str
    split: str
    user_input: str
    expected: DishExpected
    tags: List[str] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)


class ConflictExpectedPair(BaseModel):
    a_id: str
    b_id: str
    severity: Optional[str] = None
    reason: Optional[str] = None


class ConflictExpected(BaseModel):
    conflict_pairs: List[ConflictExpectedPair] = Field(default_factory=list)
    conflict_count: int = 0


class ConflictInput(BaseModel):
    format: str
    items: List[Dict[str, Any]] = Field(default_factory=list)


class ConflictCase(BaseModel):
    case_id: str
    input_ingredients: ConflictInput
    expected: ConflictExpected
    tags: List[str] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)


class ReplacementContext(BaseModel):
    dish_id: Optional[str] = None
    dish_name_vi: Optional[str] = None
    conflicted_pair: Dict[str, Any] = Field(default_factory=dict)
    target_replace_id: str
    target_category: Optional[str] = None
    exclude_ids: List[str] = Field(default_factory=list)


class ReplacementConstraints(BaseModel):
    same_category: bool = True
    must_not_include_ids: List[str] = Field(default_factory=list)
    unique: bool = True
    max_suggestions: int = 3


class ReplacementExpected(BaseModel):
    valid_replacement_exists_in_ontology: bool = True
    min_valid_suggestions: int = 1


class ReplacementCase(BaseModel):
    case_id: str
    context: ReplacementContext
    constraints: ReplacementConstraints
    expected: ReplacementExpected
    tags: List[str] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)


class LayerSummary(BaseModel):
    layer_name: str
    metrics: Dict[str, Any] = Field(default_factory=dict)


class EvaluationArtifacts(BaseModel):
    layer_summaries: List[LayerSummary] = Field(default_factory=list)
    output_files: List[str] = Field(default_factory=list)
