#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common import ROOT, ensure_dir, load_effective_yaml, read_json_file, slugify, utc_now_iso, write_json_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize cached GitHub payloads into opportunity records.")
    parser.add_argument("--input", help="Optional explicit cache JSON file path")
    parser.add_argument("--source-id", default="github_trending_builders")
    return parser.parse_args()


def find_latest_cache(cache_dir: Path) -> Path:
    candidates = sorted(cache_dir.rglob("*.json"), key=lambda item: (item.stat().st_mtime, str(item)))
    if not candidates:
        raise FileNotFoundError(f"No GitHub cache files found under {cache_dir}")
    return candidates[-1]


def infer_tags(item: dict[str, Any]) -> list[str]:
    tags = [str(topic).strip().lower() for topic in item.get("topics", []) if str(topic).strip()]
    language = str(item.get("language") or "").strip()
    if language:
        tags.append(language.lower())
    description = str(item.get("description") or "").lower()
    for tag in ("defi", "infra", "consumer", "devtools", "ai x crypto"):
        if tag.replace(" x ", " ") in description or tag in description:
            tags.append(tag)
    deduped: list[str] = []
    for tag in tags:
        if tag not in deduped:
            deduped.append(tag)
    return deduped


def infer_chains(text: str) -> list[str]:
    lowered = text.lower()
    chains = []
    for chain in ("solana", "base", "ethereum", "bitcoin"):
        if chain in lowered:
            chains.append(chain.title())
    return chains


def repo_momentum_label(item: dict[str, Any]) -> str:
    stars = int(item.get("stargazers_count") or 0)
    forks = int(item.get("forks_count") or 0)
    if stars >= 300 or forks >= 50:
        return "strong builder momentum"
    if stars >= 50 or forks >= 10:
        return "visible builder momentum"
    return "early builder activity"


def build_record(item: dict[str, Any], source_id: str, fetched_at: str) -> dict[str, Any]:
    full_name = str(item.get("full_name") or item.get("name") or "github-repo").strip()
    description = str(item.get("description") or "").strip()
    topics = infer_tags(item)
    query = str(item.get("_query") or "").strip()
    owner = str(item.get("owner", {}).get("login") or "").strip()
    pushed_at = item.get("pushed_at")
    signals = [
        f"GitHub builder signal: {repo_momentum_label(item)}",
        f"GitHub stars: {item.get('stargazers_count', 0)}",
        f"GitHub forks: {item.get('forks_count', 0)}",
        f"GitHub pushed at: {pushed_at}",
        f"Matched query: {query}",
    ]
    return {
        "id": f"github:{full_name}",
        "entity_key": slugify(full_name),
        "source_id": source_id,
        "source_type": "github.search.repositories",
        "project_name": full_name,
        "project_url": item.get("html_url"),
        "summary": description or full_name,
        "category": "discovery",
        "chains": infer_chains(f"{full_name} {description}"),
        "tags": topics,
        "signals": signals,
        "published_at": item.get("created_at"),
        "observed_at": fetched_at,
        "confidence": 0.6,
        "raw_ref": {
            "query": query,
            "pushed_at": item.get("pushed_at"),
            "language": item.get("language"),
            "owner": owner,
            "open_issues_count": item.get("open_issues_count"),
            "watchers_count": item.get("watchers_count"),
        },
        "status": "candidate",
    }


def main() -> int:
    args = parse_args()
    config, _ = load_effective_yaml("config.yaml", "config.example.yaml")
    cache_dir = ROOT / str(config.get("profile", {}).get("cache_dir", "cache")) / "github"
    output_dir = ROOT / str(config.get("profile", {}).get("output_dir", "output")) / "normalized"
    ensure_dir(output_dir)
    input_path = Path(args.input).resolve() if args.input else find_latest_cache(cache_dir)
    artifact = read_json_file(input_path, {})
    fetched_at = artifact.get("fetched_at") or utc_now_iso()
    payload = artifact.get("response", {}).get("payload", {})
    items = [item for item in payload.get("items", []) if isinstance(item, dict)]
    normalized = [build_record(item, args.source_id, fetched_at) for item in items]
    output_path = output_dir / f"{input_path.stem}-normalized.json"
    write_json_file(output_path, {
        "source_id": args.source_id,
        "normalized_at": utc_now_iso(),
        "input_cache": str(input_path.relative_to(ROOT)),
        "record_count": len(normalized),
        "records": normalized,
    })
    print(f"PASS  Normalized GitHub records: {output_path.relative_to(ROOT)}")
    print(f"PASS  Opportunity records: {len(normalized)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
