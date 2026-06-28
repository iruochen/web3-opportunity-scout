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
    candidates = sorted(cache_dir.rglob("*.json"))
    if not candidates:
        raise FileNotFoundError(f"No RootData cache files found under {cache_dir}")
    return candidates[-1]


def build_record(item: dict[str, Any], source_id: str, fetched_at: str) -> dict[str, Any]:
    project_id = item.get("project_id")
    project_name = item.get("project_name") or f"rootdata-{project_id}"
    project_url = item.get("rootdataurl") or item.get("X")
    tags = item.get("tags") if isinstance(item.get("tags"), list) else []
    summary = item.get("one_liner") or ""
    signal_parts = []

    rank = item.get("rank")
    if rank is not None:
        signal_parts.append(f"RootData hot rank: {rank}")
    if tags:
        signal_parts.append("Tags: " + ", ".join(str(tag).strip() for tag in tags if str(tag).strip()))

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
        "raw_ref": {
            "project_id": project_id,
            "x_url": item.get("X"),
        },
        "status": "candidate",
    }


def main() -> int:
    args = parse_args()
    config, _ = load_effective_yaml("config.yaml", "config.example.yaml")
    cache_dir = ROOT / str(config.get("profile", {}).get("cache_dir", "cache")) / "rootdata"
    output_dir = ROOT / str(config.get("profile", {}).get("output_dir", "output")) / "normalized"
    ensure_dir(output_dir)

    input_path = Path(args.input).resolve() if args.input else find_latest_cache(cache_dir)
    artifact = read_json_file(input_path, {})
    fetched_at = artifact.get("fetched_at") or utc_now_iso()
    payload = artifact.get("response", {}).get("payload", {})
    records = payload.get("data", []) if isinstance(payload, dict) else []

    normalized = [build_record(item, args.source_id, fetched_at) for item in records if isinstance(item, dict)]
    output_path = output_dir / f"{input_path.stem}-normalized.json"
    write_json_file(
        output_path,
        {
            "source_id": args.source_id,
            "normalized_at": utc_now_iso(),
            "input_cache": str(input_path.relative_to(ROOT)),
            "record_count": len(normalized),
            "records": normalized,
        },
    )

    print(f"PASS  Normalized RootData records: {output_path.relative_to(ROOT)}")
    print(f"PASS  Opportunity records: {len(normalized)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
