#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
import uuid
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
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


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


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def infer_participation_angle(tags: list[str], summary: str) -> list[str]:
    lowered_tags = {str(tag).strip().lower() for tag in tags}
    lowered_summary = summary.lower()
    suggestions: list[str] = []

    if {"layer1", "layer2", "infra", "modular"} & lowered_tags or "network" in lowered_summary or "blockchain" in lowered_summary:
        suggestions.append("Track testnet, validator, or ecosystem builder programs.")
    if {"ai", "fhe", "privacy", "cloud computing"} & lowered_tags:
        suggestions.append("Look for developer previews, research communities, or early integration programs.")
    if {"defi", "dex", "perp", "lending", "stablecoin protocol", "prediction market"} & lowered_tags:
        suggestions.append("Monitor product launch access, liquidity programs, and early user incentives.")
    if {"payment", "crypto card", "did", "consumer"} & lowered_tags or "consumer" in lowered_summary:
        suggestions.append("Watch for waitlists, referral programs, and user onboarding campaigns.")

    if not suggestions:
        suggestions.append("Check official channels for launch updates, partnerships, and early access opportunities.")

    return suggestions


def infer_validation_sources(tags: list[str], source_ids: list[str]) -> list[str]:
    lowered_tags = {str(tag).strip().lower() for tag in tags}
    suggestions = ["Official announcements", "Project X/Twitter account", "GitHub activity"]

    if {"defi", "lending", "dex", "perp", "stablecoin protocol"} & lowered_tags:
        suggestions.append("DeFiLlama listings or TVL changes")
    if {"infra", "layer1", "layer2", "modular"} & lowered_tags:
        suggestions.append("Ecosystem launch posts or developer documentation")
    if {"ai", "privacy", "fhe"} & lowered_tags:
        suggestions.append("Research threads, technical blog posts, or demo releases")
    if "rootdata_projects" in source_ids:
        suggestions.append("RootData project detail page")

    deduped: list[str] = []
    for item in suggestions:
        if item not in deduped:
            deduped.append(item)
    return deduped


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


def start_pipeline_run(state_dir: Path, source_id: str, top_n: int, skip_fetch: bool) -> str:
    run_state = load_run_state(state_dir)
    run_id = make_run_id("pipeline")
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
    write_run_state(state_dir, run_state)
    return run_id


def update_pipeline_stage(state_dir: Path, run_id: str, stage_name: str, completed: bool = False) -> None:
    run_state = load_run_state(state_dir)
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
    write_run_state(state_dir, run_state)


def finish_pipeline_run(state_dir: Path, run_id: str, status: str, error: str | None = None) -> None:
    run_state = load_run_state(state_dir)
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
    write_run_state(state_dir, run_state)


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
