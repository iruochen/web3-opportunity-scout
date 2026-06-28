#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common import ROOT, ensure_dir, latest_json_file, latest_json_file_for_source, load_effective_yaml, output_dir_from_config, read_json_file, utc_now_iso, write_json_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply profile-based candidate filters to normalized records.")
    parser.add_argument("--input", help="Optional path to normalized JSON file")
    parser.add_argument("--source-id", help="Resolve the latest normalized artifact for this source when --input is omitted")
    parser.add_argument("--profile", help="Filter profile name; defaults to config.filters.active_profile")
    return parser.parse_args()


def get_filter_profile(config: dict[str, Any], profile_name: str | None) -> tuple[str, dict[str, Any]]:
    filters = config.get("filters", {})
    if not isinstance(filters, dict):
        return "opportunity", {}
    resolved_name = str(profile_name or filters.get("active_profile", "opportunity"))
    profiles = filters.get("profiles", {})
    if not isinstance(profiles, dict):
        return resolved_name, {}
    profile = profiles.get(resolved_name, {})
    return resolved_name, profile if isinstance(profile, dict) else {}


def get_source_override(sources_config: dict[str, Any], source_id: str, profile_name: str) -> dict[str, Any]:
    sources = sources_config.get("sources", {})
    if not isinstance(sources, dict):
        return {}
    for entries in sources.values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("id") != source_id:
                continue
            profiles = entry.get("filter_profiles", {})
            if not isinstance(profiles, dict):
                return {}
            override = profiles.get(profile_name, {})
            return override if isinstance(override, dict) else {}
    return {}


def merged_filter_rules(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key in {"include_any_tags", "exclude_title_keywords", "exclude_summary_keywords"}:
            merged[key] = list(value) if isinstance(value, list) else []
        else:
            merged[key] = value
    return merged


def contains_any(text: str, keywords: list[str]) -> str | None:
    lowered = text.lower()
    for keyword in keywords:
        token = str(keyword).strip().lower()
        if token and token in lowered:
            return str(keyword)
    return None


def evaluate_record(record: dict[str, Any], rules: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    confidence = float(record.get("confidence", 0.0))
    min_confidence = float(rules.get("min_confidence", 0.0))
    if confidence < min_confidence:
        reasons.append(f"confidence<{min_confidence}")

    tags = {str(tag).strip().lower() for tag in record.get("tags", [])}
    include_any_tags = [str(item).strip().lower() for item in rules.get("include_any_tags", []) if str(item).strip()]
    if include_any_tags and not (tags & set(include_any_tags)):
        reasons.append("missing_required_tags")

    title = str(record.get("project_name", "")).strip()
    summary = str(record.get("summary", "")).strip()

    title_hit = contains_any(title, list(rules.get("exclude_title_keywords", [])))
    if title_hit:
        reasons.append(f"title_keyword:{title_hit}")

    summary_hit = contains_any(summary, list(rules.get("exclude_summary_keywords", [])))
    if summary_hit:
        reasons.append(f"summary_keyword:{summary_hit}")

    return reasons


def main() -> int:
    args = parse_args()
    config, _ = load_effective_yaml("config.yaml", "config.example.yaml")
    sources_config, _ = load_effective_yaml("sources.yaml", "sources.example.yaml")
    output_dir = output_dir_from_config(config)
    ensure_dir(output_dir / "filtered")

    if args.input:
        input_path = ROOT / args.input
    elif args.source_id:
        input_path = latest_json_file_for_source(output_dir / "normalized", args.source_id)
    else:
        input_path = latest_json_file(output_dir / "normalized")
    normalized_artifact = read_json_file(input_path, {})
    source_id = str(normalized_artifact.get("source_id", "unknown"))
    records = normalized_artifact.get("records", [])

    profile_name, profile_rules = get_filter_profile(config, args.profile)
    source_override = get_source_override(sources_config, source_id, profile_name)
    rules = merged_filter_rules(profile_rules, source_override)

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        reasons = evaluate_record(record, rules)
        if reasons:
            rejected.append(
                {
                    "record": record,
                    "rejection_reasons": reasons,
                }
            )
        else:
            accepted.append(record)

    output_path = output_dir / "filtered" / f"{input_path.stem.replace('-normalized', '')}-filtered.json"
    write_json_file(
        output_path,
        {
            "source_id": source_id,
            "profile": profile_name,
            "filtered_at": utc_now_iso(),
            "input_normalized": str(input_path.relative_to(ROOT)),
            "record_count": len(accepted),
            "rejected_count": len(rejected),
            "rules": rules,
            "records": accepted,
            "rejected_records": rejected,
        },
    )

    print(f"PASS  Filtered candidates: {output_path.relative_to(ROOT)}")
    print(f"PASS  Accepted records: {len(accepted)}")
    print(f"PASS  Rejected records: {len(rejected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
