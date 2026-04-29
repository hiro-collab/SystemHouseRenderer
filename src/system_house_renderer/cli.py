from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from system_house_renderer.pipeline import render_file, write_render_output
from system_house_renderer.runtime_status import RuntimeStatusWriter


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
    map_parser.add_argument(
        "--runtime-status-file",
        default="",
        help=(
            "Optional JSON status file for integration launchers. "
            "SystemHouseRenderer is short-lived, so no health or shutdown endpoint is exposed."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    command_line = list(sys.argv) if argv is None else ["system-house-renderer", *argv]
    args = parser.parse_args(argv)
    setattr(args, "command_line", command_line)
    if args.command == "map":
        return run_map(args)
    parser.print_help()
    return 2


def run_map(args: argparse.Namespace) -> int:
    status_writer = RuntimeStatusWriter(
        args.runtime_status_file or None,
        module="system_house_renderer.map",
        command_line=getattr(args, "command_line", list(sys.argv)),
    )
    status_writer.write_running()
    view_options: dict[str, Any] = {
        "mode": args.mode,
        "metaphor": args.metaphor,
        "detailLevel": args.detail_level,
        "language": args.language,
    }
    try:
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
    except KeyboardInterrupt:
        status_writer.write_stopped()
        print("SystemHouseRenderer interrupted; status marked stopped.", file=sys.stderr)
        return 130
    except Exception as exc:
        status_writer.write_failed(str(exc))
        raise
    status_writer.write_stopped()
    return 0
