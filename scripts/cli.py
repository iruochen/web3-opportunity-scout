#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from common import load_dotenv_file


ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified CLI for web3-opportunity-scout.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor", help="Validate repository setup")
    subparsers.add_parser("init", help="Initialize state files")

    fetch_parser = subparsers.add_parser("fetch-rootdata", help="Fetch RootData raw payloads")
    fetch_parser.add_argument("--days", type=int, default=1)
    fetch_parser.add_argument("--limit", type=int)
    fetch_parser.add_argument("--dry-run", action="store_true")

    run_parser = subparsers.add_parser("run", help="Run the end-to-end pipeline")
    run_parser.add_argument("--skip-fetch", action="store_true")
    run_parser.add_argument("--top", type=int, default=10)
    run_parser.add_argument("--days", type=int, default=1)

    return parser


def run_script(args: list[str]) -> int:
    command = [PYTHON, *args]
    print(f"==> {' '.join(command)}", flush=True)
    completed = subprocess.run(command, cwd=ROOT)
    return completed.returncode


def main() -> int:
    load_dotenv_file()
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "doctor":
        return run_script(["scripts/doctor.py"])
    if args.command == "init":
        return run_script(["scripts/init.py"])
    if args.command == "fetch-rootdata":
        command = ["scripts/fetch-rootdata.py", "--days", str(args.days)]
        if args.limit is not None:
            command.extend(["--limit", str(args.limit)])
        if args.dry_run:
            command.append("--dry-run")
        return run_script(command)
    if args.command == "run":
        command = ["scripts/run-pipeline.py", "--top", str(args.top), "--days", str(args.days)]
        if args.skip_fetch:
            command.append("--skip-fetch")
        return run_script(command)

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
