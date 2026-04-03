from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _mean(rows: Iterable[Dict[str, Any]], key: str) -> float:
    vals: List[float] = []
    for row in rows:
        value = row.get(key)
        if value is None:
            continue
        vals.append(float(value))
    return sum(vals) / len(vals) if vals else 0.0


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, float]:
    return {
        "n_cases": len(rows),
        "dish_accuracy": _mean(rows, "dish_ok"),
        "macro_f1_all": _mean(rows, "f1_all"),
        "macro_f1_core": _mean(rows, "f1_core"),
        "excluded_ok_rate": _mean(rows, "excluded_ok"),
        "extra_ok_rate": _mean(rows, "extra_ok"),
        "error_rate": _mean(rows, "error"),
    }


def summarize_by_split(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        split = str(row.get("split", "unknown"))
        grouped.setdefault(split, []).append(row)

    return {split: summarize(items) for split, items in grouped.items()}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Recompute Layer A summary from JSONL results.")
    parser.add_argument(
        "--input",
        type=str,
        default="evaluation/outputs/layerA_results.jsonl",
        help="Path to layerA_results.jsonl",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Optional output JSON path. If omitted, prints to stdout only.",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indent for stdout/file output.",
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    input_path = Path(args.input).resolve()

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    rows = load_jsonl(input_path)
    result = {
        "overall": summarize(rows),
        "by_split": summarize_by_split(rows),
    }

    output_text = json.dumps(result, ensure_ascii=False, indent=args.indent)
    print(output_text)

    if args.output:
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_text + "\n", encoding="utf-8")
        print(f"Saved summary to: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
