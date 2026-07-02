#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
from datetime import UTC, datetime
from html import unescape
from pathlib import Path
from typing import Any

from common import ROOT, ensure_dir, load_effective_yaml, read_json_file, slugify, utc_now_iso, write_json_file


TAG_RULES = {
    "infra": ["infra", "infrastructure", "rollup", "sequencer", "modular", "rpc"],
    "ai x crypto": ["ai", "agent", "model", "inference"],
    "defi": ["defi", "dex", "amm", "lending", "yield", "restaking", "liquidity"],
    "consumer": ["consumer", "wallet", "social", "meme", "gaming"],
    "depin": ["depin", "compute", "gpu", "storage"],
}

CHAIN_RULES = {
    "solana": ["solana"],
    "base": ["base"],
    "ethereum": ["ethereum", "eth"],
    "bitcoin": ["bitcoin", "btc"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize cached BlockBeats payloads into opportunity records.")
    parser.add_argument("--input", help="Optional explicit cache JSON file path")
    parser.add_argument("--source-id", default="blockbeats_original_newsflash", help="Source id to annotate in normalized records")
    return parser.parse_args()


def find_latest_cache(cache_dir: Path, source_id: str) -> Path:
    needle = slugify(source_id)
    candidates = sorted([item for item in cache_dir.rglob("*.json") if needle in slugify(item.stem)])
    if not candidates:
        raise FileNotFoundError(f"No BlockBeats cache files found under {cache_dir} for source {source_id}")
    return candidates[-1]


def html_to_text(value: str) -> str:
    no_tags = re.sub(r"<[^>]+>", " ", value or "")
    collapsed = re.sub(r"\s+", " ", unescape(no_tags)).strip()
    return collapsed


def parse_observed_at(value: str, fallback: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return fallback
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(raw, fmt).replace(tzinfo=UTC)
            return parsed.isoformat().replace("+00:00", "Z")
        except ValueError:
            continue
    if raw.isdigit():
        try:
            return datetime.fromtimestamp(int(raw), tz=UTC).isoformat().replace("+00:00", "Z")
        except ValueError:
            return fallback
    return fallback


def infer_tags(text: str) -> list[str]:
    lowered = text.lower()
    tags: list[str] = []
    for tag, keywords in TAG_RULES.items():
        if any(keyword in lowered for keyword in keywords):
            tags.append(tag)
    return tags


def infer_chains(text: str) -> list[str]:
    lowered = text.lower()
    chains: list[str] = []
    for chain, keywords in CHAIN_RULES.items():
        if any(keyword in lowered for keyword in keywords):
            chains.append(chain.title())
    return chains


def build_entity_key(item: dict[str, Any], title: str, summary: str) -> str:
    preferred = item.get("url") or item.get("link") or title
    return slugify(str(preferred or summary or item.get("id") or "blockbeats"))


def blockbeats_feed_name(source_id: str) -> str:
    for name in ("financing", "important", "ai", "first", "onchain", "original"):
        if name in source_id:
            return name
    return "newsflash"


def build_record(item: dict[str, Any], source_id: str, fetched_at: str) -> dict[str, Any]:
    title = str(item.get("title") or f"blockbeats-{item.get('id')}").strip()
    content_text = html_to_text(str(item.get("content") or ""))
    combined_text = f"{title} {content_text}".strip()
    summary = content_text[:320] if content_text else title
    link = str(item.get("url") or item.get("link") or "").strip() or None
    tags = infer_tags(combined_text)
    chains = infer_chains(combined_text)
    feed_name = blockbeats_feed_name(source_id)
    signals = []
    if item.get("link"):
        signals.append(f"BlockBeats {feed_name} newsflash")
    if item.get("url"):
        signals.append("Contains outbound reference link")
    if feed_name == "financing":
        signals.append("Funding signal: BlockBeats financing")
    if feed_name in {"first", "important"}:
        signals.append(f"Launch signal: BlockBeats {feed_name}")

    return {
        "id": f"blockbeats:{item.get('id')}",
        "entity_key": build_entity_key(item, title, summary),
        "source_id": source_id,
        "source_type": f"blockbeats.newsflash.{feed_name}",
        "project_name": title,
        "project_url": link,
        "summary": summary,
        "category": "discovery",
        "chains": chains,
        "tags": tags,
        "signals": signals,
        "published_at": parse_observed_at(str(item.get("create_time") or ""), fetched_at),
        "observed_at": fetched_at,
        "confidence": 0.7 if feed_name in {"financing", "first", "important"} else 0.62,
        "raw_ref": {
            "blockbeats_id": item.get("id"),
            "link": item.get("link"),
            "url": item.get("url"),
        },
        "status": "candidate",
    }


def extract_records(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        return [item for item in data["data"] if isinstance(item, dict)]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def main() -> int:
    args = parse_args()
    config, _ = load_effective_yaml("config.yaml", "config.example.yaml")
    cache_dir = ROOT / str(config.get("profile", {}).get("cache_dir", "cache")) / "blockbeats"
    output_dir = ROOT / str(config.get("profile", {}).get("output_dir", "output")) / "normalized"
    ensure_dir(output_dir)

    input_path = Path(args.input).resolve() if args.input else find_latest_cache(cache_dir, args.source_id)
    artifact = read_json_file(input_path, {})
    fetched_at = artifact.get("fetched_at") or utc_now_iso()
    payload = artifact.get("response", {}).get("payload", {})
    records = extract_records(payload)

    normalized = [build_record(item, args.source_id, fetched_at) for item in records]
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

    print(f"PASS  Normalized BlockBeats records: {output_path.relative_to(ROOT)}")
    print(f"PASS  Opportunity records: {len(normalized)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
