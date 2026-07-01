#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
import fcntl
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent


def load_dotenv_file(path: Path | None = None, override: bool = False) -> Path | None:
    dotenv_path = path or (ROOT / ".env")
    if not dotenv_path.exists():
        return None

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        if override or key not in os.environ:
            os.environ[key] = value
    return dotenv_path


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_yaml_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in YAML file: {path}")
    return data


def load_effective_yaml(primary_name: str, fallback_name: str) -> tuple[dict[str, Any], Path]:
    primary = ROOT / primary_name
    fallback = ROOT / fallback_name

    if primary.exists():
        return load_yaml_file(primary), primary
    return load_yaml_file(fallback), fallback


def iter_source_entries(sources_config: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    results: list[tuple[str, dict[str, Any]]] = []
    sources = sources_config.get("sources", {})
    if not isinstance(sources, dict):
        raise ValueError("Expected 'sources' to be a mapping")

    for category, entries in sources.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict):
                results.append((str(category), entry))
    return results


def find_source_definition(sources_config: dict[str, Any], source_id: str) -> tuple[str, dict[str, Any]]:
    for category, entry in iter_source_entries(sources_config):
        if entry.get("id") == source_id:
            return category, entry
    raise KeyError(f"Source id not found: {source_id}")


def enabled_source_entries(sources_config: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [
        (category, entry)
        for category, entry in iter_source_entries(sources_config)
        if bool(entry.get("enabled"))
    ]


def resolve_source_adapter(source_id: str, source_def: dict[str, Any]) -> str:
    adapter = str(source_def.get("adapter", "")).strip()
    if adapter:
        return adapter

    if source_id.endswith("_projects"):
        return source_id[: -len("_projects")]
    if source_id.endswith("_project"):
        return source_id[: -len("_project")]
    if source_id.endswith("_list"):
        return source_id[: -len("_list")]
    return source_id


def read_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json_file(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(path)


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip())
    return normalized.strip("-").lower() or "default"


def load_profile_config(config: dict[str, Any]) -> dict[str, Any]:
    profile = config.get("profile", {})
    if not isinstance(profile, dict):
        return {}
    return profile


def state_dir_from_config(config: dict[str, Any]) -> Path:
    return ROOT / str(load_profile_config(config).get("state_dir", "state"))


def cache_dir_from_config(config: dict[str, Any]) -> Path:
    return ROOT / str(load_profile_config(config).get("cache_dir", "cache"))


def output_dir_from_config(config: dict[str, Any]) -> Path:
    return ROOT / str(load_profile_config(config).get("output_dir", "output"))


def reporting_config(config: dict[str, Any]) -> dict[str, Any]:
    reporting = config.get("reporting", {})
    if not isinstance(reporting, dict):
        return {}
    return reporting


def infer_locale_from_environment(config: dict[str, Any]) -> str:
    for env_key in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = str(os.environ.get(env_key, "")).lower()
        if value.startswith("zh"):
            return "zh"
        if value.startswith("en"):
            return "en"

    timezone = str(load_profile_config(config).get("timezone", "")).lower()
    if timezone.startswith("asia/shanghai") or timezone.startswith("asia/hong_kong") or timezone.startswith("asia/taipei"):
        return "zh"
    return "en"


def resolve_reporting_locale(config: dict[str, Any]) -> str:
    reporting = reporting_config(config)
    locale = str(reporting.get("locale", "auto")).strip().lower()
    if locale in {"en", "zh", "bilingual"}:
        return locale
    return infer_locale_from_environment(config)


def resolve_reporting_formats(config: dict[str, Any]) -> list[str]:
    reporting = reporting_config(config)
    raw_formats = reporting.get("generate_formats")
    if isinstance(raw_formats, list):
        formats = [str(item).strip().lower() for item in raw_formats if str(item).strip()]
    else:
        primary = str(reporting.get("primary_format", "html")).strip().lower() or "html"
        formats = [primary]

    allowed = {"md", "html"}
    deduped: list[str] = []
    for item in formats:
        if item in allowed and item not in deduped:
            deduped.append(item)
    return deduped or ["html"]


def latest_json_file(path: Path) -> Path:
    candidates = sorted(path.rglob("*.json"), key=lambda item: (item.stat().st_mtime, str(item)))
    if not candidates:
        raise FileNotFoundError(f"No JSON files found under {path}")
    return candidates[-1]


def latest_json_file_for_source(path: Path, source_id: str) -> Path:
    needle = slugify(source_id)
    candidates = sorted(
        [item for item in path.rglob("*.json") if needle in slugify(item.stem)],
        key=lambda item: (item.stat().st_mtime, str(item)),
    )
    if not candidates:
        raise FileNotFoundError(f"No JSON files found under {path} for source {source_id}")
    return candidates[-1]


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def extract_hot_rank(signals: list[str]) -> int | None:
    for signal in signals:
        text = str(signal).strip()
        prefix = "RootData hot rank:"
        if not text.startswith(prefix):
            continue
        try:
            return int(text.split(":", 1)[1].strip())
        except ValueError:
            return None
    return None


def is_established_project(project_name: str) -> bool:
    normalized = project_name.strip().lower()
    established = {
        "solana",
        "ethereum",
        "sui",
        "hyperliquid",
        "chainlink",
        "injective",
        "layerzero",
        "near protocol",
        "ripple",
        "stellar",
        "monad",
        "manta network",
        "bittensor",
        "aave",
        "aave v3",
        "lido",
        "binance cex",
        "okx",
        "bybit",
        "bitfinex",
    }
    return normalized in established


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    results: list[str] = []
    for item in items:
        text = str(item).strip()
        if text and text not in results:
            results.append(text)
    return results


def _project_tags(project: dict[str, Any]) -> set[str]:
    return {str(tag).strip().lower() for tag in project.get("tags", []) if str(tag).strip()}


def _project_summary(project: dict[str, Any]) -> str:
    return str(project.get("summary") or "").strip()


def _project_investors(project: dict[str, Any]) -> list[str]:
    return _dedupe_preserve_order([str(item).strip() for item in project.get("investors", []) if str(item).strip()])


def _project_team(project: dict[str, Any]) -> list[dict[str, str]]:
    team = project.get("team", [])
    if not isinstance(team, list):
        return []
    results: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for member in team:
        if not isinstance(member, dict):
            continue
        name = str(member.get("name") or "").strip()
        role = str(member.get("role") or "").strip()
        key = (name, role)
        if not name or key in seen:
            continue
        seen.add(key)
        results.append({"name": name, "role": role})
    return results


def _project_funding_signals(project: dict[str, Any]) -> list[str]:
    direct = project.get("funding_signals", [])
    if isinstance(direct, list) and direct:
        return _dedupe_preserve_order([str(item).strip() for item in direct if str(item).strip()])

    recovered: list[str] = []
    for signal in project.get("signals", []):
        text = str(signal).strip()
        prefix = "Funding signal:"
        if text.startswith(prefix):
            recovered.append(text.split(":", 1)[1].strip())
    return _dedupe_preserve_order(recovered)


def _project_funding_rounds(project: dict[str, Any]) -> list[dict[str, Any]]:
    rounds = project.get("funding_rounds", [])
    if not isinstance(rounds, list):
        return []
    results: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in rounds:
        if not isinstance(item, dict):
            continue
        round_name = str(item.get("round") or "").strip()
        amount = str(item.get("amount") or "").strip()
        date = str(item.get("date") or "").strip()
        investors = [str(name).strip() for name in item.get("investors", []) if str(name).strip()] if isinstance(item.get("investors"), list) else []
        key = (round_name, amount, date)
        if not any(key) or key in seen:
            continue
        seen.add(key)
        results.append({"round": round_name, "amount": amount, "date": date, "investors": investors})
    return results


def _project_news_links(project: dict[str, Any]) -> list[dict[str, str]]:
    news_links = project.get("news_links", [])
    if not isinstance(news_links, list):
        return []
    results: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for item in news_links:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        title = str(item.get("title") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        results.append({"title": title, "url": url})
    return results


def _project_rank(project: dict[str, Any]) -> int | None:
    return extract_hot_rank(project.get("signals", []))


def _project_source_ids(project: dict[str, Any]) -> list[str]:
    values = project.get("source_ids", [])
    if not isinstance(values, list):
        return []
    return _dedupe_preserve_order([str(item).strip() for item in values if str(item).strip()])


def _joined_project_text(project: dict[str, Any]) -> str:
    parts = [str(project.get("summary") or "")]
    parts.extend(str(item) for item in project.get("signals", []))
    parts.extend(str(item) for item in project.get("funding_signals", []))
    return " ".join(parts).lower()


def _keyword_hits(text: str, keywords: tuple[str, ...]) -> list[str]:
    hits: list[str] = []
    for keyword in keywords:
        if keyword in text and keyword not in hits:
            hits.append(keyword)
    return hits


def project_participation_signals(project: dict[str, Any]) -> list[str]:
    text = _joined_project_text(project)
    keywords = (
        "waitlist",
        "beta",
        "testnet",
        "devnet",
        "points",
        "quest",
        "incentive",
        "incentives",
        "referral",
        "whitelist",
        "allowlist",
        "ambassador",
        "grant",
        "grants",
        "validator",
        "liquidity mining",
        "vault",
        "staking",
        "campaign",
        "early access",
        "mainnet launch",
    )
    return _keyword_hits(text, keywords)


def project_strong_participation_signals(project: dict[str, Any]) -> list[str]:
    strong = {
        "waitlist",
        "beta",
        "testnet",
        "devnet",
        "points",
        "quest",
        "incentive",
        "incentives",
        "referral",
        "whitelist",
        "allowlist",
        "ambassador",
        "grant",
        "grants",
        "liquidity mining",
        "early access",
        "mainnet launch",
    }
    return [item for item in project_participation_signals(project) if item in strong]


def project_funding_evidence(project: dict[str, Any]) -> list[str]:
    rounds = _project_funding_rounds(project)
    if rounds:
        evidence: list[str] = []
        for item in rounds:
            text = " ".join(str(item.get(key) or "").strip() for key in ("round", "amount") if str(item.get(key) or "").strip())
            if text:
                evidence.append(text)
        if evidence:
            return evidence
    direct = _project_funding_signals(project)
    if direct:
        return direct
    investors = _project_investors(project)
    if investors:
        return investors
    text = _joined_project_text(project)
    keywords = ("seed round", "series a", "series b", "raised", "backed by", "investment round", "lead investor")
    return _keyword_hits(text, keywords)


def project_negative_signals(project: dict[str, Any]) -> list[str]:
    text = _joined_project_text(project)
    keywords = (
        "没真新闻",
        "没资金动静",
        "复读",
        "故事已经快讲完",
        "no real news",
        "no funding movement",
        "no new information",
        "narrative is fading",
    )
    return _keyword_hits(text, keywords)


def project_actionability_score(project: dict[str, Any]) -> float:
    participation = project_participation_signals(project)
    strong_participation = project_strong_participation_signals(project)
    funding = project_funding_evidence(project)
    investors = _project_investors(project)
    team = _project_team(project)
    sources = _project_source_ids(project)
    score = 0.0
    score += min(len(strong_participation), 4) * 20.0
    weak_participation = max(0, len(participation) - len(strong_participation))
    score += min(weak_participation, 2) * 6.0
    if funding:
        score += 22.0
    if investors:
        score += 10.0
    if team:
        score += min(len(team), 3) * 4.0
    if len(sources) >= 2:
        score += 12.0 + min(len(sources) - 2, 2) * 4.0
    if project_negative_signals(project):
        score -= 20.0
    return clamp(score, 0.0, 100.0)


def _project_shape_theses(project: dict[str, Any], locale: str) -> list[str]:
    tags = _project_tags(project)
    summary = _project_summary(project).lower()
    name = str(project.get("project_name") or project.get("canonical_name") or "").strip()
    theses: list[str] = []

    def add(zh: str, en: str) -> None:
        theses.append(zh if locale == "zh" else en)

    if "intent" in tags and "infra" in tags:
        add(
            "它不是单纯新链叙事，而是意图/抽象层基础设施；真正的早期边际在 SDK、集成方和跨协议操作入口是否先放出来。",
            "This is not just a new-chain narrative; as intent/abstraction infra, the early edge is whether SDKs, integrations, or cross-protocol workflows open first.",
        )
    elif "cloud computing" in tags or ("ai" in tags and ("layer1" in tags or "network" in summary)):
        add(
            "它更像 AI/算力网络，不能只看热度；优先判断是否能贡献算力、跑节点、接入开发者测试网或参与研究社区。",
            "This looks like an AI/compute network, so heat alone is not enough; prioritize compute contribution, nodes, dev testnets, or research community access.",
        )
    elif "bridge" in tags or "ecosystem(19):" in tags:
        add(
            "它的机会更可能出现在新链接入、跨链流动性迁移和生态活动，而不是普通持币观察。",
            "The likely edge is new-chain support, cross-chain liquidity migration, or ecosystem campaigns rather than passive token watching.",
        )
    elif "crypto card" in tags or "payment" in tags:
        add(
            "这是偏消费/支付入口的项目，早期价值通常不在技术白皮书，而在首批开户、邀请、卡片权益或积分活动。",
            "This is closer to a consumer/payment entry point; early value usually comes from first-wave onboarding, referrals, card perks, or points campaigns.",
        )
    elif "insurance" in tags:
        add(
            "保险/风险市场项目的参与点通常在承保资金池、保险库或首批产品试用，适合看是否出现资本提供者入口。",
            "Insurance/risk-market projects usually become actionable through underwriting pools, vaults, or first product trials; look for capital-provider access.",
        )
    elif {"tools", "data & analysis", "on-chain data"} & tags:
        add(
            "它偏数据/分析工具，参与边际更可能来自 API、dashboard beta、数据贡献或开发者社区，而不是普通交互任务。",
            "This is more of a data/tooling play; the edge is more likely APIs, dashboard beta, data contribution, or developer community access than generic quests.",
        )
    elif "defi" in tags and "intent" in tags:
        add(
            "DeFi + intent 的组合更适合盯自动化策略、首批 vault、路由/执行任务和积分，而不是只看融资背书。",
            "DeFi plus intents should be watched for automated strategies, first vaults, routing/execution tasks, and points rather than funding alone.",
        )
    elif "defi" in tags:
        add(
            "DeFi 项目只有出现可用产品、资金池、积分或流动性激励时才值得上手，单纯关注度不够。",
            "A DeFi project only becomes actionable when usable products, pools, points, or liquidity incentives appear; attention alone is not enough.",
        )
    elif "infra" in tags or "layer1" in tags or "layer2" in tags:
        add(
            "基础设施项目的早期窗口通常在测试网、节点/验证者、grant 和生态开发者计划，适合先看 builder 入口。",
            "Infrastructure projects usually expose early windows through testnets, nodes/validators, grants, and ecosystem builder programs.",
        )
    elif name:
        add(
            f"{name} 目前更像需要继续观察入口的早期项目，关键不是先下结论，而是等官方开放可执行路径。",
            f"{name} currently looks like an early project where the key is waiting for an executable official path, not rushing the conclusion.",
        )
    return theses


def _project_participation_actions(project: dict[str, Any], locale: str) -> list[str]:
    tags = _project_tags(project)
    summary = _project_summary(project).lower()
    actions: list[str] = []

    def add(zh: str, en: str) -> None:
        actions.append(zh if locale == "zh" else en)

    if "intent" in tags and "infra" in tags:
        add(
            "先找 SDK、开发者文档、集成伙伴申请和跨链/多协议 demo，能接入或试用的入口优先级最高。",
            "Look first for SDKs, developer docs, integration partner forms, and cross-protocol demos; anything you can integrate or test has priority.",
        )
    if "cloud computing" in tags or ("ai" in tags and ("layer1" in tags or "network" in summary)):
        add(
            "重点确认有没有 testnet、算力贡献、节点运行、研究者社区或模型/数据任务。",
            "Check for testnets, compute contribution, node running, research communities, or model/data tasks.",
        )
    if "bridge" in tags:
        add(
            "盯新增链支持、迁移活动、LP 激励和跨链任务，桥类项目的机会通常跟生态切换同步出现。",
            "Watch new-chain support, migration campaigns, LP incentives, and bridge tasks; bridge opportunities often appear with ecosystem shifts.",
        )
    if {"defi", "dex", "lending", "stablecoin protocol", "prediction market", "yield aggregator", "asset management", "onchain fund"} & tags:
        add(
            "优先看产品 beta、vault/资金池、积分、交易/预测任务和流动性激励是否已经开放。",
            "Prioritize product beta, vaults/pools, points, trading/prediction tasks, and liquidity incentives.",
        )
    if "crypto card" in tags or "payment" in tags:
        add(
            "找候补名单、邀请制开户、卡片权益、返现/积分和首批地区开放信息。",
            "Look for waitlists, invite onboarding, card perks, cashback/points, and first-region rollout details.",
        )
    if "insurance" in tags:
        add(
            "确认是否能作为资本提供者进入 vault、承保池或首批保险产品试用。",
            "Confirm whether you can join as a capital provider through vaults, underwriting pools, or first insurance product trials.",
        )
    if {"tools", "data & analysis", "on-chain data"} & tags:
        add(
            "优先找 dashboard beta、API key、数据贡献任务、研究员社区和开发者 grant。",
            "Look for dashboard beta, API keys, data contribution tasks, researcher communities, and developer grants.",
        )
    if {"ai", "fhe", "privacy", "r&d"} & tags and not any("研究" in item or "research" in item.lower() for item in actions):
        add(
            "找技术 demo、研究社区、白名单测试和合作集成入口，AI/隐私类项目通常更偏 builder 参与。",
            "Look for technical demos, research communities, whitelist testing, and integration access; AI/privacy projects often favor builders.",
        )
    if {"infra", "layer1", "layer2", "modular"} & tags and not any("testnet" in item.lower() or "测试网" in item for item in actions):
        add(
            "确认测试网、节点/验证者、builder program 和 grant 是否已经开放。",
            "Confirm whether testnet, nodes/validators, builder programs, or grants are open.",
        )
    return _dedupe_preserve_order(actions)


def infer_opportunity_thesis(project: dict[str, Any], locale: str = "en") -> list[str]:
    summary = _project_summary(project)
    tags = _project_tags(project)
    investors = _project_investors(project)
    team = _project_team(project)
    funding_signals = _project_funding_signals(project)
    funding_rounds = _project_funding_rounds(project)
    participation_signals = project_participation_signals(project)
    strong_participation = project_strong_participation_signals(project)
    source_ids = _project_source_ids(project)
    rank = _project_rank(project)
    theses: list[str] = []

    theses.extend(_project_shape_theses(project, locale)[:1])

    if funding_rounds:
        first_round = funding_rounds[0]
        round_name = str(first_round.get("round") or "").strip()
        amount = str(first_round.get("amount") or "").strip()
        if locale == "zh":
            if round_name and amount:
                theses.append(f"已看到 {round_name} 融资金额 {amount}，资金信号足够明确，下一步要看是否开放真实参与入口。")
            elif amount:
                theses.append(f"已看到融资金额 {amount}，下一步要看是否开放真实参与入口。")
            else:
                theses.append("已看到结构化融资记录，下一步要看是否开放真实参与入口。")
        else:
            if round_name and amount:
                theses.append(f"A {round_name} round of {amount} is visible; the next question is whether real access opens.")
            elif amount:
                theses.append(f"A funding amount of {amount} is visible; the next question is whether real access opens.")
            else:
                theses.append("Structured funding is visible; the next question is whether real access opens.")
    elif funding_signals:
        if locale == "zh":
            theses.append("已经出现公开融资线索，资金面只作为筛选权重，真正要看有没有内测、任务或激励入口。")
        else:
            theses.append("Public financing is visible, but the real edge is whether it is followed by beta, quests, or incentives.")
    elif investors:
        joined = ", ".join(investors[:3])
        if locale == "zh":
            theses.append(f"投资方里已经出现 {joined}，这更像是可继续追踪的资金确认信号，但还不能替代真实参与入口。")
        else:
            theses.append(f"Backers such as {joined} make this worth tracking, but they do not replace a real participation surface.")

    if strong_participation:
        if locale == "zh":
            theses.append("已经出现可参与信号，重点不再是围观热度，而是尽快确认入口是否真实开放。")
        else:
            theses.append("There is already a visible participation surface, so the focus is confirming whether the access path is actually live.")

    if rank is not None and rank <= 3:
        if locale == "zh":
            theses.append(f"RootData 排名已经到第 {rank}，说明市场注意力很靠前；如果入口开放，窗口可能不会太长。")
        else:
            theses.append(f"RootData rank #{rank} suggests attention is already near the front; if access opens, the window may be short.")
    elif rank is not None and rank <= 10 and not participation_signals and not funding_signals:
        if locale == "zh":
            theses.append(f"RootData 排名在前 {rank}，适合观察从关注度到可参与入口的转换，而不是只看热榜。")
        else:
            theses.append(f"RootData rank #{rank} is useful only if attention converts into an actual access path.")

    if len(source_ids) >= 2:
        if locale == "zh":
            theses.append(f"它同时被 {len(source_ids)} 类来源命中，优先级高于单一热榜项目。")
        else:
            theses.append(f"It appears across {len(source_ids)} source types, so it ranks above single-feed heat.")

    if team and len(theses) < 3:
        if locale == "zh":
            theses.append(f"团队信息相对透明，已识别 {len(team)} 位成员，后续追踪交付和活动更容易。")
        else:
            theses.append(f"Team visibility is decent with {len(team)} named members, making follow-up easier.")

    if not theses:
        if locale == "zh":
            theses.append("目前还没看到足够硬的融资或参与信号，只有在真实入口开放后才值得升级关注。")
        else:
            theses.append("There is not enough hard funding or participation evidence yet, so only upgrade this if a real access surface opens.")

    return _dedupe_preserve_order(theses)[:3]


def infer_participation_angle(project: dict[str, Any], locale: str = "en") -> list[str]:
    tags = _project_tags(project)
    summary = _project_summary(project).lower()
    investors = _project_investors(project)
    funding_signals = _project_funding_signals(project)
    funding_rounds = _project_funding_rounds(project)
    participation_signals = project_participation_signals(project)
    strong_participation = project_strong_participation_signals(project)
    actions: list[str] = []

    if strong_participation:
        joined = ", ".join(strong_participation[:3])
        actions.append(
            f"先直接核查这几个已出现的参与线索：{joined}。"
            if locale == "zh"
            else f"Start by verifying the participation cues already visible: {joined}."
        )

    actions.extend(_project_participation_actions(project, locale))
    if funding_signals or funding_rounds or investors:
        actions.append(
            "融资只用来决定是否值得盯；真正执行前必须找到官网、X 或文档里的可操作入口。"
            if locale == "zh"
            else "Use funding only to decide whether to watch; before acting, find an executable path on the site, X, or docs."
        )

    if not actions:
        actions.append(
            "先只盯官方站点和 X，等它放出 beta、testnet、quest 或积分入口再上手。"
            if locale == "zh"
            else "Just monitor the official site and X for now, and only act when beta, testnet, quest, or points access goes live."
        )

    return _dedupe_preserve_order(actions)[:4]


def infer_validation_sources(project: dict[str, Any], locale: str = "en") -> list[str]:
    tags = _project_tags(project)
    source_ids = {str(item).strip() for item in project.get("source_ids", [])}
    sources = [
        "官方公告 / 官方博客" if locale == "zh" else "Official announcements or project blog",
        "项目官方 X/Twitter" if locale == "zh" else "Project X/Twitter account",
    ]

    if project.get("website_url"):
        sources.append("官网产品页" if locale == "zh" else "Official product site")
    if "github_trending_builders" in source_ids or {"infra", "ai", "privacy", "fhe", "r&d"} & tags:
        sources.append("GitHub / 开发者文档" if locale == "zh" else "GitHub activity or developer docs")
    if {"defi", "lending", "dex", "perp", "stablecoin protocol"} & tags:
        sources.append("DeFiLlama / 链上数据面板" if locale == "zh" else "DeFiLlama or on-chain dashboards")
    if "rootdata_projects" in source_ids:
        sources.append("RootData 项目详情页" if locale == "zh" else "RootData project detail page")
    if _project_news_links(project):
        sources.append("相关新闻原文" if locale == "zh" else "Linked news coverage")

    return _dedupe_preserve_order(sources)[:5]


def infer_priority_checks(project: dict[str, Any], locale: str = "en") -> list[str]:
    tags = _project_tags(project)
    summary = _project_summary(project).lower()
    funding_signals = _project_funding_signals(project)
    funding_rounds = _project_funding_rounds(project)
    participation_signals = project_participation_signals(project)
    strong_participation = project_strong_participation_signals(project)
    checks: list[str] = []

    if funding_signals or funding_rounds:
        checks.append(
            "从融资新闻跳到官网和 X，确认是否已经挂出任务、waitlist、testnet、points 或合作申请入口。"
            if locale == "zh"
            else "Jump from funding coverage to the official site and X to confirm whether quests, waitlists, testnets, points, or partner applications are live."
        )
    if {"infra", "layer1", "layer2", "modular"} & tags:
        checks.append(
            "确认测试网、builder program、验证者计划或 grant 入口是不是已经开放。"
            if locale == "zh"
            else "Confirm whether testnet, builder program, validator access, or grants are already live."
        )
    if {"defi", "dex", "lending", "stablecoin protocol", "prediction market", "yield aggregator"} & tags:
        checks.append(
            "确认产品是不是已经开放候补、beta、积分、流动性挖矿或第一批金库权限。"
            if locale == "zh"
            else "Confirm whether waitlist, beta, points, liquidity mining, or first-wave vault access is already open."
        )
    if strong_participation:
        checks.append(
            "确认这些参与入口是不是当前真的可用，而不是只是文案或社区预告。"
            if locale == "zh"
            else "Confirm whether those participation surfaces are actually live rather than just mentioned in copy or community chatter."
        )
    if {"ai", "fhe", "privacy", "r&d"} & tags or "research" in summary:
        checks.append(
            "确认有没有开发者试点、技术 demo 或合作接入可以尽早参与。"
            if locale == "zh"
            else "Confirm whether there is a developer pilot, technical demo, or partner integration you can join early."
        )
    if not checks:
        checks.append(
            "确认第一层真实参与入口，而不是只看热度。"
            if locale == "zh"
            else "Confirm the first real participation surface instead of relying on attention alone."
        )

    return _dedupe_preserve_order(checks)[:3]


def default_run_state() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": utc_now_iso(),
        "active_run": None,
        "last_completed_run": None,
        "runs": [],
        "sources": {},
    }


def make_run_id(prefix: str = "run") -> str:
    return f"{prefix}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"


def load_run_state(state_dir: Path) -> dict[str, Any]:
    return read_json_file(state_dir / "run-state.json", default_run_state())


def write_run_state(state_dir: Path, run_state: dict[str, Any]) -> None:
    run_state["updated_at"] = utc_now_iso()
    write_json_file(state_dir / "run-state.json", run_state)


def mutate_run_state(state_dir: Path, mutator) -> None:
    ensure_dir(state_dir)
    lock_path = state_dir / ".run-state.lock"
    with lock_path.open("w", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        run_state = read_json_file(state_dir / "run-state.json", default_run_state())
        mutator(run_state)
        write_run_state(state_dir, run_state)
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def start_pipeline_run(state_dir: Path, source_id: str, top_n: int, skip_fetch: bool) -> str:
    run_id = make_run_id("pipeline")

    def mutator(run_state: dict[str, Any]) -> None:
        run_entry = {
            "run_id": run_id,
            "status": "running",
            "source_id": source_id,
            "top_n": top_n,
            "skip_fetch": skip_fetch,
            "started_at": utc_now_iso(),
            "finished_at": None,
            "current_stage": "init",
            "completed_stages": [],
            "error": None,
        }
        run_state["active_run"] = run_id
        run_state.setdefault("runs", []).append(run_entry)
        run_state["runs"] = run_state["runs"][-50:]

    mutate_run_state(state_dir, mutator)
    return run_id


def update_pipeline_stage(state_dir: Path, run_id: str, stage_name: str, completed: bool = False) -> None:
    def mutator(run_state: dict[str, Any]) -> None:
        for run in run_state.get("runs", []):
            if run.get("run_id") != run_id:
                continue
            run["current_stage"] = stage_name
            if completed:
                stages = list(run.get("completed_stages", []))
                if stage_name not in stages:
                    stages.append(stage_name)
                run["completed_stages"] = stages
            break

    mutate_run_state(state_dir, mutator)


def finish_pipeline_run(state_dir: Path, run_id: str, status: str, error: str | None = None) -> None:
    def mutator(run_state: dict[str, Any]) -> None:
        for run in run_state.get("runs", []):
            if run.get("run_id") != run_id:
                continue
            run["status"] = status
            run["finished_at"] = utc_now_iso()
            run["error"] = error
            break

        if run_state.get("active_run") == run_id:
            run_state["active_run"] = None
        if status == "completed":
            run_state["last_completed_run"] = run_id

    mutate_run_state(state_dir, mutator)


def default_event_memory() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": utc_now_iso(),
        "projects": {},
        "events": [],
    }


def default_watchlist() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": utc_now_iso(),
        "projects": [],
    }


def default_delivery_log() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": utc_now_iso(),
        "deliveries": [],
    }


def default_project_dossiers() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": utc_now_iso(),
        "projects": [],
    }
