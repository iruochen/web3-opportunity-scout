#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from common import (
    enabled_source_entries,
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


def pipeline_capable_sources(sources_config: dict[str, object]) -> list[str]:
    source_ids: list[str] = []
    for _, entry in enabled_source_entries(sources_config):
        source_id = str(entry.get("id") or "").strip()
        adapter = str(entry.get("adapter") or "").strip()
        if not source_id or not adapter:
            continue
        if source_id == "combined_market_scan":
            continue
        if source_id not in source_ids:
            source_ids.append(source_id)
    return source_ids


def main() -> int:
    load_dotenv_file()
    args = parse_args()
    config, _ = load_effective_yaml("config.yaml", "config.example.yaml")
    sources_config, _ = load_effective_yaml("sources.yaml", "sources.example.yaml")
    state_dir = state_dir_from_config(config)
    run_id = start_pipeline_run(state_dir, args.source, args.top, args.skip_fetch)

    try:
        update_pipeline_stage(state_dir, run_id, "init")
        run_step(["scripts/init.py"])
        update_pipeline_stage(state_dir, run_id, "init", completed=True)

        if args.source == "combined_market_scan":
            child_sources = pipeline_capable_sources(sources_config)
            if not child_sources:
                raise ValueError("No enabled adapter-backed sources are available for combined_market_scan")
            include_args: list[str] = []
            for source_id in child_sources:
                include_args.extend(["--include-source", source_id])

            for child_source in child_sources:
                _, source_def = find_source_definition(sources_config, child_source)
                adapter = resolve_source_adapter(child_source, source_def)
                if not args.skip_fetch:
                    update_pipeline_stage(state_dir, run_id, f"fetch:{child_source}")
                    run_step([f"scripts/fetch-{adapter}.py", "--source-id", child_source, "--days", str(args.days)])
                    update_pipeline_stage(state_dir, run_id, f"fetch:{child_source}", completed=True)

                    if adapter == "rootdata":
                        update_pipeline_stage(state_dir, run_id, f"fetch-details:{child_source}")
                        run_step(["scripts/fetch-rootdata-details.py", "--source-id", child_source])
                        update_pipeline_stage(state_dir, run_id, f"fetch-details:{child_source}", completed=True)

                update_pipeline_stage(state_dir, run_id, f"normalize:{child_source}")
                run_step([f"scripts/normalize-{adapter}.py", "--source-id", child_source])
                update_pipeline_stage(state_dir, run_id, f"normalize:{child_source}", completed=True)

            update_pipeline_stage(state_dir, run_id, "combine-normalized")
            run_step(["scripts/build-combined-normalized.py", "--source-id", args.source, *include_args])
            update_pipeline_stage(state_dir, run_id, "combine-normalized", completed=True)

            update_pipeline_stage(state_dir, run_id, "filter")
            run_step(["scripts/filter-candidates.py", "--source-id", args.source])
            update_pipeline_stage(state_dir, run_id, "filter", completed=True)

            update_pipeline_stage(state_dir, run_id, "merge")
            run_step(["scripts/merge-project-entities.py", "--source-id", args.source])
            update_pipeline_stage(state_dir, run_id, "merge", completed=True)

            update_pipeline_stage(state_dir, run_id, "score")
            run_step(["scripts/score-opportunities.py", "--source-id", args.source, "--top", str(args.top)])
            update_pipeline_stage(state_dir, run_id, "score", completed=True)

            update_pipeline_stage(state_dir, run_id, "context")
            run_step(["scripts/build-summary-context.py", "--source-id", args.source, "--top", str(args.top)])
            update_pipeline_stage(state_dir, run_id, "context", completed=True)

            update_pipeline_stage(state_dir, run_id, "dossiers")
            run_step(["scripts/build-project-dossiers.py", "--source-id", args.source, "--top", str(args.top)])
            update_pipeline_stage(state_dir, run_id, "dossiers", completed=True)

            update_pipeline_stage(state_dir, run_id, "briefs")
            run_step(["scripts/build-briefs.py", "--source-id", args.source, "--top", str(min(args.top, 8))])
            update_pipeline_stage(state_dir, run_id, "briefs", completed=True)

            update_pipeline_stage(state_dir, run_id, "check-run-state")
            run_step(["scripts/check-run-state.py"])
            update_pipeline_stage(state_dir, run_id, "check-run-state", completed=True)

            finish_pipeline_run(state_dir, run_id, "completed")
            return 0

        _, source_def = find_source_definition(sources_config, args.source)
        adapter = resolve_source_adapter(args.source, source_def)

        if not args.skip_fetch:
            update_pipeline_stage(state_dir, run_id, "fetch")
            run_step([f"scripts/fetch-{adapter}.py", "--source-id", args.source, "--days", str(args.days)])
            update_pipeline_stage(state_dir, run_id, "fetch", completed=True)

            if adapter == "rootdata":
                update_pipeline_stage(state_dir, run_id, "fetch-details")
                run_step(["scripts/fetch-rootdata-details.py", "--source-id", args.source])
                update_pipeline_stage(state_dir, run_id, "fetch-details", completed=True)

        update_pipeline_stage(state_dir, run_id, "normalize")
        run_step([f"scripts/normalize-{adapter}.py", "--source-id", args.source])
        update_pipeline_stage(state_dir, run_id, "normalize", completed=True)

        update_pipeline_stage(state_dir, run_id, "filter")
        run_step(["scripts/filter-candidates.py", "--source-id", args.source])
        update_pipeline_stage(state_dir, run_id, "filter", completed=True)

        update_pipeline_stage(state_dir, run_id, "merge")
        run_step(["scripts/merge-project-entities.py", "--source-id", args.source])
        update_pipeline_stage(state_dir, run_id, "merge", completed=True)

        update_pipeline_stage(state_dir, run_id, "score")
        run_step(["scripts/score-opportunities.py", "--source-id", args.source, "--top", str(args.top)])
        update_pipeline_stage(state_dir, run_id, "score", completed=True)

        update_pipeline_stage(state_dir, run_id, "context")
        run_step(["scripts/build-summary-context.py", "--source-id", args.source, "--top", str(args.top)])
        update_pipeline_stage(state_dir, run_id, "context", completed=True)

        update_pipeline_stage(state_dir, run_id, "dossiers")
        run_step(["scripts/build-project-dossiers.py", "--source-id", args.source, "--top", str(args.top)])
        update_pipeline_stage(state_dir, run_id, "dossiers", completed=True)

        update_pipeline_stage(state_dir, run_id, "briefs")
        run_step(["scripts/build-briefs.py", "--source-id", args.source, "--top", str(min(args.top, 8))])
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
