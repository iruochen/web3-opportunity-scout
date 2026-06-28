#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from common import enabled_source_entries, find_source_definition, load_dotenv_file, load_effective_yaml, resolve_source_adapter


ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified CLI for web3-opportunity-scout.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor", help="Validate repository setup")
    subparsers.add_parser("init", help="Initialize state files")
    subparsers.add_parser("list-sources", help="List configured sources and whether they are enabled")

    fetch_parser = subparsers.add_parser("fetch", help="Fetch raw payloads for a configured source")
    fetch_parser.add_argument("--source", default="rootdata_projects")
    fetch_parser.add_argument("--days", type=int, default=1)
    fetch_parser.add_argument("--limit", type=int)
    fetch_parser.add_argument("--dry-run", action="store_true")

    legacy_fetch_parser = subparsers.add_parser("fetch-rootdata", help="Fetch RootData raw payloads")
    legacy_fetch_parser.add_argument("--days", type=int, default=1)
    legacy_fetch_parser.add_argument("--limit", type=int)
    legacy_fetch_parser.add_argument("--dry-run", action="store_true")

    run_parser = subparsers.add_parser("run", help="Run the end-to-end pipeline")
    run_parser.add_argument("--source", default="rootdata_projects")
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
    if args.command == "list-sources":
        sources_config, _ = load_effective_yaml("sources.yaml", "sources.example.yaml")
        enabled = {entry.get("id") for _, entry in enabled_source_entries(sources_config)}
        print("Configured sources:")
        for category, entry in sources_config.get("sources", {}).items():
            if not isinstance(entry, list):
                continue
            for item in entry:
                if not isinstance(item, dict):
                    continue
                source_id = item.get("id", "unknown")
                adapter = item.get("adapter", "n/a")
                status = "enabled" if source_id in enabled else "disabled"
                print(f"- {source_id} [{category}] adapter={adapter} status={status}")
        return 0
    if args.command in {"fetch-rootdata", "fetch"}:
        source_id = "rootdata_projects" if args.command == "fetch-rootdata" else args.source
        sources_config, _ = load_effective_yaml("sources.yaml", "sources.example.yaml")
        _, source_def = find_source_definition(sources_config, source_id)
        adapter = resolve_source_adapter(source_id, source_def)
        command = [f"scripts/fetch-{adapter}.py", "--source-id", source_id, "--days", str(args.days)]
        if args.limit is not None:
            command.extend(["--limit", str(args.limit)])
        if args.dry_run:
            command.append("--dry-run")
        return run_script(command)
    if args.command == "run":
        command = ["scripts/run-pipeline.py", "--source", args.source, "--top", str(args.top), "--days", str(args.days)]
        if args.skip_fetch:
            command.append("--skip-fetch")
        return run_script(command)

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
