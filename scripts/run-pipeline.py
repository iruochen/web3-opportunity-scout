#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the current end-to-end opportunity pipeline.")
    parser.add_argument("--skip-fetch", action="store_true", help="Reuse existing cache and skip live fetch")
    parser.add_argument("--top", type=int, default=15, help="Top ranked projects to keep in the watchlist and markdown output")
    parser.add_argument("--days", type=int, default=1, help="RootData hot_index days parameter")
    return parser.parse_args()


def run_step(args: list[str]) -> None:
    command = [PYTHON, *args]
    print(f"==> {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    args = parse_args()
    run_step(["scripts/init.py"])
    if not args.skip_fetch:
        run_step(["scripts/fetch-rootdata.py", "--days", str(args.days)])
    run_step(["scripts/normalize-rootdata.py"])
    run_step(["scripts/merge-project-entities.py"])
    run_step(["scripts/score-opportunities.py", "--top", str(args.top)])
    run_step(["scripts/build-summary-context.py", "--top", str(args.top)])
    run_step(["scripts/build-project-dossiers.py", "--top", str(args.top)])
    run_step(["scripts/build-briefs.py", "--top", str(min(args.top, 8))])
    run_step(["scripts/check-run-state.py"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
