#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from common import (
    find_source_definition,
    finish_pipeline_run,
    load_dotenv_file,
    load_effective_yaml,
    resolve_source_adapter,
    start_pipeline_run,
    state_dir_from_config,
    update_pipeline_stage,
)


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
    config, _ = load_effective_yaml("config.yaml", "config.example.yaml")
    sources_config, _ = load_effective_yaml("sources.yaml", "sources.example.yaml")
    _, source_def = find_source_definition(sources_config, args.source)
    adapter = resolve_source_adapter(args.source, source_def)
    state_dir = state_dir_from_config(config)
    run_id = start_pipeline_run(state_dir, args.source, args.top, args.skip_fetch)

    try:
        update_pipeline_stage(state_dir, run_id, "init")
        run_step(["scripts/init.py"])
        update_pipeline_stage(state_dir, run_id, "init", completed=True)

        if not args.skip_fetch:
            update_pipeline_stage(state_dir, run_id, "fetch")
            run_step([f"scripts/fetch-{adapter}.py", "--source-id", args.source, "--days", str(args.days)])
            update_pipeline_stage(state_dir, run_id, "fetch", completed=True)

        update_pipeline_stage(state_dir, run_id, "normalize")
        run_step([f"scripts/normalize-{adapter}.py", "--source-id", args.source])
        update_pipeline_stage(state_dir, run_id, "normalize", completed=True)

        update_pipeline_stage(state_dir, run_id, "filter")
        run_step(["scripts/filter-candidates.py"])
        update_pipeline_stage(state_dir, run_id, "filter", completed=True)

        update_pipeline_stage(state_dir, run_id, "merge")
        run_step(["scripts/merge-project-entities.py"])
        update_pipeline_stage(state_dir, run_id, "merge", completed=True)

        update_pipeline_stage(state_dir, run_id, "score")
        run_step(["scripts/score-opportunities.py", "--top", str(args.top)])
        update_pipeline_stage(state_dir, run_id, "score", completed=True)

        update_pipeline_stage(state_dir, run_id, "context")
        run_step(["scripts/build-summary-context.py", "--top", str(args.top)])
        update_pipeline_stage(state_dir, run_id, "context", completed=True)

        update_pipeline_stage(state_dir, run_id, "dossiers")
        run_step(["scripts/build-project-dossiers.py", "--top", str(args.top)])
        update_pipeline_stage(state_dir, run_id, "dossiers", completed=True)

        update_pipeline_stage(state_dir, run_id, "briefs")
        run_step(["scripts/build-briefs.py", "--top", str(min(args.top, 8))])
        update_pipeline_stage(state_dir, run_id, "briefs", completed=True)

        update_pipeline_stage(state_dir, run_id, "check-run-state")
        run_step(["scripts/check-run-state.py"])
        update_pipeline_stage(state_dir, run_id, "check-run-state", completed=True)

        finish_pipeline_run(state_dir, run_id, "completed")
        return 0
    except subprocess.CalledProcessError as exc:
        finish_pipeline_run(state_dir, run_id, "failed", error=f"Command failed with exit code {exc.returncode}")
        return exc.returncode
    except Exception as exc:
        finish_pipeline_run(state_dir, run_id, "failed", error=str(exc))
        raise


if __name__ == "__main__":
    raise SystemExit(main())
