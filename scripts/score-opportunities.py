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
    is_established_project,
    latest_json_file,
    latest_json_file_for_source,
    load_effective_yaml,
    output_dir_from_config,
    project_actionability_score,
    project_builder_signals,
    project_funding_evidence,
    project_negative_signals,
    project_participation_signals,
    project_stage,
    project_strong_participation_signals,
    project_token_status,
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
    seen_count = int(previous.get("seen_count", 0))
    first_seen_at = previous.get("first_seen_at")
    last_seen_at = previous.get("last_seen_at")
    if seen_count <= 1:
        return 90.0
    if first_seen_at and first_seen_at == project.get("observed_at"):
        return 88.0
    if last_seen_at and last_seen_at != project.get("observed_at"):
        return 62.0
    if seen_count == 2:
        return 68.0
    return 38.0


def compute_traction(project: dict[str, Any]) -> float:
    rank = extract_rank(project)
    confidence = float(project.get("confidence", 0.0))
    tags = project.get("tags", [])
    participation = project_participation_signals(project)
    strong_participation = project_strong_participation_signals(project)
    funding = project_funding_evidence(project)
    builder = project_builder_signals(project)
    token_status = project_token_status(project)
    negative = project_negative_signals(project)
    base = 38.0 + confidence * 24.0
    if rank is not None:
        base += max(0, 20 - min(rank, 20)) * 0.35
    base += min(len(tags), 4) * 2.5
    base += min(len(strong_participation), 3) * 8.0
    base += max(0, min(len(participation) - len(strong_participation), 2)) * 2.0
    base += min(len(builder), 3) * 6.0
    if funding:
        base += 10.0
    if token_status == "pre_token_likely":
        base += 8.0
    elif token_status == "listed_or_established":
        base -= 28.0
    if negative:
        base -= 14.0
    return clamp(base, 20.0, 95.0)


def compute_asymmetry(project: dict[str, Any], focus: dict[str, Any]) -> float:
    rank = extract_rank(project)
    tags = {str(tag).strip().lower() for tag in project.get("tags", [])}
    sectors = {str(item).strip().lower() for item in focus.get("sectors", [])}
    participation = project_participation_signals(project)
    strong_participation = project_strong_participation_signals(project)
    funding = project_funding_evidence(project)
    builder = project_builder_signals(project)
    token_status = project_token_status(project)
    source_count = len(project.get("source_ids", []))

    base = 42.0
    if rank is not None:
        base += max(0, 18 - min(rank, 18)) * 0.4
    if tags & sectors:
        base += 12.0
    if "infra" in tags or "devtools" in tags or "ai x crypto" in tags:
        base += 6.0
    if strong_participation:
        base += 18.0
    elif participation:
        base += 6.0
    if funding:
        base += 10.0
    if builder:
        base += 10.0
    if token_status == "pre_token_likely":
        base += 14.0
    elif token_status == "token_live":
        base -= 12.0
    elif token_status == "listed_or_established":
        base -= 30.0
    if source_count >= 2:
        base += 8.0 + min(source_count - 2, 2) * 3.0
    return clamp(base, 25.0, 94.0)


def compute_viability(project: dict[str, Any]) -> float:
    actionability = project_actionability_score(project)
    negative = project_negative_signals(project)
    token_status = project_token_status(project)
    base = actionability
    if is_established_project(str(project.get("canonical_name") or project.get("project_name") or "")):
        base -= 35.0
    if token_status == "pre_token_likely":
        base += 10.0
    elif token_status == "token_live":
        base -= 18.0
    elif token_status == "listed_or_established":
        base -= 35.0
    if negative:
        base -= 18.0
    return clamp(base, 0.0, 95.0)


def label_for_score(score: float, risk: dict[str, Any] | None = None) -> str:
    risk = risk or {}
    tier1 = float(risk.get("tier1_score", 84))
    strong = float(risk.get("strong_candidate_score", 80))
    minimum = float(risk.get("min_opportunity_score", 72))
    if score >= tier1:
        return "high-priority follow"
    if score >= strong:
        return "strong candidate"
    if score >= minimum:
        return "monitor"
    return "low priority for now"


