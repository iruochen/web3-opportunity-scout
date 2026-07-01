#!/usr/bin/env python3

from __future__ import annotations

import argparse
from typing import Any

from common import (
    ROOT,
    ensure_dir,
    infer_opportunity_thesis,
    infer_participation_angle,
    infer_priority_checks,
    infer_validation_sources,
    is_established_project,
    latest_json_file,
    latest_json_file_for_source,
    load_effective_yaml,
    output_dir_from_config,
    project_actionability_score,
    project_funding_evidence,
    project_strong_participation_signals,
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
    summary = project.get("summary", "")
    signals = project.get("signals", [])[:4]
    return {
        "entity_key": project["entity_key"],
        "project_name": project["project_name"],
        "project_url": project.get("project_url"),
        "website_url": project.get("website_url"),
        "x_url": project.get("x_url"),
        "rootdata_url": project.get("rootdata_url"),
        "detail_url": project.get("detail_url"),
        "summary": summary,
        "score": project.get("opportunity_score"),
        "label": project.get("label"),
        "opportunity_tier": project.get("opportunity_tier"),
        "token_status": project.get("token_status"),
        "stage": project.get("stage"),
        "actionability_level": project.get("actionability_level"),
        "source_ids": source_ids,
        "participation_signals": project.get("participation_signals", []),
        "builder_signals": project.get("builder_signals", []),
        "supporting_signals": signals,
        "tags": tags[:6],
        "founded": project.get("founded"),
        "team": project.get("team", []),
        "investors": project.get("investors", []),
        "funding_rounds": project.get("funding_rounds", []),
        "funding_signals": project.get("funding_signals", []),
        "news_links": project.get("news_links", []),
        "opportunity_thesis": infer_opportunity_thesis(project, locale="en"),
        "opportunity_thesis_zh": infer_opportunity_thesis(project, locale="zh"),
        "participation_angle": infer_participation_angle(project, locale="en"),
        "participation_angle_zh": infer_participation_angle(project, locale="zh"),
        "validation_sources": infer_validation_sources(project, locale="en"),
        "validation_sources_zh": infer_validation_sources(project, locale="zh"),
        "priority_checks": infer_priority_checks(project, locale="en"),
        "priority_checks_zh": infer_priority_checks(project, locale="zh"),
        "known_state": {
            "already_in_watchlist": bool(watch),
            "watchlist_score": watch.get("opportunity_score"),
            "last_updated_at": watch.get("updated_at"),
        },
    }


def should_include_in_brief(project: dict[str, Any]) -> bool:
    name = str(project.get("project_name", "")).strip()
    if is_established_project(name):
        return False
    tier = str(project.get("opportunity_tier") or "")
    if tier.startswith("Rejected"):
        return False
    actionability = project_actionability_score(project)
    funding = project_funding_evidence(project)
    strong_participation = project_strong_participation_signals(project)
    website_url = str(project.get("website_url") or "").strip()
    x_url = str(project.get("x_url") or "").strip()
    if actionability < 24 and not funding and not strong_participation:
        return False
    if len(project.get("source_ids", [])) == 1 and "surf_project_ai_news" in project.get("source_ids", []) and (not strong_participation or (not website_url and not x_url)):
        return False
    if len(project.get("source_ids", [])) == 1 and "github_trending_builders" in project.get("source_ids", []) and "/" in name and actionability < 28:
        return False
    return True


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

    filtered_projects = [project for project in projects if should_include_in_brief(project)]
    selected = [build_context_item(project, watchlist_map) for project in filtered_projects[: args.top]]
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
