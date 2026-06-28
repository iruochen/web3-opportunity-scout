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
    resolve_reporting_formats,
    resolve_reporting_locale,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build user-facing opportunity briefs and project thesis files.")
    parser.add_argument("--input", help="Optional path to context JSON file")
    parser.add_argument("--top", type=int, default=8, help="Number of projects to include in the brief")
    return parser.parse_args()


def format_focus_list(items: list[str], fallback: str) -> str:
    cleaned = [str(item).strip() for item in items if str(item).strip()]
    return ", ".join(cleaned) or fallback


def html_escape(value: str) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


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
        lines.append(f"- Participation angle: {' '.join(project.get('participation_angle', []))}")
        lines.append(f"- Suggested validation sources: {', '.join(project.get('validation_sources', []))}")
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
        lines.append(f"- 参与角度: {' '.join(project.get('participation_angle', []))}")
        lines.append(f"- 建议补查来源: {', '.join(project.get('validation_sources', []))}")
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
            "- Participation angle:",
            *[f"  - {item}" for item in project.get("participation_angle", [])],
            "",
            "- Suggested sources:",
            *[f"  - {item}" for item in project.get("validation_sources", [])],
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
            "- 参与角度：",
            *[f"  - {item}" for item in project.get("participation_angle", [])],
            "",
            "- 建议补查来源：",
            *[f"  - {item}" for item in project.get("validation_sources", [])],
            "",
            *[f"- {translate_question_zh(question)}" for question in project.get("follow_up_questions", [])],
            "",
        ]
    ).strip() + "\n"


def render_project_cards_html(projects: list[dict[str, Any]], locale: str) -> str:
    cards: list[str] = []
    for index, project in enumerate(projects, start=1):
        title = html_escape(project["project_name"])
        score = html_escape(str(project["score"]))
        label = html_escape(label_zh(project["label"]) if locale == "zh" else project["label"])
        url = html_escape(project.get("project_url") or "#")
        reasoning_items = project.get("reasoning", [])
        reasoning = " ".join(
            translate_reason_zh(item) if locale == "zh" else item
            for item in reasoning_items
        )
        signals = project.get("supporting_signals", [])
        participation = project.get("participation_angle", [])
        next_check = (
            translate_question_zh(project["follow_up_questions"][2])
            if locale == "zh"
            else project["follow_up_questions"][2]
        )
        score_label = "评分" if locale == "zh" else "Score"
        why_label = "为什么值得看" if locale == "zh" else "Why it matters"
        signal_label = "关键线索" if locale == "zh" else "Signals"
        angle_label = "参与角度" if locale == "zh" else "Participation angle"
        next_label = "下一步建议" if locale == "zh" else "Suggested next check"
        link_label = "项目链接" if locale == "zh" else "Project link"

        cards.append(
            "\n".join(
                [
                    '<article class="opportunity-card">',
                    f'  <div class="card-rank">{index:02d}</div>',
                    f"  <h2>{title}</h2>",
                    f'  <p class="score-pill">{score_label}: {score} · {label}</p>',
                    f"  <p><strong>{why_label}:</strong> {html_escape(reasoning)}</p>",
                    f"  <p><strong>{signal_label}:</strong> {html_escape(' | '.join(signals) or 'n/a')}</p>",
                    f"  <p><strong>{angle_label}:</strong> {html_escape(' '.join(participation))}</p>",
                    f"  <p><strong>{next_label}:</strong> {html_escape(next_check)}</p>",
                    f'  <p><a href="{url}" target="_blank" rel="noopener noreferrer">{link_label}</a></p>',
                    "</article>",
                ]
            )
        )
    return "\n".join(cards)