def label_for_score_zh(score: float, risk: dict[str, Any] | None = None) -> str:
    risk = risk or {}
    tier1 = float(risk.get("tier1_score", 84))
    strong = float(risk.get("strong_candidate_score", 80))
    minimum = float(risk.get("min_opportunity_score", 72))
    if score >= tier1:
        return "高优先级跟踪"
    if score >= strong:
        return "强候选"
    if score >= minimum:
        return "建议观察"
    return "暂时低优先级"


def tier_for_project(score: float, project: dict[str, Any], risk: dict[str, Any]) -> str:
    token_status = project_token_status(project)
    strong_participation = project_strong_participation_signals(project)
    builder = project_builder_signals(project)
    funding = project_funding_evidence(project)
    tier1 = float(risk.get("tier1_score", 84))
    strong = float(risk.get("strong_candidate_score", 80))
    minimum = float(risk.get("min_opportunity_score", 72))
    if score >= tier1 and token_status != "listed_or_established" and strong_participation:
        return "Tier-1 actionable"
    if score >= strong and token_status in {"pre_token_likely", "unknown"} and (strong_participation or funding or builder):
        return "Tier-2 research now"
    if score >= minimum:
        return "Tier-3 monitor"
    return "Rejected/low priority"


def actionability_level(project: dict[str, Any]) -> str:
    if project_strong_participation_signals(project):
        return "executable"
    if project_participation_signals(project) or project_builder_signals(project):
        return "researchable"
    if project_funding_evidence(project):
        return "watch_for_entry"
    return "unclear"


def build_reasoning(project: dict[str, Any], novelty: float, traction: float, asymmetry: float) -> list[str]:
    reasons = []
    participation = project_participation_signals(project)
    strong_participation = project_strong_participation_signals(project)
    funding = project_funding_evidence(project)
    source_count = len(project.get("source_ids", []))
    negative = project_negative_signals(project)
    rank = extract_rank(project)
    if funding:
        reasons.append("Funding evidence is visible and can translate into near-term product or incentive rollout.")
    if strong_participation:
        reasons.append("Participation cues are already visible: " + ", ".join(strong_participation[:3]) + ".")
    builder = project_builder_signals(project)
    if builder:
        reasons.append("Builder signal is present: " + ", ".join(builder[:3]) + ".")
    token_status = project_token_status(project)
    if token_status == "pre_token_likely":
        reasons.append("Token status looks pre-token or not-yet-confirmed, which preserves upside if access is real.")
    elif token_status in {"token_live", "listed_or_established"}:
        reasons.append(f"Token status is {token_status}, so this is penalized versus early pre-token opportunities.")
    if source_count >= 2:
        reasons.append(f"This project is supported by {source_count} source types rather than a single discovery feed.")
    if rank is not None and not funding and not participation:
        reasons.append(f"RootData hot list rank is {rank}.")
    if novelty >= 80:
        reasons.append("This project looks newly surfaced in current memory.")
    elif novelty >= 60:
        reasons.append("This project has some prior memory but still carries new value.")
    if traction >= 70:
        reasons.append("Current source signals suggest real attention or execution momentum.")
    if asymmetry >= 75:
        reasons.append("The upside may still be underpriced relative to current visibility.")
    if negative:
        reasons.append("Some current chatter looks noisy, so actionability should be confirmed before upgrading conviction.")
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
        ranked_lines.append(f"- Tier: {project['opportunity_tier']}")
        ranked_lines.append(f"- Token status: {project['token_status']} | Stage: {project['stage']} | Actionability: {project['actionability_level']}")
        ranked_lines.append(
            f"- Breakdown: novelty {project['novelty_score']}, traction {project['traction_score']}, asymmetry {project['asymmetry_score']}, viability {project['viability_score']}"
        )
        ranked_lines.append(f"- Why now: {' '.join(project.get('reasoning', []))}")
        ranked_lines.append(f"- URL: {project.get('project_url') or 'n/a'}")
        ranked_lines.append("")

    return "\n".join(raw_lines).strip() + "\n", "\n".join(ranked_lines).strip() + "\n"


