#!/usr/bin/env python3

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from typing import Any

from common import (
    ROOT,
    ensure_dir,
    latest_json_file,
    load_effective_yaml,
    output_dir_from_config,
    read_json_file,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build user-facing opportunity briefs and project thesis files.")
    parser.add_argument("--input", help="Optional path to context JSON file")
    parser.add_argument("--top", type=int, default=8, help="Number of projects to include in the brief")
    return parser.parse_args()


def render_brief_en(projects: list[dict[str, Any]], focus: dict[str, Any]) -> str:
    lines = ["# Opportunity Brief", ""]
    lines.append(f"- Focus chains: {', '.join(focus.get('chains', [])) or 'global'}")
    lines.append(f"- Focus sectors: {', '.join(focus.get('sectors', [])) or 'general'}")
    lines.append("")
    lines.append("## Top Opportunities")
    lines.append("")
    for index, project in enumerate(projects, start=1):
        lines.append(f"### {index}. {project['project_name']}")
        lines.append(f"- Score: {project['score']} ({project['label']})")
        lines.append(f"- Why it matters: {' '.join(project.get('reasoning', []))}")
        lines.append(f"- Signals: {' | '.join(project.get('supporting_signals', [])) or 'n/a'}")
        lines.append(f"- Suggested next check: {project['follow_up_questions'][2]}")
        lines.append(f"- URL: {project.get('project_url') or 'n/a'}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def translate_reason_zh(reason: str) -> str:
    mapping = {
        "This project looks newly surfaced in current memory.": "这个项目在当前记忆里看起来是新近浮现出来的。",
        "Current source signals suggest real attention or execution momentum.": "当前来源信号显示它已经有了真实关注度或执行动能。",
        "The upside may still be underpriced relative to current visibility.": "相对于现在的可见度，它的上行空间可能仍然被低估。",
    }
    if reason in mapping:
        return mapping[reason]
    if reason.startswith("RootData hot list rank is "):
        rank = reason.removeprefix("RootData hot list rank is ").rstrip(".")
        return f"RootData 热榜当前排名第 {rank}。"
    return reason


def translate_question_zh(question: str) -> str:
    mapping = {
        "Does this project show evidence beyond current hot-list visibility?": "这个项目是否有超出热榜曝光之外的真实证据？",
        "Is there a concrete participation angle for the configured user profile?": "对于当前配置的用户画像，是否存在明确的参与角度？",
        "What source should be checked next for validation?": "下一步应该补查哪个来源来继续验证？",
    }
    return mapping.get(question, question)


def label_zh(label: str) -> str:
    mapping = {
        "high-priority follow": "高优先级跟踪",
        "strong candidate": "强候选",
        "monitor": "建议观察",
        "low priority for now": "暂时低优先级",
    }
    return mapping.get(label, label)


def render_brief_zh(projects: list[dict[str, Any]], focus: dict[str, Any]) -> str:
    lines = ["# 机会简报", ""]
    lines.append(f"- 关注链: {', '.join(focus.get('chains', [])) or 'global'}")
    lines.append(f"- 关注赛道: {', '.join(focus.get('sectors', [])) or 'general'}")
    lines.append("")
    lines.append("## 核心机会")
    lines.append("")
    for index, project in enumerate(projects, start=1):
        lines.append(f"### {index}. {project['project_name']}")
        lines.append(f"- 评分: {project['score']} ({label_zh(project['label'])})")
        lines.append(f"- 为什么值得看: {' '.join(translate_reason_zh(item) for item in project.get('reasoning', []))}")
        lines.append(f"- 关键线索: {' | '.join(project.get('supporting_signals', [])) or 'n/a'}")
        lines.append(f"- 下一步建议: {translate_question_zh(project['follow_up_questions'][2])}")
        lines.append(f"- 链接: {project.get('project_url') or 'n/a'}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_thesis_en(project: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {project['project_name']} Thesis",
            "",
            f"- Score: {project['score']} ({project['label']})",
            f"- URL: {project.get('project_url') or 'n/a'}",
            f"- Tags: {', '.join(project.get('tags', [])) or 'n/a'}",
            "",
            "## Why This Looks Early",
            "",
            f"{' '.join(project.get('reasoning', []))}",
            "",
            "## Supporting Signals",
            "",
            *[f"- {signal}" for signal in project.get("supporting_signals", [])],
            "",
            "## Suggested Validation",
            "",
            *[f"- {question}" for question in project.get("follow_up_questions", [])],
            "",
        ]
    ).strip() + "\n"


def render_thesis_zh(project: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {project['project_name']} 机会 Thesis",
            "",
            f"- 评分: {project['score']} ({label_zh(project['label'])})",
            f"- 链接: {project.get('project_url') or 'n/a'}",
            f"- 标签: {', '.join(project.get('tags', [])) or 'n/a'}",
            "",
            "## 为什么这可能还处于早期",
            "",
            f"{' '.join(translate_reason_zh(item) for item in project.get('reasoning', []))}",
            "",
            "## 支撑线索",
            "",
            *[f"- {signal}" for signal in project.get("supporting_signals", [])],
            "",
            "## 建议继续验证的问题",
            "",
            *[f"- {translate_question_zh(question)}" for question in project.get("follow_up_questions", [])],
            "",
        ]
    ).strip() + "\n"


def main() -> int:
    args = parse_args()
    config, _ = load_effective_yaml("config.yaml", "config.example.yaml")
    output_dir = output_dir_from_config(config)
    ensure_dir(output_dir / "briefs")
    ensure_dir(output_dir / "project-theses" / "en")
    ensure_dir(output_dir / "project-theses" / "zh")

    input_path = ROOT / args.input if args.input else latest_json_file(output_dir / "context")
    context_artifact = read_json_file(input_path, {})
    projects = context_artifact.get("projects", [])[: args.top]
    focus = config.get("focus", {})
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    brief_en = render_brief_en(projects, focus)
    brief_zh = render_brief_zh(projects, focus)
    (output_dir / "briefs" / f"{today}-brief.en.md").write_text(brief_en, encoding="utf-8")
    (output_dir / "briefs" / f"{today}-brief.zh.md").write_text(brief_zh, encoding="utf-8")
    (output_dir / "briefs" / "latest-brief.en.md").write_text(brief_en, encoding="utf-8")
    (output_dir / "briefs" / "latest-brief.zh.md").write_text(brief_zh, encoding="utf-8")

    for project in projects:
        entity_key = project["entity_key"]
        (output_dir / "project-theses" / "en" / f"{entity_key}.md").write_text(render_thesis_en(project), encoding="utf-8")
        (output_dir / "project-theses" / "zh" / f"{entity_key}.md").write_text(render_thesis_zh(project), encoding="utf-8")

    print(f"PASS  Briefs written under: {(output_dir / 'briefs').relative_to(ROOT)}")
    print(f"PASS  Thesis files written: {len(projects) * 2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
