#!/usr/bin/env python3

from __future__ import annotations

import argparse
from collections import defaultdict
from typing import Any
from urllib.parse import urlparse

from common import (
    default_event_memory,
    default_project_dossiers,
    ensure_dir,
    load_effective_yaml,
    output_dir_from_config,
    read_json_file,
    state_dir_from_config,
    latest_json_file_for_source,
    utc_now_iso,
    write_json_file,
    latest_json_file,
    ROOT,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge normalized opportunity records into canonical project entities.")
    parser.add_argument("--input", help="Optional path to normalized JSON file")
    parser.add_argument("--source-id", help="Source id to annotate during merge and to resolve latest artifacts")
    return parser.parse_args()


def normalized_domain(url: str | None) -> str | None:
    raw = str(url or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = parsed.netloc.lower().removeprefix("www.")
    if not host or "." not in host:
        return None
    blocked = {
        "rootdata.com",
        "x.com",
        "twitter.com",
        "theblockbeats.info",
        "github.com",
        "defillama.com",
    }
    if host in blocked or any(host.endswith(f".{domain}") for domain in blocked):
        return None
    return host


def canonical_group_key(record: dict[str, Any]) -> str:
    for field_name in ("website_url", "project_url"):
        domain = normalized_domain(record.get(field_name))
        if domain:
            return f"domain:{domain}"

    raw_ref = record.get("raw_ref", {})
    raw_ref = raw_ref if isinstance(raw_ref, dict) else {}
    x_url = str(record.get("x_url") or raw_ref.get("x_url") or "").strip()
    parsed_x = urlparse(x_url if "://" in x_url else f"https://{x_url}") if x_url else None
    if parsed_x and parsed_x.netloc.lower().removeprefix("www.") in {"x.com", "twitter.com"}:
        handle = parsed_x.path.strip("/").split("/")[0].lower()
        if handle:
            return f"x:{handle}"

    return str(record.get("entity_key", record.get("id")))


def pick_latest_observed(records: list[dict[str, Any]]) -> str | None:
    timestamps = [record.get("observed_at") for record in records if record.get("observed_at")]
    return sorted(timestamps)[-1] if timestamps else None


def pick_best_summary(records: list[dict[str, Any]]) -> str | None:
    candidates = [str(record.get("summary") or "").strip() for record in records if str(record.get("summary") or "").strip()]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (len(item), item))[-1]


def first_non_empty(records: list[dict[str, Any]], field_name: str) -> Any:
    for record in records:
        value = record.get(field_name)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if value not in (None, [], {}, ""):
            return value
    return None


def first_raw_ref_value(records: list[dict[str, Any]], field_name: str) -> str | None:
    for record in records:
        raw_ref = record.get("raw_ref", {})
        if not isinstance(raw_ref, dict):
            continue
        value = str(raw_ref.get(field_name) or "").strip()
        if value:
            return value
    return None


def merge_people(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for record in records:
        team = record.get("team", [])
        if not isinstance(team, list):
            continue
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


def merge_strings(records: list[dict[str, Any]], field_name: str) -> list[str]:
    values: list[str] = []
    for record in records:
        items = record.get(field_name, [])
        if not isinstance(items, list):
            continue
        for item in items:
            text = str(item).strip()
            if text and text not in values:
                values.append(text)
    return values


def merge_news_links(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    values: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for record in records:
        raw_ref = record.get("raw_ref", {})
        if not isinstance(raw_ref, dict):
            continue
        news_links = raw_ref.get("news_links", [])
        if not isinstance(news_links, list):
            continue
        for item in news_links:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            title = str(item.get("title") or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            values.append({"title": title, "url": url})
    return values


def merge_funding_rounds(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for record in records:
        rounds = record.get("funding_rounds", [])
        if not isinstance(rounds, list):
            continue
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
            values.append({"round": round_name, "amount": amount, "date": date, "investors": investors})
    return values


def merge_group(entity_key: str, records: list[dict[str, Any]], source_id: str) -> dict[str, Any]:
    primary = records[0]
    tags: list[str] = []
    signals: list[str] = []
    aliases: list[str] = []
    seen_ids: list[str] = []

    for record in records:
        seen_ids.append(str(record.get("id")))
        name = str(record.get("project_name", "")).strip()
        if name and name not in aliases:
            aliases.append(name)
        for tag in record.get("tags", []):
            text = str(tag).strip()
            if text and text not in tags:
                tags.append(text)
        for signal in record.get("signals", []):
            text = str(signal).strip()
            if text and text not in signals:
                signals.append(text)

    return {
        "entity_key": entity_key,
        "canonical_name": primary.get("project_name"),
        "aliases": aliases,
        "source_ids": sorted({str(record.get("source_id")) for record in records}),
        "project_url": first_non_empty(records, "project_url"),
        "website_url": first_non_empty(records, "website_url"),
        "x_url": first_non_empty(records, "x_url"),
        "rootdata_url": first_raw_ref_value(records, "rootdata_url"),
        "detail_url": first_raw_ref_value(records, "detail_url"),
        "summary": pick_best_summary(records) or primary.get("summary"),
        "category": primary.get("category", "discovery"),
        "chains": primary.get("chains", []),
        "tags": tags,
        "signals": signals,
        "founded": first_non_empty(records, "founded"),
        "team": merge_people(records),
        "investors": merge_strings(records, "investors"),
        "funding_rounds": merge_funding_rounds(records),
        "funding_signals": merge_strings(records, "funding_signals"),
        "news_links": merge_news_links(records),
        "confidence": max(float(record.get("confidence", 0.0)) for record in records),
        "observed_at": pick_latest_observed(records),
        "record_count": len(records),
        "records": records,
        "record_ids": seen_ids,
        "status": "merged",
        "source_type": primary.get("source_type"),
        "source_id": source_id,
    }


def update_state_files(merged_projects: list[dict[str, Any]], state_dir) -> None:
    event_memory_path = state_dir / "event-memory.json"
    event_memory = read_json_file(event_memory_path, default_event_memory())
    event_memory["updated_at"] = utc_now_iso()

    projects = dict(event_memory.get("projects", {}))
    events = list(event_memory.get("events", []))
    for project in merged_projects:
        entity_key = project["entity_key"]
        project_state = dict(projects.get(entity_key, {}))
        first_seen_at = project_state.get("first_seen_at") or project.get("observed_at") or utc_now_iso()
        seen_count = int(project_state.get("seen_count", 0)) + 1
        project_state.update(
            {
                "entity_key": entity_key,
                "project_name": project.get("canonical_name"),
                "project_url": project.get("project_url"),
                "first_seen_at": first_seen_at,
                "last_seen_at": project.get("observed_at"),
                "seen_count": seen_count,
                "last_source_ids": project.get("source_ids", []),
                "last_tags": project.get("tags", []),
            }
        )
        projects[entity_key] = project_state
        events.append(
            {
                "event_type": "entity_merged",
                "entity_key": entity_key,
                "observed_at": project.get("observed_at"),
                "record_count": project.get("record_count"),
                "source_ids": project.get("source_ids", []),
            }
        )

    event_memory["projects"] = projects
    event_memory["events"] = events[-1000:]
    write_json_file(event_memory_path, event_memory)

    dossiers_path = state_dir / "project-dossiers.json"
    dossiers = read_json_file(dossiers_path, default_project_dossiers())
    dossiers["updated_at"] = utc_now_iso()
    existing = {item.get("entity_key"): item for item in dossiers.get("projects", []) if isinstance(item, dict)}
    for project in merged_projects:
        existing[project["entity_key"]] = {
            "entity_key": project["entity_key"],
            "project_name": project.get("canonical_name"),
            "project_url": project.get("project_url"),
            "summary": project.get("summary"),
            "tags": project.get("tags", []),
            "signals": project.get("signals", []),
            "last_observed_at": project.get("observed_at"),
            "source_ids": project.get("source_ids", []),
        }
    dossiers["projects"] = sorted(existing.values(), key=lambda item: str(item.get("project_name", "")).lower())
    write_json_file(dossiers_path, dossiers)


def main() -> int:
    args = parse_args()
    config, _ = load_effective_yaml("config.yaml", "config.example.yaml")
    output_dir = output_dir_from_config(config)
    state_dir = state_dir_from_config(config)
    ensure_dir(output_dir / "merged")

    resolved_source_id = args.source_id
    if args.input:
        input_path = ROOT / args.input
    else:
        filtered_dir = output_dir / "filtered"
        if filtered_dir.exists() and resolved_source_id:
            input_path = latest_json_file_for_source(filtered_dir, resolved_source_id)
        elif filtered_dir.exists():
            input_path = latest_json_file(filtered_dir)
        elif resolved_source_id:
            input_path = latest_json_file_for_source(output_dir / "normalized", resolved_source_id)
        else:
            input_path = latest_json_file(output_dir / "normalized")
    normalized_artifact = read_json_file(input_path, {})
    if not resolved_source_id:
        resolved_source_id = str(normalized_artifact.get("source_id", "unknown"))
    records = normalized_artifact.get("records", [])

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if not isinstance(record, dict):
            continue
        grouped[canonical_group_key(record)].append(record)

    merged_projects = [
        merge_group(entity_key, group_records, resolved_source_id)
        for entity_key, group_records in sorted(grouped.items())
    ]

    output_path = output_dir / "merged" / f"{input_path.stem.replace('-normalized', '')}-merged.json"
    write_json_file(
        output_path,
        {
            "source_id": resolved_source_id,
            "merged_at": utc_now_iso(),
            "input_normalized": str(input_path.relative_to(ROOT)),
            "project_count": len(merged_projects),
            "projects": merged_projects,
        },
    )

    update_state_files(merged_projects, state_dir)
    print(f"PASS  Merged projects: {output_path.relative_to(ROOT)}")
    print(f"PASS  Canonical entities: {len(merged_projects)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
