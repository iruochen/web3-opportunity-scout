#!/usr/bin/env python3

from __future__ import annotations

import argparse
from collections import defaultdict
from typing import Any

from common import (
    default_event_memory,
    default_project_dossiers,
    ensure_dir,
    load_effective_yaml,
    output_dir_from_config,
    read_json_file,
    state_dir_from_config,
    utc_now_iso,
    write_json_file,
    latest_json_file,
    ROOT,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge normalized opportunity records into canonical project entities.")
    parser.add_argument("--input", help="Optional path to normalized JSON file")
    parser.add_argument("--source-id", default="rootdata_projects", help="Source id to annotate during merge")
    return parser.parse_args()


def pick_latest_observed(records: list[dict[str, Any]]) -> str | None:
    timestamps = [record.get("observed_at") for record in records if record.get("observed_at")]
    return sorted(timestamps)[-1] if timestamps else None


def merge_group(entity_key: str, records: list[dict[str, Any]], source_id: str) -> dict[str, Any]:
    primary = records[0]
    tags: list[str] = []
    signals: list[str] = []
    aliases: list[str] = []
    seen_ids: list[str] = []

    for record in records:
        seen_ids.append(str(record.get("id")))
        name = str(record.get("project_name", "")).strip()
        if name and name not in aliases:
            aliases.append(name)
        for tag in record.get("tags", []):
            text = str(tag).strip()
            if text and text not in tags:
                tags.append(text)
        for signal in record.get("signals", []):
            text = str(signal).strip()
            if text and text not in signals:
                signals.append(text)

    return {
        "entity_key": entity_key,
        "canonical_name": primary.get("project_name"),
        "aliases": aliases,
        "source_ids": sorted({str(record.get("source_id")) for record in records}),
        "project_url": primary.get("project_url"),
        "summary": primary.get("summary"),
        "category": primary.get("category", "discovery"),
        "chains": primary.get("chains", []),
        "tags": tags,
        "signals": signals,
        "confidence": max(float(record.get("confidence", 0.0)) for record in records),
        "observed_at": pick_latest_observed(records),
        "record_count": len(records),
        "records": records,
        "record_ids": seen_ids,
        "status": "merged",
        "source_type": primary.get("source_type"),
        "source_id": source_id,
    }


def update_state_files(merged_projects: list[dict[str, Any]], state_dir) -> None:
    event_memory_path = state_dir / "event-memory.json"
    event_memory = read_json_file(event_memory_path, default_event_memory())
    event_memory["updated_at"] = utc_now_iso()

    projects = dict(event_memory.get("projects", {}))
    events = list(event_memory.get("events", []))
    for project in merged_projects:
        entity_key = project["entity_key"]
        project_state = dict(projects.get(entity_key, {}))
        first_seen_at = project_state.get("first_seen_at") or project.get("observed_at") or utc_now_iso()
        seen_count = int(project_state.get("seen_count", 0)) + 1
        project_state.update(
            {
                "entity_key": entity_key,
                "project_name": project.get("canonical_name"),
                "project_url": project.get("project_url"),
                "first_seen_at": first_seen_at,
                "last_seen_at": project.get("observed_at"),
                "seen_count": seen_count,
                "last_source_ids": project.get("source_ids", []),
                "last_tags": project.get("tags", []),
            }
        )
        projects[entity_key] = project_state
        events.append(
            {
                "event_type": "entity_merged",
                "entity_key": entity_key,
                "observed_at": project.get("observed_at"),
                "record_count": project.get("record_count"),
                "source_ids": project.get("source_ids", []),
            }
        )

    event_memory["projects"] = projects
    event_memory["events"] = events[-1000:]
    write_json_file(event_memory_path, event_memory)

    dossiers_path = state_dir / "project-dossiers.json"
    dossiers = read_json_file(dossiers_path, default_project_dossiers())
    dossiers["updated_at"] = utc_now_iso()
    existing = {item.get("entity_key"): item for item in dossiers.get("projects", []) if isinstance(item, dict)}
    for project in merged_projects:
        existing[project["entity_key"]] = {
            "entity_key": project["entity_key"],
            "project_name": project.get("canonical_name"),
            "project_url": project.get("project_url"),
            "summary": project.get("summary"),
            "tags": project.get("tags", []),
            "signals": project.get("signals", []),
            "last_observed_at": project.get("observed_at"),
            "source_ids": project.get("source_ids", []),
        }
    dossiers["projects"] = sorted(existing.values(), key=lambda item: str(item.get("project_name", "")).lower())
    write_json_file(dossiers_path, dossiers)


def main() -> int:
    args = parse_args()
    config, _ = load_effective_yaml("config.yaml", "config.example.yaml")
    output_dir = output_dir_from_config(config)
    state_dir = state_dir_from_config(config)
    ensure_dir(output_dir / "merged")

    if args.input:
        input_path = ROOT / args.input
    else:
        filtered_dir = output_dir / "filtered"
        input_path = latest_json_file(filtered_dir) if filtered_dir.exists() else latest_json_file(output_dir / "normalized")
    normalized_artifact = read_json_file(input_path, {})
    records = normalized_artifact.get("records", [])

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if not isinstance(record, dict):
            continue
        grouped[str(record.get("entity_key", record.get("id")))].append(record)

    merged_projects = [
        merge_group(entity_key, group_records, args.source_id)
        for entity_key, group_records in sorted(grouped.items())
    ]

    output_path = output_dir / "merged" / f"{input_path.stem.replace('-normalized', '')}-merged.json"
    write_json_file(
        output_path,
        {
            "source_id": args.source_id,
            "merged_at": utc_now_iso(),
            "input_normalized": str(input_path.relative_to(ROOT)),
            "project_count": len(merged_projects),
            "projects": merged_projects,
        },
    )

    update_state_files(merged_projects, state_dir)
    print(f"PASS  Merged projects: {output_path.relative_to(ROOT)}")
    print(f"PASS  Canonical entities: {len(merged_projects)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
