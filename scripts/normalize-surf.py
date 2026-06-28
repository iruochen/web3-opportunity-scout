#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common import ROOT, ensure_dir, load_effective_yaml, read_json_file, slugify, utc_now_iso, write_json_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize cached Surf payloads into opportunity records.")
    parser.add_argument("--input", help="Optional explicit cache JSON file path")
    parser.add_argument("--source-id", default="surf_project_ai_news")
    return parser.parse_args()


def find_latest_cache(cache_dir: Path) -> Path:
    candidates = sorted(cache_dir.rglob("*.json"), key=lambda item: (item.stat().st_mtime, str(item)))
    if not candidates:
        raise FileNotFoundError(f"No Surf cache files found under {cache_dir}")
    return candidates[-1]


def build_record(item: dict[str, Any], source_id: str, fetched_at: str) -> dict[str, Any]:
    title = str(item.get("title") or item.get("subtitle") or item.get("slug") or "surf-project").strip()
    slug = str(item.get("slug") or slugify(title)).strip()
    tldr = item.get("tldr", [])
    summary_bits = [str(item.get("subtitle") or "").strip()]
    if isinstance(tldr, list):
        summary_bits.extend(str(bit).strip() for bit in tldr[:3] if str(bit).strip())
    summary = " ".join(bit for bit in summary_bits if bit) or title
    signal_type = str(item.get("signal_type") or "surf_signal")
    twitter_author = item.get("twitter_author", {}) if isinstance(item.get("twitter_author"), dict) else {}
    follower_count = twitter_author.get("follower_count")
    signals = [f"Surf signal type: {signal_type}", f"Matched query: {item.get('_query', '')}"]
    if follower_count is not None:
        signals.append(f"Author followers: {follower_count}")
    project_url = None
    sources = item.get("sources", [])
    if isinstance(sources, list) and sources:
        first = sources[0]
        if isinstance(first, dict):
            project_url = first.get("url")
        elif isinstance(first, str):
            project_url = first
    source_tweet = item.get("source_tweet", {}) if isinstance(item.get("source_tweet"), dict) else {}
    if not project_url and source_tweet.get("tweet_id"):
        project_url = f"https://x.com/i/web/status/{source_tweet.get('tweet_id')}"
    tags = [signal_type.replace("_", " ")]
    query = str(item.get("_query") or "").strip()
    if query:
        tags.append(query.lower())
    return {
        "id": f"surf:{item.get('id') or slug}",
        "entity_key": slugify(slug),
        "source_id": source_id,
        "source_type": "surf.project.ai_news",
        "project_name": title,
        "project_url": project_url,
        "summary": summary,
        "category": "discovery",
        "chains": [],
        "tags": [tag for tag in tags if tag],
        "signals": signals,
        "published_at": item.get("timestamp"),
        "observed_at": fetched_at,
        "confidence": 0.72,
        "raw_ref": {
            "slug": slug,
            "signal_type": signal_type,
            "query": query,
        },
        "status": "candidate",
    }


def main() -> int:
    args = parse_args()
    config, _ = load_effective_yaml("config.yaml", "config.example.yaml")
    cache_dir = ROOT / str(config.get("profile", {}).get("cache_dir", "cache")) / "surf"
    output_dir = ROOT / str(config.get("profile", {}).get("output_dir", "output")) / "normalized"
    ensure_dir(output_dir)
    input_path = Path(args.input).resolve() if args.input else find_latest_cache(cache_dir)
    artifact = read_json_file(input_path, {})
    fetched_at = artifact.get("fetched_at") or utc_now_iso()
    payload = artifact.get("response", {}).get("payload", {})
    items = [item for item in payload.get("data", []) if isinstance(item, dict)]
    normalized = [build_record(item, args.source_id, fetched_at) for item in items]
    output_path = output_dir / f"{input_path.stem}-normalized.json"
    write_json_file(output_path, {
        "source_id": args.source_id,
        "normalized_at": utc_now_iso(),
        "input_cache": str(input_path.relative_to(ROOT)),
        "record_count": len(normalized),
        "records": normalized,
    })
    print(f"PASS  Normalized Surf records: {output_path.relative_to(ROOT)}")
    print(f"PASS  Opportunity records: {len(normalized)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