def eligible_projects(scored_projects: list[dict[str, Any]], risk: dict[str, Any]) -> list[dict[str, Any]]:
    minimum = float(risk.get("min_opportunity_score", 72))
    return [project for project in scored_projects if float(project.get("opportunity_score", 0.0)) >= minimum]


def update_watchlist_and_delivery(scored_projects: list[dict[str, Any]], state_dir, top_n: int, risk: dict[str, Any]) -> None:
    selected_projects = eligible_projects(scored_projects, risk)[:top_n]
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
            "opportunity_tier": project.get("opportunity_tier"),
            "token_status": project.get("token_status"),
            "stage": project.get("stage"),
            "actionability_level": project.get("actionability_level"),
            "summary": project.get("summary"),
            "updated_at": utc_now_iso(),
        }
        for project in selected_projects
    ]
    write_json_file(watchlist_path, watchlist)

    delivery_path = state_dir / "delivery-log.json"
    delivery_log = read_json_file(delivery_path, default_delivery_log())
    delivery_log["updated_at"] = utc_now_iso()
    delivery_log.setdefault("deliveries", []).append(
        {
            "delivery_type": "ranked_opportunities_build",
            "created_at": utc_now_iso(),
            "project_count": len(selected_projects),
            "entity_keys": [project["entity_key"] for project in selected_projects],
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
    risk = config.get("risk", {}) if isinstance(config.get("risk", {}), dict) else {}

    scored_projects: list[dict[str, Any]] = []
    for project in projects:
        novelty = round(compute_novelty(project, memory_projects), 1)
        traction = round(compute_traction(project), 1)
        asymmetry = round(compute_asymmetry(project, focus), 1)
        viability = round(compute_viability(project), 1)
        score = round(novelty * 0.16 + traction * 0.26 + asymmetry * 0.24 + viability * 0.34, 1)
        label = label_for_score(score, risk)
        token_status = project_token_status(project)
        stage = project_stage(project)
        tier = tier_for_project(score, project, risk)
        scored_projects.append(
            {
                "entity_key": project["entity_key"],
                "project_name": project.get("canonical_name"),
                "project_url": project.get("project_url"),
                "website_url": project.get("website_url"),
                "x_url": project.get("x_url"),
                "rootdata_url": project.get("rootdata_url"),
                "detail_url": project.get("detail_url"),
                "summary": project.get("summary"),
                "tags": project.get("tags", []),
                "signals": project.get("signals", []),
                "founded": project.get("founded"),
                "team": project.get("team", []),
                "investors": project.get("investors", []),
                "funding_rounds": project.get("funding_rounds", []),
                "funding_signals": project.get("funding_signals", []),
                "news_links": project.get("news_links", []),
                "novelty_score": novelty,
                "traction_score": traction,
                "asymmetry_score": asymmetry,
                "viability_score": viability,
                "opportunity_score": score,
                "label": label,
                "label_zh": label_for_score_zh(score, risk),
                "opportunity_tier": tier,
                "token_status": token_status,
                "stage": stage,
                "actionability_level": actionability_level(project),
                "participation_signals": project_participation_signals(project),
                "builder_signals": project_builder_signals(project),
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
    update_watchlist_and_delivery(scored_projects, state_dir, args.top, risk)

    print(f"PASS  Scored projects: {scored_path.relative_to(ROOT)}")
    print(f"PASS  Ranked markdown: {(output_dir / 'ranked-opportunities.md').relative_to(ROOT)}")
    print(f"PASS  Watchlist entries: {min(args.top, len(eligible_projects(scored_projects, risk)))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
