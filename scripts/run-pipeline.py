#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from common import find_source_definition, load_dotenv_file, load_effective_yaml, resolve_source_adapter


ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the current end-to-end opportunity pipeline.")
    parser.add_argument("--source", default="rootdata_projects", help="Source id defined in sources.yaml")
    parser.add_argument("--skip-fetch", action="store_true", help="Reuse existing cache and skip live fetch")
    parser.add_argument("--top", type=int, default=15, help="Top ranked projects to keep in the watchlist and markdown output")
    parser.add_argument("--days", type=int, default=1, help="Days parameter for sources that support it")
    return parser.parse_args()


def run_step(args: list[str]) -> None:
    command = [PYTHON, *args]
    print(f"==> {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    load_dotenv_file()
    args = parse_args()
    sources_config, _ = load_effective_yaml("sources.yaml", "sources.example.yaml")
    _, source_def = find_source_definition(sources_config, args.source)
    adapter = resolve_source_adapter(args.source, source_def)

    run_step(["scripts/init.py"])
    if not args.skip_fetch:
        run_step([f"scripts/fetch-{adapter}.py", "--source-id", args.source, "--days", str(args.days)])
    run_step([f"scripts/normalize-{adapter}.py", "--source-id", args.source])
    run_step(["scripts/merge-project-entities.py"])
    run_step(["scripts/score-opportunities.py", "--top", str(args.top)])
    run_step(["scripts/build-summary-context.py", "--top", str(args.top)])
    run_step(["scripts/build-project-dossiers.py", "--top", str(args.top)])
    run_step(["scripts/build-briefs.py", "--top", str(min(args.top, 8))])
    run_step(["scripts/check-run-state.py"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
