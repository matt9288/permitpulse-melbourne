from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from permitpulse.pipeline import build_pipeline, download_address_source, download_source


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Use an ISO date such as 2026-10-01.") from error


def _add_build_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--as-of-date", type=_date, default=None)
    parser.add_argument(
        "--address-input",
        type=Path,
        default=None,
        help="Optional City of Melbourne street-address CSV used for map coordinates.",
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="permitpulse")
    subcommands = root.add_subparsers(dest="command", required=True)

    build = subcommands.add_parser("build", help="Build from an existing source snapshot.")
    build.add_argument("--input", type=Path, required=True)
    _add_build_arguments(build)

    refresh = subcommands.add_parser("refresh", help="Download the open dataset and build it.")
    refresh.add_argument("--raw-path", type=Path, default=Path("data/raw/building-permits.csv"))
    refresh.add_argument(
        "--address-raw-path",
        type=Path,
        default=Path("data/raw/street-addresses.csv"),
    )
    _add_build_arguments(refresh)
    return root


def main() -> None:
    arguments = parser().parse_args()
    if arguments.command == "refresh":
        source = download_source(arguments.raw_path)
        address_source = download_address_source(arguments.address_raw_path)
    else:
        source = arguments.input
        address_source = arguments.address_input
    summary = build_pipeline(
        source,
        arguments.output_dir,
        arguments.as_of_date,
        address_source,
    )
    print(json.dumps(asdict(summary), indent=2))


if __name__ == "__main__":
    main()
