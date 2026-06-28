#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path

from common import (
    ROOT,
    default_delivery_log,
    default_event_memory,
    default_project_dossiers,
    default_run_state,
    default_watchlist,
    ensure_dir,
    load_effective_yaml,
    read_json_file,
    write_json_file,
)


STATE_FILES = {
    "run-state.json": default_run_state,
    "event-memory.json": default_event_memory,
    "watchlist.json": default_watchlist,
    "delivery-log.json": default_delivery_log,
    "project-dossiers.json": default_project_dossiers,
}


def state_dir_from_config(config: dict) -> Path:
    profile = config.get("profile", {})
    state_dir = profile.get("state_dir", "state")
    return ROOT / str(state_dir)


def main() -> int:
    config, config_path = load_effective_yaml("config.yaml", "config.example.yaml")
    state_dir = ensure_dir(state_dir_from_config(config))
    ensure_dir(ROOT / str(config.get("profile", {}).get("cache_dir", "cache")))
    ensure_dir(ROOT / str(config.get("profile", {}).get("output_dir", "output")))

    print(f"Using config: {config_path.relative_to(ROOT)}")
    print(f"Ensuring state directory: {state_dir.relative_to(ROOT)}")

    for filename, factory in STATE_FILES.items():
        path = state_dir / filename
        if path.exists():
            read_json_file(path, {})
            print(f"PASS  Existing state file is readable: {path.relative_to(ROOT)}")
            continue

        write_json_file(path, factory())
        print(f"PASS  Created state file: {path.relative_to(ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
