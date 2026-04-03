from __future__ import annotations

import argparse
from pathlib import Path

from .adapters import LiveRAGAdapter
from .config import build_default_paths
from .metrics.layer_b import summarize_layer_b
from .reporting import ReportWriter
from .runners import EvaluationCoordinator


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run only Layer B evaluation.")
    parser.add_argument(
        "--repo-root",
        type=str,
        default=str(Path(__file__).resolve().parents[1]),
        help="Repository root path.",
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    paths = build_default_paths(repo_root)

    adapter = LiveRAGAdapter.build_default()
    writer = ReportWriter(paths.outputs_root)
    coordinator = EvaluationCoordinator(paths=paths)

    # Reset only Layer B artifacts before rerun to avoid append duplicates.
    writer.reset_layer_rows("layerB_results.jsonl")

    layer_b_rows = coordinator._run_layer_b(adapter, writer)
    summary_b = summarize_layer_b(layer_b_rows)
    writer.write_layer_summary("layerB_summary.json", summary_b)

    print("Layer B evaluation completed")
    print(summary_b)
    print("Output files:")
    print("-", paths.outputs_root / "layerB_results.jsonl")
    print("-", paths.outputs_root / "layerB_summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
