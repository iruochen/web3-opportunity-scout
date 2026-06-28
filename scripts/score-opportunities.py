#!/usr/bin/env python3

from __future__ import annotations

import argparse
from typing import Any

from common import (
    ROOT,
    clamp,
    default_delivery_log,
    default_event_memory,
    default_watchlist,
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
    parser = argparse.ArgumentParser(description="Score merged opportunity projects and build ranked outputs.")
    parser.add_argument("--input", help="Optional path to merged JSON file")
    parser.add_argument("--source-id", help="Resolve the latest merged artifact for this source when --input is omitted")
    parser.add_argument("--top", type=int, default=15, help="Top ranked projects to include in markdown output")
    return parser.parse_args()


def extract_rank(project: dict[str, Any]) -> int | None:
    for signal in project.get("signals", []):
        text = str(signal)
        prefix = "RootData hot rank:"
        if text.startswith(prefix):
            try:
                return int(text.split(":", 1)[1].strip())
            except ValueError:
                return None
    return None


def compute_novelty(project: dict[str, Any], memory_projects: dict[str, Any]) -> float:
    previous = memory_projects.get(project["entity_key"], {})
    last_seen_at = previous.get("last_seen_at")
    if last_seen_at and last_seen_at == project.get("observed_at"):
        return 90.0
    seen_count = int(previous.get("seen_count", 0))
    if seen_count <= 1:
        return 90.0
    if seen_count == 2:
        return 70.0
    return 45.0


def compute_traction(project: dict[str, Any]) -> float:
    rank = extract_rank(project)
    confidence = float(project.get("confidence", 0.0))
    tags = project.get("tags", [])
    base = 52.0 + confidence * 20.0
    if rank is not None:
        base += max(0, 25 - min(rank, 25)) * 1.1
    base += min(len(tags), 4) * 2.5
    return clamp(base, 20.0, 95.0)


def compute_asymmetry(project: dict[str, Any], focus: dict[str, Any]) -> float:
    rank = extract_rank(project)
    tags = {str(tag).strip().lower() for tag in project.get("tags", [])}
    sectors = {str(item).strip().lower() for item in focus.get("sectors", [])}

    base = 55.0
    if rank is not None:
        base += max(0, 18 - min(rank, 18)) * 1.4
    if tags & sectors:
        base += 12.0
    if "infra" in tags or "devtools" in tags or "ai x crypto" in tags:
        base += 6.0
    return clamp(base, 25.0, 94.0)


def label_for_score(score: float) -> str:
    if score >= 85:
        return "high-priority follow"
    if score >= 70:
        return "strong candidate"
    if score >= 55:
        return "monitor"
    return "low priority for now"


def label_for_score_zh(score: float) -> str:
    if score >= 85:
        return "高优先级跟踪"
    if score >= 70:
        return "强候选"
    if score >= 55:
        return "建议观察"
    return "暂时低优先级"


def build_reasoning(project: dict[str, Any], novelty: float, traction: float, asymmetry: float) -> list[str]:
    reasons = []
    rank = extract_rank(project)
    if rank is not None:
        reasons.append(f"RootData hot list rank is {rank}.")
    if novelty >= 80:
        reasons.append("This project looks newly surfaced in current memory.")
    elif novelty >= 60:
        reasons.append("This project has some prior memory but still carries new value.")
    if traction >= 70:
        reasons.append("Current source signals suggest real attention or execution momentum.")
    if asymmetry >= 75:
        reasons.append("The upside may still be underpriced relative to current visibility.")
    return reasons


def build_markdown(scored_projects: list[dict[str, Any]], top_n: int) -> tuple[str, str]:
    raw_lines = ["# Raw Opportunities", ""]
    ranked_lines = ["# Ranked Opportunities", ""]

    for index, project in enumerate(scored_projects, start=1):
        raw_lines.append(f"## {index}. {project['project_name']}")
        raw_lines.append(f"- Score: {project['opportunity_score']}")
        raw_lines.append(f"- Label: {project['label']}")
        raw_lines.append(f"- URL: {project.get('project_url') or 'n/a'}")
        raw_lines.append(f"- Summary: {project.get('summary') or 'n/a'}")
        raw_lines.append(f"- Tags: {', '.join(project.get('tags', [])) or 'n/a'}")
        raw_lines.append(f"- Signals: {' | '.join(project.get('signals', [])) or 'n/a'}")
        raw_lines.append("")

    for index, project in enumerate(scored_projects[:top_n], start=1):
        ranked_lines.append(f"## {index}. {project['project_name']}")
        ranked_lines.append(f"- Opportunity score: {project['opportunity_score']} ({project['label']})")
        ranked_lines.append(
            f"- Breakdown: novelty {project['novelty_score']}, traction {project['traction_score']}, asymmetry {project['asymmetry_score']}"
        )
        ranked_lines.append(f"- Why now: {' '.join(project.get('reasoning', []))}")
        ranked_lines.append(f"- URL: {project.get('project_url') or 'n/a'}")
        ranked_lines.append("")

    return "\n".join(raw_lines).strip() + "\n", "\n".join(ranked_lines).strip() + "\n"


def update_watchlist_and_delivery(scored_projects: list[dict[str, Any]], state_dir, top_n: int) -> None:
    watchlist_path = state_dir / "watchlist.json"
    watchlist = read_json_file(watchlist_path, default_watchlist())
    watchlist["updated_at"] = utc_now_iso()
    watchlist["projects"] = [
        {
            "entity_key": project["entity_key"],
            "project_name": project["project_name"],
            "project_url": project.get("project_url"),
            "opportunity_score": project["opportunity_score"],
            "label": project["label"],
            "summary": project.get("summary"),
            "updated_at": utc_now_iso(),
        }
        for project in scored_projects[:top_n]
    ]
    write_json_file(watchlist_path, watchlist)

    delivery_path = state_dir / "delivery-log.json"
    delivery_log = read_json_file(delivery_path, default_delivery_log())
    delivery_log["updated_at"] = utc_now_iso()
    delivery_log.setdefault("deliveries", []).append(
        {
            "delivery_type": "ranked_opportunities_build",
            "created_at": utc_now_iso(),
            "project_count": min(top_n, len(scored_projects)),
            "entity_keys": [project["entity_key"] for project in scored_projects[:top_n]],
        }
    )
    delivery_log["deliveries"] = delivery_log["deliveries"][-200:]
    write_json_file(delivery_path, delivery_log)


def main() -> int:
    args = parse_args()
    config, _ = load_effective_yaml("config.yaml", "config.example.yaml")
    output_dir = output_dir_from_config(config)
    state_dir = state_dir_from_config(config)
    ensure_dir(output_dir / "scored")

    if args.input:
        input_path = ROOT / args.input
    elif args.source_id:
        input_path = latest_json_file_for_source(output_dir / "merged", args.source_id)
    else:
        input_path = latest_json_file(output_dir / "merged")
    merged_artifact = read_json_file(input_path, {})
    projects = merged_artifact.get("projects", [])
    memory = read_json_file(state_dir / "event-memory.json", default_event_memory())
    memory_projects = memory.get("projects", {})
    focus = config.get("focus", {})

    scored_projects: list[dict[str, Any]] = []
    for project in projects:
        novelty = round(compute_novelty(project, memory_projects), 1)
        traction = round(compute_traction(project), 1)
        asymmetry = round(compute_asymmetry(project, focus), 1)
        score = round(novelty * 0.35 + traction * 0.40 + asymmetry * 0.25, 1)
        label = label_for_score(score)
        scored_projects.append(
            {
                "entity_key": project["entity_key"],
                "project_name": project.get("canonical_name"),
                "project_url": project.get("project_url"),
                "summary": project.get("summary"),
                "tags": project.get("tags", []),
                "signals": project.get("signals", []),
                "novelty_score": novelty,
                "traction_score": traction,
                "asymmetry_score": asymmetry,
                "opportunity_score": score,
                "label": label,
                "reasoning": build_reasoning(project, novelty, traction, asymmetry),
                "source_ids": project.get("source_ids", []),
                "observed_at": project.get("observed_at"),
            }
        )

    scored_projects.sort(key=lambda item: (-item["opportunity_score"], item["project_name"].lower()))
    scored_path = output_dir / "scored" / f"{input_path.stem.replace('-merged', '')}-scored.json"
    write_json_file(
        scored_path,
        {
            "scored_at": utc_now_iso(),
            "input_merged": str(input_path.relative_to(ROOT)),
            "project_count": len(scored_projects),
            "projects": scored_projects,
        },
    )

    raw_md, ranked_md = build_markdown(scored_projects, args.top)
    (output_dir / "raw-opportunities.md").write_text(raw_md, encoding="utf-8")
    (output_dir / "ranked-opportunities.md").write_text(ranked_md, encoding="utf-8")
    update_watchlist_and_delivery(scored_projects, state_dir, args.top)

    print(f"PASS  Scored projects: {scored_path.relative_to(ROOT)}")
    print(f"PASS  Ranked markdown: {(output_dir / 'ranked-opportunities.md').relative_to(ROOT)}")
    print(f"PASS  Watchlist entries: {min(args.top, len(scored_projects))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
