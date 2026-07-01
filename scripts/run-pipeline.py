#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

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
    utc_now_iso,
    write_json_file,
)


ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the current end-to-end opportunity pipeline.")
    parser.add_argument("--source", default="combined_market_scan", help="Source id defined in sources.yaml or combined_market_scan")
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


def source_preflight_status(source_id: str, source_def: dict[str, Any]) -> dict[str, Any]:
    adapter = resolve_source_adapter(source_id, source_def)
    script_path = ROOT / "scripts" / f"fetch-{adapter}.py"
    auth_cfg = source_def.get("auth", {})
    env_name = str(auth_cfg.get("env") or "").strip() if isinstance(auth_cfg, dict) else ""
    if env_name and not os.getenv(env_name):
        return {"source_id": source_id, "adapter": adapter, "available": False, "reason": f"missing_env:{env_name}"}
    if not script_path.exists():
        return {"source_id": source_id, "adapter": adapter, "available": False, "reason": f"missing_fetch_adapter:{script_path.name}"}
    return {"source_id": source_id, "adapter": adapter, "available": True, "reason": "ok"}


def write_source_status(state_dir: Path, statuses: dict[str, dict[str, Any]]) -> None:
    write_json_file(state_dir / "source-status.json", {"updated_at": utc_now_iso(), "sources": statuses})


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

            source_statuses: dict[str, dict[str, Any]] = {}
            runnable_sources: list[str] = []
            for source_id in child_sources:
                _, source_def = find_source_definition(sources_config, source_id)
                status = source_preflight_status(source_id, source_def)
                source_statuses[source_id] = status
                if status["available"]:
                    runnable_sources.append(source_id)
                else:
                    print(f"SKIP  {source_id}: {status['reason']}", flush=True)
            write_source_status(state_dir, source_statuses)
            if not runnable_sources:
                raise ValueError("No preflight-available adapter-backed sources are available for combined_market_scan")

            successful_sources: list[str] = []
            for child_source in runnable_sources:
                _, source_def = find_source_definition(sources_config, child_source)
                adapter = resolve_source_adapter(child_source, source_def)
                try:
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
                    successful_sources.append(child_source)
                    source_statuses[child_source] = {**source_statuses[child_source], "available": True, "reason": "ok"}
                    write_source_status(state_dir, source_statuses)
                except subprocess.CalledProcessError as exc:
                    source_statuses[child_source] = {
                        **source_statuses.get(child_source, {"source_id": child_source, "adapter": adapter}),
                        "available": False,
                        "reason": f"command_failed:{exc.returncode}",
                    }
                    write_source_status(state_dir, source_statuses)
                    if not bool(config.get("run", {}).get("skip_unavailable_sources", True)):
                        raise
                    print(f"SKIP  {child_source}: command failed with exit code {exc.returncode}", flush=True)
                    continue

            if not successful_sources:
                raise ValueError("All combined_market_scan child sources failed or were unavailable")
            include_args: list[str] = []
            for source_id in successful_sources:
                include_args.extend(["--include-source", source_id])

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

            update_pipeline_stage(state_dir, run_id, "telegram")
            run_step(["scripts/build-telegram-digest.py", "--source-id", args.source, "--mode", "intraday", "--top", str(args.top)])
            run_step(["scripts/build-telegram-digest.py", "--source-id", args.source, "--mode", "early", "--top", str(args.top)])
            update_pipeline_stage(state_dir, run_id, "telegram", completed=True)

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

        update_pipeline_stage(state_dir, run_id, "telegram")
        run_step(["scripts/build-telegram-digest.py", "--source-id", args.source, "--mode", "intraday", "--top", str(args.top)])
        run_step(["scripts/build-telegram-digest.py", "--source-id", args.source, "--mode", "early", "--top", str(args.top)])
        update_pipeline_stage(state_dir, run_id, "telegram", completed=True)

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
