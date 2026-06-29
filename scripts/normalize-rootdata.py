#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common import ROOT, ensure_dir, load_effective_yaml, read_json_file, slugify, utc_now_iso, write_json_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize cached RootData payloads into opportunity records.")
    parser.add_argument("--input", help="Optional explicit cache JSON file path")
    parser.add_argument("--source-id", default="rootdata_projects", help="Source id to annotate in normalized records")
    return parser.parse_args()


def find_latest_cache(cache_dir: Path) -> Path:
    candidates = sorted(cache_dir.rglob("*.json"), key=lambda item: (item.stat().st_mtime, str(item)))
    if not candidates:
        raise FileNotFoundError(f"No RootData cache files found under {cache_dir}")
    return candidates[-1]


def load_latest_detail_records(details_dir: Path) -> dict[int, dict[str, Any]]:
    if not details_dir.exists():
        return {}
    candidates = sorted(details_dir.rglob("*.json"), key=lambda item: (item.stat().st_mtime, str(item)))
    if not candidates:
        return {}
    mapping: dict[int, dict[str, Any]] = {}
    for candidate in candidates:
        artifact = read_json_file(candidate, {})
        records = artifact.get("records", [])
        for item in records:
            if not isinstance(item, dict):
                continue
            project_id = item.get("project_id")
            if isinstance(project_id, int):
                mapping[project_id] = item
    return mapping


def build_record(item: dict[str, Any], detail: dict[str, Any] | None, source_id: str, fetched_at: str) -> dict[str, Any]:
    project_id = item.get("project_id")
    project_name = item.get("project_name") or f"rootdata-{project_id}"
    project_url = (detail or {}).get("website_url") or item.get("rootdataurl") or item.get("X")
    tags = (detail or {}).get("tags") if isinstance((detail or {}).get("tags"), list) and (detail or {}).get("tags") else item.get("tags")
    tags = tags if isinstance(tags, list) else []
    summary = (detail or {}).get("details") or item.get("one_liner") or ""
    signal_parts = []

    rank = item.get("rank")
    if rank is not None:
        signal_parts.append(f"RootData hot rank: {rank}")
    if tags:
        signal_parts.append("Tags: " + ", ".join(str(tag).strip() for tag in tags if str(tag).strip()))
    founded = (detail or {}).get("founded")
    if founded:
        signal_parts.append(f"Founded: {founded}")
    investors = (detail or {}).get("investors") if isinstance((detail or {}).get("investors"), list) else []
    if investors:
        signal_parts.append("Investors: " + ", ".join(str(name).strip() for name in investors[:4] if str(name).strip()))
    funding_signals = (detail or {}).get("funding_signals") if isinstance((detail or {}).get("funding_signals"), list) else []
    if funding_signals:
        signal_parts.append("Funding signal: " + str(funding_signals[0]).strip())

    return {
        "id": f"rootdata:{project_id}",
        "entity_key": slugify(str(project_name)),
        "source_id": source_id,
        "source_type": "rootdata.hot_index",
        "project_name": project_name,
        "project_url": project_url,
        "summary": summary,
        "category": "discovery",
        "chains": [],
        "tags": [str(tag).strip() for tag in tags if str(tag).strip()],
        "signals": signal_parts,
        "published_at": None,
        "observed_at": fetched_at,
        "confidence": 0.7,
        "website_url": (detail or {}).get("website_url"),
        "x_url": (detail or {}).get("x_url") or item.get("X"),
        "founded": founded,
        "team": (detail or {}).get("team", []),
        "investors": investors,
        "funding_signals": funding_signals,
        "raw_ref": {
            "project_id": project_id,
            "x_url": item.get("X"),
            "rootdata_url": item.get("rootdataurl"),
            "detail_url": (detail or {}).get("detail_url"),
            "project_links": (detail or {}).get("project_links", []),
            "news_links": (detail or {}).get("news_links", []),
        },
        "status": "candidate",
    }


def main() -> int:
    args = parse_args()
    config, _ = load_effective_yaml("config.yaml", "config.example.yaml")
    cache_dir = ROOT / str(config.get("profile", {}).get("cache_dir", "cache")) / "rootdata"
    details_dir = ROOT / str(config.get("profile", {}).get("cache_dir", "cache")) / "rootdata-details"
    output_dir = ROOT / str(config.get("profile", {}).get("output_dir", "output")) / "normalized"
    ensure_dir(output_dir)

    input_path = Path(args.input).resolve() if args.input else find_latest_cache(cache_dir)
    artifact = read_json_file(input_path, {})
    fetched_at = artifact.get("fetched_at") or utc_now_iso()
    payload = artifact.get("response", {}).get("payload", {})
    records = payload.get("data", []) if isinstance(payload, dict) else []
    detail_records = load_latest_detail_records(details_dir)

    normalized = [
        build_record(item, detail_records.get(int(item.get("project_id"))) if str(item.get("project_id", "")).isdigit() else None, args.source_id, fetched_at)
        for item in records
        if isinstance(item, dict)
    ]
    output_path = output_dir / f"{input_path.stem}-normalized.json"
    write_json_file(
        output_path,
        {
            "source_id": args.source_id,
            "normalized_at": utc_now_iso(),
            "input_cache": str(input_path.relative_to(ROOT)),
            "input_details_cache_count": len(detail_records),
            "record_count": len(normalized),
            "records": normalized,
        },
    )

    print(f"PASS  Normalized RootData records: {output_path.relative_to(ROOT)}")
    print(f"PASS  Opportunity records: {len(normalized)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
