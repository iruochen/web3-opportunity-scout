#!/usr/bin/env python3

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

from common import (
    ROOT,
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
    parser = argparse.ArgumentParser(description="Build Telegram-friendly opportunity digests.")
    parser.add_argument("--input", help="Optional context JSON path")
    parser.add_argument("--source-id", default="combined_market_scan")
    parser.add_argument("--mode", choices=["intraday", "early"], default="intraday")
    parser.add_argument("--top", type=int, default=None)
    return parser.parse_args()


def compact_text(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def link_for(project: dict[str, Any]) -> str:
    return str(
        project.get("rootdata_url")
        or project.get("detail_url")
        or project.get("website_url")
        or project.get("project_url")
        or "n/a"
    )


def unavailable_source_line(state_dir: Path) -> str | None:
    artifact = read_json_file(state_dir / "source-status.json", {})
    sources = artifact.get("sources", {})
    if not isinstance(sources, dict):
        return None
    unavailable: list[str] = []
    for source_id, status in sorted(sources.items()):
        if isinstance(status, dict) and not bool(status.get("available", True)):
            unavailable.append(f"{source_id} ❌ {status.get('reason', 'unavailable')}")
    if not unavailable:
        return None
    return "数据源状态: " + " / ".join(unavailable)


def source_count(project: dict[str, Any]) -> int:
    values = project.get("source_ids", [])
    return len(values) if isinstance(values, list) else 0


def has_funding(project: dict[str, Any]) -> bool:
    return bool(project.get("funding_rounds") or project.get("funding_signals") or project.get("investors"))


def has_participation(project: dict[str, Any]) -> bool:
    fields = [
        project.get("actionability_level"),
        " ".join(project.get("participation_angle_zh", []) if isinstance(project.get("participation_angle_zh"), list) else []),
        " ".join(project.get("participation_signals", []) if isinstance(project.get("participation_signals"), list) else []),
    ]
    text = " ".join(str(item or "") for item in fields).lower()
    return any(token in text for token in ("executable", "waitlist", "testnet", "quest", "points", "测试网", "任务", "积分", "候补"))


def select_intraday(projects: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for project in projects:
        if float(project.get("score") or 0.0) < 65.0:
            continue
        if not has_participation(project) and str(project.get("actionability_level")) != "researchable":
            continue
        selected.append(project)
        if len(selected) >= limit:
            break
    return selected


def select_early(projects: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for project in projects:
        token_status = str(project.get("token_status") or "")
        tier = str(project.get("opportunity_tier") or "")
        if token_status != "pre_token_likely":
            continue
        if not has_funding(project):
            continue
        if "Tier-1" not in tier and source_count(project) < 2 and float(project.get("score") or 0.0) < 80.0:
            continue
        selected.append(project)
        if len(selected) >= limit:
            break
    return selected


def tier_stars(project: dict[str, Any]) -> str:
    tier = str(project.get("opportunity_tier") or "")
    if "Tier-1" in tier:
        return "⭐️⭐️⭐️"
    if "Tier-2" in tier:
        return "⭐️⭐️"
    return "⭐️"


def render_intraday(projects: list[dict[str, Any]], state_dir: Path) -> str:
    selected = select_intraday(projects, 10)
    if not selected:
        return ""
    now = datetime.now().strftime("%H:%M")
    lines = [f"⚡️ 盘中扫描 · {now}"]
    status_line = unavailable_source_line(state_dir)
    if status_line:
        lines.append(status_line)
    for project in selected:
        investors = ", ".join(str(item) for item in project.get("investors", [])[:2]) if isinstance(project.get("investors"), list) else ""
        angle = compact_text(" / ".join(project.get("participation_angle_zh", [])[:1]), 46) if isinstance(project.get("participation_angle_zh"), list) else "等官方入口"
        thesis = compact_text(" ".join(project.get("opportunity_thesis_zh", [])[:1]), 48) if isinstance(project.get("opportunity_thesis_zh"), list) else compact_text(project.get("summary"), 48)
        lines.append(f"• {project.get('project_name')}｜{thesis}")
        lines.append(f"  投资方:{investors or '待核'}｜参与:{angle}｜{link_for(project)}")
    return "\n".join(lines).strip() + "\n"


def render_early(projects: list[dict[str, Any]], state_dir: Path) -> str:
    selected = select_early(projects, 8)
    if not selected:
        return ""
    today = datetime.now().strftime("%m.%d")
    lines = [f"🎯 早期项目机会卡 · {today}"]
    status_line = unavailable_source_line(state_dir)
    if status_line:
        lines.append(status_line)
    for project in selected:
        tags = " / ".join(str(item) for item in project.get("tags", [])[:3])
        funding = project.get("funding_rounds", [])
        first_round = funding[0] if isinstance(funding, list) and funding and isinstance(funding[0], dict) else {}
        round_text = " / ".join(str(first_round.get(key) or "").strip() for key in ("round", "amount") if str(first_round.get(key) or "").strip()) or "融资已确认"
        investors = ", ".join(str(item) for item in project.get("investors", [])[:3]) if isinstance(project.get("investors"), list) else ""
        thesis = compact_text(" ".join(project.get("opportunity_thesis_zh", [])[:1]), 56)
        angle = compact_text(" / ".join(project.get("participation_angle_zh", [])[:1]), 56)
        lines.extend(
            [
                f"{tier_stars(project)} {project.get('project_name')}（{project.get('opportunity_tier')}）",
                f"💡 {thesis}",
                f"🏷️ {tags or '待核'}",
                f"💰 {round_text} {investors}".strip(),
                f"🔍 验证:{source_count(project)}源｜pre-token:{project.get('token_status')}",
                f"🔗 {angle}｜{link_for(project)}",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    args = parse_args()
    config, _ = load_effective_yaml("config.yaml", "config.example.yaml")
    output_dir = output_dir_from_config(config)
    state_dir = state_dir_from_config(config)
    ensure_dir(output_dir / "telegram")
    if args.input:
        input_path = ROOT / args.input
    elif args.source_id:
        input_path = latest_json_file_for_source(output_dir / "context", args.source_id)
    else:
        input_path = latest_json_file(output_dir / "context")
    artifact = read_json_file(input_path, {})
    projects = [item for item in artifact.get("projects", []) if isinstance(item, dict)]
    if args.top is not None:
        projects = projects[: args.top]
    text = render_intraday(projects, state_dir) if args.mode == "intraday" else render_early(projects, state_dir)
    output_path = output_dir / "telegram" / f"latest-{args.mode}.txt"
    output_path.write_text(text, encoding="utf-8")
    dated_path = output_dir / "telegram" / f"{datetime.now().strftime('%Y-%m-%d')}-{args.mode}.txt"
    dated_path.write_text(text, encoding="utf-8")
    write_json_file(
        output_dir / "telegram" / f"latest-{args.mode}.json",
        {
            "built_at": utc_now_iso(),
            "mode": args.mode,
            "input_context": str(input_path.relative_to(ROOT)),
            "silent": not bool(text.strip()),
            "output_text": str(output_path.relative_to(ROOT)),
        },
    )
    if text.strip():
        print(f"PASS  Telegram digest: {output_path.relative_to(ROOT)}")
    else:
        print("SILENT  No Telegram digest candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
