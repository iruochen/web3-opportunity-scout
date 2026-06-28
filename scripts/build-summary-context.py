#!/usr/bin/env python3

from __future__ import annotations

import argparse
from typing import Any

from common import (
    ROOT,
    ensure_dir,
    infer_participation_angle,
    infer_validation_sources,
    latest_json_file,
    latest_json_file_for_source,
    load_effective_yaml,
    output_dir_from_config,
    read_json_file,
    state_dir_from_config,
    utc_now_iso,
    write_json_file,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build compact summary context from scored opportunities.")
    parser.add_argument("--input", help="Optional path to scored JSON file")
    parser.add_argument("--source-id", help="Resolve the latest scored artifact for this source when --input is omitted")
    parser.add_argument("--top", type=int, default=12, help="Number of projects to include in compact context")
    return parser.parse_args()


def build_context_item(project: dict[str, Any], watchlist_map: dict[str, Any]) -> dict[str, Any]:
    watch = watchlist_map.get(project["entity_key"], {})
    tags = project.get("tags", [])
    source_ids = project.get("source_ids", [])
    return {
        "entity_key": project["entity_key"],
        "project_name": project["project_name"],
        "project_url": project.get("project_url"),
        "summary": project.get("summary"),
        "score": project.get("opportunity_score"),
        "label": project.get("label"),
        "supporting_signals": project.get("signals", [])[:4],
        "tags": tags[:6],
        "reasoning": project.get("reasoning", []),
        "participation_angle": infer_participation_angle(tags, project.get("summary", "")),
        "validation_sources": infer_validation_sources(tags, source_ids),
        "known_state": {
            "already_in_watchlist": bool(watch),
            "watchlist_score": watch.get("opportunity_score"),
            "last_updated_at": watch.get("updated_at"),
        },
        "follow_up_questions": [
            "Does this project show evidence beyond current hot-list visibility?",
            "Is there a concrete participation angle for the configured user profile?",
            "What source should be checked next for validation?"
        ],
    }


def main() -> int:
    args = parse_args()
    config, _ = load_effective_yaml("config.yaml", "config.example.yaml")
    output_dir = output_dir_from_config(config)
    state_dir = state_dir_from_config(config)
    ensure_dir(output_dir / "context")

    if args.input:
        input_path = ROOT / args.input
    elif args.source_id:
        input_path = latest_json_file_for_source(output_dir / "scored", args.source_id)
    else:
        input_path = latest_json_file(output_dir / "scored")
    scored_artifact = read_json_file(input_path, {})
    projects = scored_artifact.get("projects", [])
    watchlist = read_json_file(state_dir / "watchlist.json", {"projects": []})
    watchlist_map = {
        item.get("entity_key"): item
        for item in watchlist.get("projects", [])
        if isinstance(item, dict) and item.get("entity_key")
    }

    selected = [build_context_item(project, watchlist_map) for project in projects[: args.top]]
    output_path = output_dir / "context" / f"{input_path.stem.replace('-scored', '')}-context.json"
    write_json_file(
        output_path,
        {
            "built_at": utc_now_iso(),
            "input_scored": str(input_path.relative_to(ROOT)),
            "project_count": len(selected),
            "projects": selected,
        },
    )

    print(f"PASS  Summary context: {output_path.relative_to(ROOT)}")
    print(f"PASS  Context projects: {len(selected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
