from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .io_jsonl import append_jsonl, write_json, write_jsonl


@dataclass
class ReportWriter:
    output_root: Path

    def reset_layer_rows(self, filename: str) -> Path:
        path = self.output_root / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        return path

    def append_layer_row(self, filename: str, row: Dict[str, Any]) -> Path:
        path = self.output_root / filename
        append_jsonl(path, row)
        return path

    def write_layer_rows(self, filename: str, rows: Iterable[Dict[str, Any]]) -> Path:
        path = self.output_root / filename
        rows_list: List[Dict[str, Any]] = list(rows)
        write_jsonl(path, rows_list)
        return path

    def write_layer_summary(self, filename: str, summary: Dict[str, Any]) -> Path:
        path = self.output_root / filename
        write_json(path, summary)
        return path

    def write_overall_summary(self, filename: str, payload: Dict[str, Any]) -> Path:
        path = self.output_root / filename
        write_json(path, payload)
        return path
