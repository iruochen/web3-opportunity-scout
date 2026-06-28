#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common import ROOT, ensure_dir, load_effective_yaml, read_json_file, slugify, utc_now_iso, write_json_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize cached DeFiLlama payloads into opportunity records.")
    parser.add_argument("--input", help="Optional explicit cache JSON file path")
    parser.add_argument("--source-id", default="defillama_new_protocols")
    return parser.parse_args()


def find_latest_cache(cache_dir: Path) -> Path:
    candidates = sorted(cache_dir.rglob("*.json"), key=lambda item: (item.stat().st_mtime, str(item)))
    if not candidates:
        raise FileNotFoundError(f"No DeFiLlama cache files found under {cache_dir}")
    return candidates[-1]


def build_record(item: dict[str, Any], source_id: str, fetched_at: str) -> dict[str, Any]:
    name = str(item.get("name") or item.get("slug") or "defillama-protocol").strip()
    slug = str(item.get("slug") or slugify(name))
    chains = [str(chain).strip() for chain in item.get("chains", []) if str(chain).strip()]
    category = str(item.get("category") or "defi").strip()
    tvl = item.get("tvl")
    tvl_text = f"TVL: {tvl}" if tvl is not None else None
    change_1d = item.get("change_1d")
    change_text = f"24h TVL change: {change_1d}" if change_1d is not None else None
    signals = [text for text in [tvl_text, change_text] if text]
    tags = [category] + [str(module).strip() for module in item.get("module", [])] if isinstance(item.get("module"), list) else [category]
    summary_parts = []
    if category:
        summary_parts.append(f"Category: {category}.")
    if chains:
        summary_parts.append(f"Chains: {', '.join(chains[:5])}.")
    if tvl is not None:
        summary_parts.append(f"TVL currently reported at {tvl}.")
    return {
        "id": f"defillama:{slug}",
        "entity_key": slugify(slug),
        "source_id": source_id,
        "source_type": "defillama.protocols",
        "project_name": name,
        "project_url": item.get("url") or item.get("website"),
        "summary": " ".join(summary_parts).strip(),
        "category": "discovery",
        "chains": chains,
        "tags": [tag for tag in tags if tag],
        "signals": signals,
        "published_at": None,
        "observed_at": fetched_at,
        "confidence": 0.66,
        "raw_ref": {
            "slug": slug,
            "tvl": tvl,
            "twitter": item.get("twitter"),
        },
        "status": "candidate",
    }


def main() -> int:
    args = parse_args()
    config, _ = load_effective_yaml("config.yaml", "config.example.yaml")
    cache_dir = ROOT / str(config.get("profile", {}).get("cache_dir", "cache")) / "defillama"
    output_dir = ROOT / str(config.get("profile", {}).get("output_dir", "output")) / "normalized"
    ensure_dir(output_dir)
    input_path = Path(args.input).resolve() if args.input else find_latest_cache(cache_dir)
    artifact = read_json_file(input_path, {})
    fetched_at = artifact.get("fetched_at") or utc_now_iso()
    payload = artifact.get("response", {}).get("payload", [])
    records = [item for item in payload if isinstance(item, dict)]
    normalized = [build_record(item, args.source_id, fetched_at) for item in records]
    output_path = output_dir / f"{input_path.stem}-normalized.json"
    write_json_file(output_path, {
        "source_id": args.source_id,
        "normalized_at": utc_now_iso(),
        "input_cache": str(input_path.relative_to(ROOT)),
        "record_count": len(normalized),
        "records": normalized,
    })
    print(f"PASS  Normalized DeFiLlama records: {output_path.relative_to(ROOT)}")
    print(f"PASS  Opportunity records: {len(normalized)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
