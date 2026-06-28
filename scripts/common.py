#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
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


def latest_json_file(path: Path) -> Path:
    candidates = sorted(path.rglob("*.json"))
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
