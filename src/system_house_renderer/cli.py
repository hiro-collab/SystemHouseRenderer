from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from system_house_renderer.pipeline import render_file, write_render_output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render system topology or Dify workflows as a house map."
    )
    subparsers = parser.add_subparsers(dest="command")
    map_parser = subparsers.add_parser("map", help="Generate map JSON and preview HTML.")
    map_parser.add_argument(
        "--input",
        default="",
        help="Input JSON/YAML topology or Dify export. Optional when --runtime uses a topology-producing adapter.",
    )
    map_parser.add_argument("--out", required=True, help="Output directory.")
    map_parser.add_argument(
        "--runtime",
        default="",
        help="Optional runtime trace JSON/YAML/JSONL or SSE URL.",
    )
    map_parser.add_argument(
        "--runtime-adapter",
        choices=("auto", "generic", "sword-events"),
        default="auto",
        help="How to normalize --runtime. auto detects events.jsonl and /api/events.",
    )
    map_parser.add_argument(
        "--turn-id",
        default="",
        help="Filter runtime events to a single turn_id when supported.",
    )
    map_parser.add_argument("--requirements", default="", help="Optional requirements JSON/YAML.")
    map_parser.add_argument(
        "--mode",
        choices=("overview", "tour", "trace", "debug", "cost", "security"),
        default="overview",
    )
    map_parser.add_argument("--metaphor", choices=("house",), default="house")
    map_parser.add_argument(
        "--detail-level",
        choices=("simple", "normal", "deep"),
        default="normal",
    )
    map_parser.add_argument("--language", choices=("ja", "en"), default="ja")
    map_parser.add_argument(
        "--print-files",
        action="store_true",
        help="Print generated file paths as JSON.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "map":
        return run_map(args)
    parser.print_help()
    return 2


def run_map(args: argparse.Namespace) -> int:
    view_options: dict[str, Any] = {
        "mode": args.mode,
        "metaphor": args.metaphor,
        "detailLevel": args.detail_level,
        "language": args.language,
    }
    output = render_file(
        args.input or None,
        runtime_path=args.runtime or None,
        runtime_adapter=args.runtime_adapter,
        turn_id=args.turn_id or None,
        requirements_path=args.requirements or None,
        view_options=view_options,
    )
    files = write_render_output(output, args.out)
    if args.print_files:
        print(
            json.dumps(
                {key: str(path) for key, path in files.items()},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"generated SystemHouseRenderer output in {Path(args.out)}")
    return 0
