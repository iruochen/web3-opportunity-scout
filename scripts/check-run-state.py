#!/usr/bin/env python3

from __future__ import annotations

from common import ROOT, default_run_state, load_effective_yaml, read_json_file


def main() -> int:
    config, config_path = load_effective_yaml("config.yaml", "config.example.yaml")
    state_dir = ROOT / str(config.get("profile", {}).get("state_dir", "state"))
    run_state_path = state_dir / "run-state.json"
    run_state = read_json_file(run_state_path, default_run_state())

    runs = run_state.get("runs", [])
    sources = run_state.get("sources", {})

    print(f"Using config: {config_path.relative_to(ROOT)}")
    print(f"Run state path: {run_state_path.relative_to(ROOT)}")
    print(f"Run state version: {run_state.get('version')}")
    print(f"Updated at: {run_state.get('updated_at')}")
    print(f"Active run: {run_state.get('active_run')}")
    print(f"Last completed run: {run_state.get('last_completed_run')}")
    print(f"Recorded runs: {len(runs)}")
    print(f"Tracked sources: {len(sources)}")

    if sources:
        print("\nSources:")
        for source_id in sorted(sources):
            source_state = sources[source_id]
            last_status = source_state.get("last_status", "unknown")
            last_fetch_at = source_state.get("last_fetch_at", "n/a")
            print(f"- {source_id}: status={last_status}, last_fetch_at={last_fetch_at}")

    if runs:
        print("\nRecent runs:")
        for run in runs[-5:]:
            run_id = run.get("run_id")
            status = run.get("status")
            source_id = run.get("source_id")
            current_stage = run.get("current_stage")
            completed = ",".join(run.get("completed_stages", []))
            print(f"- {run_id}: status={status}, source={source_id}, current_stage={current_stage}, completed=[{completed}]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
