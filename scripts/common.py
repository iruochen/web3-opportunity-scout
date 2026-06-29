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


def infer_opportunity_thesis(project: dict[str, Any], locale: str = "en") -> list[str]:
    summary = _project_summary(project)
    tags = _project_tags(project)
    investors = _project_investors(project)
    team = _project_team(project)
    funding_signals = _project_funding_signals(project)
    participation_signals = project_participation_signals(project)
    strong_participation = project_strong_participation_signals(project)
    source_ids = _project_source_ids(project)
    rank = _project_rank(project)
    theses: list[str] = []

    if len(source_ids) >= 2:
        if locale == "zh":
            theses.append(f"它同时被 {len(source_ids)} 类来源命中，说明不是单点热度。")
        else:
            theses.append(f"It is showing up across {len(source_ids)} source types, which reduces single-feed noise.")

    if funding_signals:
        if locale == "zh":
            theses.append(f"已经出现公开融资线索，当前更值得盯融资后会不会跟出内测、合作或激励计划。")
        else:
            theses.append("Public financing signal is already visible, so the real edge is whether it is followed by beta, partnerships, or incentives.")
    elif investors:
        joined = ", ".join(investors[:3])
        if locale == "zh":
            theses.append(f"已经能看到投资方线索：{joined}，说明它不只是纯概念项目。")
        else:
            theses.append(f"Named backers are already visible: {joined}, which makes this more than a pure narrative mention.")

    if strong_participation:
        if locale == "zh":
            theses.append("已经出现可参与信号，重点不再是围观热度，而是尽快确认入口是否真实开放。")
        else:
            theses.append("There is already a visible participation surface, so the focus is confirming whether the access path is actually live.")

    if rank is not None and rank <= 10 and not participation_signals and not funding_signals:
        if locale == "zh":
            theses.append(f"RootData 热度已经到前 {rank}，说明注意力在形成，但还没完全挤满。")
        else:
            theses.append(f"RootData rank #{rank} shows attention is forming before the setup looks fully crowded.")

    if team:
        if locale == "zh":
            theses.append(f"详情页已经能看到 {len(team)} 位具名团队成员，后续追踪产品和活动会更容易。")
        else:
            theses.append(f"{len(team)} named team members are already visible, which makes follow-up easier.")

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

    if {"infra", "layer1", "layer2", "modular"} & tags or "blockchain" in summary or "network" in summary:
        actions.append(
            "优先盯测试网、开发者计划、验证者/节点计划和生态资助入口。"
            if locale == "zh"
            else "Prioritize testnet access, builder programs, validator or node programs, and ecosystem grants."
        )
    if {"defi", "dex", "lending", "stablecoin protocol", "prediction market", "yield aggregator", "asset management", "onchain fund"} & tags:
        actions.append(
            "优先盯候补、产品内测、积分机制、流动性激励和早期金库权限。"
            if locale == "zh"
            else "Prioritize waitlists, product beta access, points systems, liquidity incentives, and early vault access."
        )
    if {"ai", "fhe", "privacy", "r&d", "cloud computing"} & tags:
        actions.append(
            "优先找开发者预览、技术 demo、试点集成和研究社区入口。"
            if locale == "zh"
            else "Look for developer previews, technical demos, pilot integrations, and research community access."
        )
    if funding_signals or investors:
        actions.append(
            "把融资节点当成时间信号，重点观察融资后 1 到 3 周内有没有产品开放、合作公告或激励上线。"
            if locale == "zh"
            else "Use the financing event as a timing signal and watch the next one to three weeks for product access, partnerships, or incentives."
        )
    if {"consumer", "payment", "crypto card", "did"} & tags or "consumer" in summary:
        actions.append(
            "优先找候补名单、邀请制扩散、ambassador 计划和首批开户入口。"
            if locale == "zh"
            else "Look for waitlists, referral loops, ambassador programs, and first-wave onboarding access."
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
    investors = _project_investors(project)
    funding_signals = _project_funding_signals(project)
    participation_signals = project_participation_signals(project)
    strong_participation = project_strong_participation_signals(project)
    checks: list[str] = []

    if funding_signals or investors:
        checks.append(
            "确认融资轮次、领投方和融资后第一波要落地的产品/生态动作。"
            if locale == "zh"
            else "Confirm the financing round, lead backers, and the first product or ecosystem milestone expected after the raise."
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
