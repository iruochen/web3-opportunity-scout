#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common import (
    ROOT,
    enabled_source_entries,
    ensure_dir,
    latest_json_file_for_source,
    load_effective_yaml,
    output_dir_from_config,
    slugify,
    utc_now_iso,
    write_json_file,
    read_json_file,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a combined normalized artifact from multiple source-normalized outputs.")
    parser.add_argument("--source-id", default="combined_market_scan")
    parser.add_argument("--include-source", action="append", dest="include_sources", help="Explicit source id to include. Can be repeated.")
    return parser.parse_args()


def resolve_source_ids(sources_config: dict[str, Any], explicit_sources: list[str] | None) -> list[str]:
    if explicit_sources:
        return [str(item).strip() for item in explicit_sources if str(item).strip()]

    source_ids: list[str] = []
    for _, entry in enabled_source_entries(sources_config):
        source_id = str(entry.get("id") or "").strip()
        adapter = str(entry.get("adapter") or "").strip()
        if not source_id or not adapter:
            continue
        if source_id == "combined_market_scan":
            continue
        if source_id not in source_ids:
            source_ids.append(source_id)
    return source_ids


def main() -> int:
    args = parse_args()
    config, _ = load_effective_yaml("config.yaml", "config.example.yaml")
    sources_config, _ = load_effective_yaml("sources.yaml", "sources.example.yaml")
    output_dir = output_dir_from_config(config)
    normalized_dir = output_dir / "normalized"
    ensure_dir(normalized_dir)

    source_ids = resolve_source_ids(sources_config, args.include_sources)
    combined_records: list[dict[str, Any]] = []
    input_sources: dict[str, str] = {}

    for source_id in source_ids:
        input_path = latest_json_file_for_source(normalized_dir, source_id)
        artifact = read_json_file(input_path, {})
        records = artifact.get("records", [])
        combined_records.extend([item for item in records if isinstance(item, dict)])
        input_sources[source_id] = str(input_path.relative_to(ROOT))

    output_path = normalized_dir / f"{utc_now_iso()[11:19].replace(':', '')}-{slugify(args.source_id)}-normalized.json"
    write_json_file(
        output_path,
        {
            "source_id": args.source_id,
            "normalized_at": utc_now_iso(),
            "input_sources": input_sources,
            "record_count": len(combined_records),
            "records": combined_records,
        },
    )

    print(f"PASS  Combined normalized artifact: {output_path.relative_to(ROOT)}")
    print(f"PASS  Included sources: {len(source_ids)}")
    print(f"PASS  Combined records: {len(combined_records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
