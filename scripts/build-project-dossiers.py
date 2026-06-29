#!/usr/bin/env python3

from __future__ import annotations

import argparse
from typing import Any

from common import (
    ROOT,
    default_project_dossiers,
    ensure_dir,
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
    parser = argparse.ArgumentParser(description="Build richer project dossiers from summary context.")
    parser.add_argument("--input", help="Optional path to context JSON file")
    parser.add_argument("--source-id", help="Resolve the latest context artifact for this source when --input is omitted")
    parser.add_argument("--top", type=int, default=12, help="Number of projects to keep in dossiers")
    return parser.parse_args()


def dossier_from_context(project: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity_key": project["entity_key"],
        "project_name": project["project_name"],
        "project_url": project.get("project_url"),
        "website_url": project.get("website_url"),
        "x_url": project.get("x_url"),
        "summary": project.get("summary"),
        "score": project.get("score"),
        "label": project.get("label"),
        "tags": project.get("tags", []),
        "supporting_signals": project.get("supporting_signals", []),
        "founded": project.get("founded"),
        "team": project.get("team", []),
        "investors": project.get("investors", []),
        "funding_signals": project.get("funding_signals", []),
        "news_links": project.get("news_links", []),
        "opportunity_thesis": project.get("opportunity_thesis", []),
        "opportunity_thesis_zh": project.get("opportunity_thesis_zh", []),
        "participation_angle": project.get("participation_angle", []),
        "participation_angle_zh": project.get("participation_angle_zh", []),
        "validation_sources": project.get("validation_sources", []),
        "validation_sources_zh": project.get("validation_sources_zh", []),
        "priority_checks": project.get("priority_checks", []),
        "priority_checks_zh": project.get("priority_checks_zh", []),
        "known_state": project.get("known_state", {}),
        "updated_at": utc_now_iso(),
    }


def main() -> int:
    args = parse_args()
    config, _ = load_effective_yaml("config.yaml", "config.example.yaml")
    output_dir = output_dir_from_config(config)
    state_dir = state_dir_from_config(config)
    ensure_dir(output_dir)

    if args.input:
        input_path = ROOT / args.input
    elif args.source_id:
        input_path = latest_json_file_for_source(output_dir / "context", args.source_id)
    else:
        input_path = latest_json_file(output_dir / "context")
    context_artifact = read_json_file(input_path, {})
    projects = context_artifact.get("projects", [])[: args.top]
    dossiers = [dossier_from_context(project) for project in projects]

    output_path = output_dir / "project-dossiers.json"
    write_json_file(
        output_path,
        {
            "built_at": utc_now_iso(),
            "input_context": str(input_path.relative_to(ROOT)),
            "project_count": len(dossiers),
            "projects": dossiers,
        },
    )

    state_path = state_dir / "project-dossiers.json"
    state_artifact = read_json_file(state_path, default_project_dossiers())
    existing = {item.get("entity_key"): item for item in state_artifact.get("projects", []) if isinstance(item, dict)}
    for dossier in dossiers:
        existing[dossier["entity_key"]] = dossier

    state_artifact["updated_at"] = utc_now_iso()
    state_artifact["projects"] = sorted(existing.values(), key=lambda item: (-float(item.get("score", 0.0)), item.get("project_name", "").lower()))
    write_json_file(state_path, state_artifact)

    print(f"PASS  Project dossiers: {output_path.relative_to(ROOT)}")
    print(f"PASS  Dossiers updated in state: {state_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