def render_brief_html(projects: list[dict[str, Any]], focus: dict[str, Any], locale: str) -> str:
    is_zh = locale == "zh"
    title = "Web3 Early Opportunity Brief" if not is_zh else "Web3 早期机会简报"
    subtitle = (
        "A compact scouting digest for scheduled pushes and operator review."
        if not is_zh
        else "适合定时推送和人工复核的一页式机会摘要。"
    )
    focus_chains = format_focus_list(focus.get("chains", []), "global")
    focus_sectors = format_focus_list(focus.get("sectors", []), "general")
    cards = render_project_cards_html(projects, locale)
    chains_label = "Focus chains" if not is_zh else "关注链"
    sectors_label = "Focus sectors" if not is_zh else "关注赛道"
    generated_label = "Generated at" if not is_zh else "生成时间"
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!doctype html>
<html lang="{locale}">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{html_escape(title)}</title>
    <style>
      :root {{
        color-scheme: light;
        --bg: #f4efe6;
        --ink: #18222d;
        --muted: #5e6a72;
        --accent: #d96c3d;
        --accent-soft: #f7d9cb;
        --card: rgba(255, 255, 255, 0.86);
        --border: rgba(24, 34, 45, 0.08);
        --shadow: 0 24px 70px rgba(24, 34, 45, 0.08);
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: "Georgia", "Times New Roman", serif;
        color: var(--ink);
        background:
          radial-gradient(circle at top left, rgba(217,108,61,0.18), transparent 24rem),
          linear-gradient(180deg, #fbf7f1 0%, var(--bg) 100%);
      }}
      main {{
        max-width: 1040px;
        margin: 0 auto;
        padding: 56px 20px 72px;
      }}
      .hero {{
        padding: 32px;
        border: 1px solid var(--border);
        border-radius: 28px;
        background: linear-gradient(135deg, rgba(255,255,255,0.92), rgba(255,248,241,0.88));
        box-shadow: var(--shadow);
      }}
      h1 {{
        margin: 0 0 10px;
        font-size: clamp(2rem, 4vw, 3.5rem);
        line-height: 0.95;
      }}
      .subtitle {{
        margin: 0 0 18px;
        color: var(--muted);
        font-size: 1rem;
      }}
      .meta {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 12px;
        margin-top: 18px;
      }}
      .meta-card, .opportunity-card {{
        border: 1px solid var(--border);
        border-radius: 22px;
        background: var(--card);
        backdrop-filter: blur(12px);
        box-shadow: var(--shadow);
      }}
      .meta-card {{
        padding: 16px 18px;
      }}
      .meta-card strong {{
        display: block;
        margin-bottom: 6px;
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--muted);
      }}
      .opportunities {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 18px;
        margin-top: 26px;
      }}
      .opportunity-card {{
        position: relative;
        padding: 24px 20px 20px;
        overflow: hidden;
      }}
      .card-rank {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 40px;
        height: 40px;
        border-radius: 999px;
        background: var(--accent-soft);
        color: var(--accent);
        font-weight: 700;
        margin-bottom: 14px;
      }}
      .opportunity-card h2 {{
        margin: 0 0 8px;
        font-size: 1.45rem;
      }}
      .score-pill {{
        display: inline-block;
        margin: 0 0 12px;
        padding: 7px 12px;
        border-radius: 999px;
        background: #18222d;
        color: #fff;
        font-size: 0.9rem;
      }}
      .opportunity-card p {{
        margin: 0 0 12px;
        line-height: 1.55;
        color: var(--muted);
      }}
      .opportunity-card strong {{
        color: var(--ink);
      }}
      .opportunity-card a {{
        color: var(--accent);
        text-decoration: none;
        font-weight: 600;
      }}
      @media (max-width: 640px) {{
        main {{
          padding: 28px 14px 40px;
        }}
        .hero {{
          padding: 22px;
          border-radius: 22px;
        }}
      }}
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <h1>{html_escape(title)}</h1>
        <p class="subtitle">{html_escape(subtitle)}</p>
        <div class="meta">
          <div class="meta-card">
            <strong>{html_escape(chains_label)}</strong>
            <span>{html_escape(focus_chains)}</span>
          </div>
          <div class="meta-card">
            <strong>{html_escape(sectors_label)}</strong>
            <span>{html_escape(focus_sectors)}</span>
          </div>
          <div class="meta-card">
            <strong>{html_escape(generated_label)}</strong>
            <span>{html_escape(generated_at)}</span>
          </div>
        </div>
      </section>
      <section class="opportunities">
        {cards}
      </section>
    </main>
  </body>
</html>
"""


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
    locale = resolve_reporting_locale(config)
    formats = resolve_reporting_formats(config)

    brief_en = render_brief_en(projects, focus)
    brief_zh = render_brief_zh(projects, focus)
    (output_dir / "briefs" / f"{today}-brief.en.md").write_text(brief_en, encoding="utf-8")
    (output_dir / "briefs" / f"{today}-brief.zh.md").write_text(brief_zh, encoding="utf-8")
    (output_dir / "briefs" / "latest-brief.en.md").write_text(brief_en, encoding="utf-8")
    (output_dir / "briefs" / "latest-brief.zh.md").write_text(brief_zh, encoding="utf-8")

    if locale == "zh":
        primary_md = brief_zh
        primary_thesis_renderer = render_thesis_zh
    elif locale == "bilingual":
        primary_md = brief_en.rstrip() + "\n\n---\n\n" + brief_zh
        primary_thesis_renderer = None
    else:
        primary_md = brief_en
        primary_thesis_renderer = render_thesis_en

    if "md" in formats:
        (output_dir / "briefs" / f"{today}-brief.md").write_text(primary_md, encoding="utf-8")
        (output_dir / "briefs" / "latest-brief.md").write_text(primary_md, encoding="utf-8")
    if "html" in formats:
        html_locale = "zh" if locale == "zh" else "en"
        brief_html = render_brief_html(projects, focus, html_locale)
        (output_dir / "briefs" / f"{today}-brief.html").write_text(brief_html, encoding="utf-8")
        (output_dir / "briefs" / "latest-brief.html").write_text(brief_html, encoding="utf-8")

    for project in projects:
        entity_key = project["entity_key"]
        (output_dir / "project-theses" / "en" / f"{entity_key}.md").write_text(render_thesis_en(project), encoding="utf-8")
        (output_dir / "project-theses" / "zh" / f"{entity_key}.md").write_text(render_thesis_zh(project), encoding="utf-8")
        if primary_thesis_renderer is not None:
            ensure_dir(output_dir / "project-theses" / "primary")
            (output_dir / "project-theses" / "primary" / f"{entity_key}.md").write_text(
                primary_thesis_renderer(project),
                encoding="utf-8",
            )

    print(f"PASS  Briefs written under: {(output_dir / 'briefs').relative_to(ROOT)}")
    print(f"PASS  Reporting locale: {locale}")
    print(f"PASS  Reporting formats: {', '.join(formats)}")
    print(f"PASS  Thesis files written: {len(projects) * 2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
