#!/usr/bin/env python3

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from typing import Any

from common import (
    ROOT,
    ensure_dir,
    latest_json_file,
    latest_json_file_for_source,
    load_effective_yaml,
    output_dir_from_config,
    read_json_file,
    resolve_reporting_formats,
    resolve_reporting_locale,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build user-facing opportunity briefs and project thesis files.")
    parser.add_argument("--input", help="Optional path to context JSON file")
    parser.add_argument("--source-id", help="Resolve the latest context artifact for this source when --input is omitted")
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


def localized_items(project: dict[str, Any], field_name: str, locale: str) -> list[str]:
    if locale == "zh":
        localized = project.get(f"{field_name}_zh", [])
        if isinstance(localized, list) and localized:
            return [str(item).strip() for item in localized if str(item).strip()]
    values = project.get(field_name, [])
    if isinstance(values, list):
        return [str(item).strip() for item in values if str(item).strip()]
    return []


def build_fact_lines(project: dict[str, Any], locale: str) -> list[str]:
    facts: list[str] = []
    investors = [str(item).strip() for item in project.get("investors", []) if str(item).strip()]
    funding_signals = [str(item).strip() for item in project.get("funding_signals", []) if str(item).strip()]
    team = project.get("team", []) if isinstance(project.get("team", []), list) else []
    founded = str(project.get("founded") or "").strip()
    signals = [str(item).strip() for item in project.get("supporting_signals", []) if str(item).strip()]

    if funding_signals:
        facts.append(("融资线索: " if locale == "zh" else "Funding: ") + funding_signals[0])
    elif investors:
        facts.append(("投资方: " if locale == "zh" else "Backers: ") + ", ".join(investors[:4]))
    if team:
        lead_names = ", ".join(str(item.get("name") or "").strip() for item in team[:3] if str(item.get("name") or "").strip())
        prefix = "团队: " if locale == "zh" else "Team: "
        suffix = f" ({len(team)} named)" if locale != "zh" else f"（已识别 {len(team)} 位具名成员）"
        facts.append(prefix + (lead_names or "n/a") + suffix)
    if founded:
        facts.append(("成立时间: " if locale == "zh" else "Founded: ") + founded)
    if signals:
        facts.append(("热度/信号: " if locale == "zh" else "Signals: ") + " | ".join(signals[:2]))
    return facts[:4]


def render_brief_en(projects: list[dict[str, Any]], focus: dict[str, Any]) -> str:
    lines = ["# Opportunity Brief", ""]
    lines.append(f"- Focus chains: {', '.join(focus.get('chains', [])) or 'global'}")
    lines.append(f"- Focus sectors: {', '.join(focus.get('sectors', [])) or 'general'}")
    lines.append("")
    lines.append("## Top Opportunities")
    lines.append("")
    for index, project in enumerate(projects, start=1):
        project_summary = project.get("summary") or "n/a"
        action_premise = " ".join(localized_items(project, "opportunity_thesis", "en")) or "Only actionable when a concrete participation surface is live."
        fact_lines = build_fact_lines(project, "en")
        lines.append(f"### {index}. {project['project_name']}")
        lines.append(f"- Score: {project['score']} ({project['label']})")
        lines.append(f"- Project setup: {project_summary}")
        lines.append(f"- Why track now: {action_premise}")
        lines.append(f"- Participation angle: {' '.join(localized_items(project, 'participation_angle', 'en'))}")
        lines.append(f"- Hard facts: {' | '.join(fact_lines) or 'n/a'}")
        lines.append(f"- Priority checks: {' '.join(localized_items(project, 'priority_checks', 'en'))}")
        lines.append(f"- Validation sources: {', '.join(localized_items(project, 'validation_sources', 'en'))}")
        lines.append(f"- URL: {project.get('project_url') or 'n/a'}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def translate_reason_zh(reason: str) -> str:
    mapping = {
        "Already ranking near the top of RootData, so attention is forming before the market is fully crowded.": "它已经进入 RootData 前排，说明关注度正在形成，但还没有完全挤满。",
        "Already appearing on RootData, which suggests early but visible market attention.": "它已经进入 RootData 视野，说明市场已经开始关注，但还不算完全拥挤。",
        "This project is confirmed across multiple source types, which lowers single-feed noise.": "它被多类来源同时捕捉到，说明不是单一信息流噪音。",
        "Infra projects often expose the earliest participation paths through testnets, validators, grants, or ecosystem programs.": "基础设施类项目通常最早会通过测试网、验证者、资助或生态计划开放参与窗口。",
        "DeFi projects often create usable early angles through points, beta access, liquidity programs, or first-wave product usage.": "DeFi 项目常见的早期参与角度包括积分、内测资格、流动性激励和第一波产品使用。",
        "AI or research-heavy teams usually reward early contributors through dev communities, integrations, or technical pilot programs.": "AI 或研究型团队更容易通过开发者社区、集成合作或技术试点释放早期位置。",
        "Consumer-facing products are most attractive when waitlists, referrals, and onboarding campaigns appear before broad distribution.": "面向用户的产品如果在大规模扩散前就开放候补、邀请或拉新机制，往往更值得提前参与。",
        "Recent financing can accelerate product shipping and ecosystem incentive rollout.": "如果它刚有融资，往往意味着产品推进和生态激励会加速落地。",
        "A visible testnet usually means there is a concrete near-term participation window rather than a pure narrative trade.": "如果已经出现测试网，通常意味着这是可参与的真实窗口，而不只是讲故事。",
        "Launch-stage signals matter because the best participation edge often sits just before or just after release.": "临近上线阶段很关键，因为最佳参与边际往往就在发布前后。",
        "The summary already hints at an incentive surface, which makes this more actionable than a pure news mention.": "摘要里已经出现激励面信号，这种机会比纯新闻更可操作。",
        "This project is worth tracking only if it opens a concrete participation surface soon, such as testnet, waitlist, liquidity, or ecosystem access.": "这类项目只有在即将开放测试网、候补、流动性或生态入口时，才真正值得跟。",
    }
    if reason in mapping:
        return mapping[reason]
    return reason


def translate_check_zh(text: str) -> str:
    mapping = {
        "Verify whether testnet, devnet, validator, or ecosystem grant access is already live.": "先确认测试网、开发网、验证者计划或生态资助入口是否已经开放。",
        "Verify whether product beta, points, vault access, or liquidity incentives are already open.": "先确认产品内测、积分、金库权限或流动性激励是否已经开放。",
        "Verify whether there is a developer program, technical demo, or partner integration you can join early.": "先确认有没有开发者计划、技术演示或合作接入可以提前参与。",
        "Verify the financing stage, lead investors, and what milestone the raise is supposed to unlock next.": "先确认融资轮次、领投方，以及这笔钱接下来会推动什么里程碑。",
        "Cross-check the RootData detail page for investor, ecosystem, and related project context.": "去 RootData 详情页补查投资方、生态归属和相关项目关系。",
        "Check GitHub activity to confirm this is shipping work, not just a narrative mention.": "去看 GitHub 活跃度，确认它是真的在交付，而不是单纯叙事热度。",
        "Verify the first concrete participation surface before treating this as an actionable opportunity.": "在把它当成可执行机会前，先确认第一层真实参与入口。",
    }
    return mapping.get(text, text)


def label_zh(label: str) -> str:
    mapping = {
        "high-priority follow": "高优先级跟踪",
        "strong candidate": "强候选",
        "monitor": "建议观察",
        "low priority for now": "暂时低优先级",
    }
    return mapping.get(label, label)


def translate_participation_zh(text: str) -> str:
    mapping = {
        "Track testnet access, validator programs, grants, and ecosystem builder campaigns.": "重点盯测试网入口、验证者计划、资助项目和生态建设者活动。",
        "Look for developer previews, technical communities, research pilots, or integration programs.": "重点找开发者预览、技术社区、研究试点或集成计划。",
        "Monitor product beta access, liquidity programs, points systems, and early user incentives.": "重点盯产品内测资格、流动性激励、积分体系和早期用户激励。",
        "Watch for waitlists, referral loops, ambassador programs, and onboarding campaigns.": "重点盯候补名单、邀请裂变、 ambassador 计划和拉新活动。",
        "Check whether the team has already exposed points, quests, or airdrop-style incentive mechanics.": "确认团队是否已经放出积分、任务或空投式激励机制。",
        "Use the financing milestone as a timing signal and watch what product or ecosystem program follows next.": "把融资节点当成时间信号，重点看接下来落什么产品或生态计划。",
        "Check official channels for launch updates, beta access, and any program that creates a concrete first-mover edge.": "去官方渠道确认上线、内测资格和任何能形成先手优势的参与计划。",
    }
    return mapping.get(text, text)


def translate_validation_source_zh(text: str) -> str:
    mapping = {
        "Official announcements": "官方公告",
        "Project X/Twitter account": "项目官方 X/Twitter",
        "GitHub activity": "GitHub 活跃度",
        "DeFiLlama listings or TVL changes": "DeFiLlama 收录和 TVL 变化",
        "Ecosystem launch posts or developer documentation": "生态上线公告或开发者文档",
        "Research threads, technical blog posts, or demo releases": "研究线程、技术博客或 demo 发布",
        "RootData project detail page": "RootData 项目详情页",
    }
    return mapping.get(text, text)


def render_brief_zh(projects: list[dict[str, Any]], focus: dict[str, Any]) -> str:
    lines = ["# 机会简报", ""]
    lines.append(f"- 关注链: {', '.join(focus.get('chains', [])) or 'global'}")
    lines.append(f"- 关注赛道: {', '.join(focus.get('sectors', [])) or 'general'}")
    lines.append("")
    lines.append("## 核心机会")
    lines.append("")
    for index, project in enumerate(projects, start=1):
        project_summary = project.get("summary") or "n/a"
        action_premise = " ".join(localized_items(project, "opportunity_thesis", "zh")) or "只有在真实参与入口已经开放时才值得上手。"
        fact_lines = build_fact_lines(project, "zh")
        lines.append(f"### {index}. {project['project_name']}")
        lines.append(f"- 评分: {project['score']} ({label_zh(project['label'])})")
        lines.append(f"- 项目定位: {project_summary}")
        lines.append(f"- 为什么值得跟: {action_premise}")
        lines.append(f"- 参与动作: {' '.join(localized_items(project, 'participation_angle', 'zh'))}")
        lines.append(f"- 硬线索: {' | '.join(fact_lines) or 'n/a'}")
        lines.append(f"- 优先补查: {' '.join(localized_items(project, 'priority_checks', 'zh'))}")
        lines.append(f"- 建议补查来源: {', '.join(localized_items(project, 'validation_sources', 'zh'))}")
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
            f"{' '.join(localized_items(project, 'opportunity_thesis', 'en'))}",
            "",
            "## Participation Angle",
            "",
            *[f"- {item}" for item in localized_items(project, "participation_angle", "en")],
            "",
            "## Hard Facts",
            "",
            *[f"- {item}" for item in build_fact_lines(project, "en")],
            "",
            "## Evidence",
            "",
            *[f"- {signal}" for signal in project.get("supporting_signals", [])],
            "",
            "## Priority Checks",
            "",
            *[f"- {item}" for item in localized_items(project, "priority_checks", "en")],
            "",
            "## Validation Sources",
            "",
            *[f"- {item}" for item in localized_items(project, "validation_sources", "en")],
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
            f"{' '.join(localized_items(project, 'opportunity_thesis', 'zh'))}",
            "",
            "## 参与角度",
            "",
            *[f"- {item}" for item in localized_items(project, "participation_angle", "zh")],
            "",
            "## 硬线索",
            "",
            *[f"- {item}" for item in build_fact_lines(project, "zh")],
            "",
            "## 支撑线索",
            "",
            *[f"- {signal}" for signal in project.get("supporting_signals", [])],
            "",
            "## 优先补查",
            "",
            *[f"- {item}" for item in localized_items(project, "priority_checks", "zh")],
            "",
            "## 建议补查来源",
            "",
            *[f"- {item}" for item in localized_items(project, "validation_sources", "zh")],
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
        signals = project.get("supporting_signals", [])
        participation = localized_items(project, "participation_angle", locale)
        checks = localized_items(project, "priority_checks", locale)
        primary_check = checks[0] if checks else "n/a"
        score_label = "评分" if locale == "zh" else "Score"
        project_setup = project.get("summary") or "n/a"
        action_premise = (
            " ".join(localized_items(project, "opportunity_thesis", "zh")) or "只有在真实参与入口已经开放时才值得上手。"
            if locale == "zh"
            else (" ".join(localized_items(project, "opportunity_thesis", "en")) or "Only actionable when a concrete participation surface is live.")
        )
        setup_label = "项目定位" if locale == "zh" else "Project setup"
        why_label = "为什么值得跟" if locale == "zh" else "Why track now"
        angle_label = "参与动作" if locale == "zh" else "Participation angle"
        signal_label = "硬线索" if locale == "zh" else "Hard facts"
        next_label = "优先补查" if locale == "zh" else "Priority check"
        link_label = "项目链接" if locale == "zh" else "Project link"
        fact_lines = build_fact_lines(project, locale)

        cards.append(
            "\n".join(
                [
                    '<article class="opportunity-card">',
                    f'  <div class="card-rank">{index:02d}</div>',
                    f"  <h2>{title}</h2>",
                    f'  <p class="score-pill">{score_label}: {score} · {label}</p>',
                    f'  <div class="card-block"><span class="block-label">{setup_label}</span><p>{html_escape(project_setup)}</p></div>',
                    f'  <div class="card-block"><span class="block-label">{why_label}</span><p>{html_escape(action_premise)}</p></div>',
                    f'  <div class="card-block"><span class="block-label">{angle_label}</span><p>{html_escape(" ".join(participation) or "n/a")}</p></div>',
                    f'  <div class="card-block"><span class="block-label">{signal_label}</span><p>{html_escape(" | ".join(fact_lines) or "n/a")}</p></div>',
                    f'  <div class="card-block"><span class="block-label">{next_label}</span><p>{html_escape(primary_check)}</p></div>',
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
        "Action-oriented early opportunity cards for scheduling, review, and follow-through."
        if not is_zh
        else "更偏执行和参与视角的一页式早期机会卡片。"
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
        --panel: #fffaf4;
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
        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: 20px;
        margin-top: 26px;
      }}
      .opportunity-card {{
        position: relative;
        padding: 24px 20px 18px;
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
        font-size: 1.5rem;
      }}
      .score-pill {{
        display: inline-block;
        margin: 0 0 14px;
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
      .card-block {{
        margin: 0 0 12px;
        padding: 12px 12px 10px;
        border-radius: 16px;
        background: var(--panel);
        border: 1px solid rgba(24, 34, 45, 0.06);
      }}
      .block-label {{
        display: inline-block;
        margin-bottom: 6px;
        font-size: 0.76rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--accent);
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

    if args.input:
        input_path = ROOT / args.input
    elif args.source_id:
        input_path = latest_json_file_for_source(output_dir / "context", args.source_id)
    else:
        input_path = latest_json_file(output_dir / "context")
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
