from __future__ import annotations

import argparse
from pathlib import Path

from .config import build_default_paths
from .runners import EvaluationCoordinator


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run rag_service evaluation pipeline.")
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

    coordinator = EvaluationCoordinator(paths=paths)
    result = coordinator.run_all()

    print("Evaluation completed")
    print("Overall summary:")
    print(result.overall_summary)
    print("Output files:")
    for path in result.output_files:
        print("-", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
