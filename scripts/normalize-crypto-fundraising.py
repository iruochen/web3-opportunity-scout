#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
from html import unescape
from pathlib import Path
from typing import Any

from common import ROOT, ensure_dir, load_effective_yaml, read_json_file, slugify, utc_now_iso, write_json_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize Crypto Fundraising public table rows into opportunity records.")
    parser.add_argument("--input", help="Optional explicit cache JSON file path")
    parser.add_argument("--source-id", default="crypto_fundraising_recent")
    return parser.parse_args()


def find_latest_cache(cache_dir: Path) -> Path:
    candidates = sorted(cache_dir.rglob("*.json"), key=lambda item: (item.stat().st_mtime, str(item)))
    if not candidates:
        raise FileNotFoundError(f"No Crypto Fundraising cache files found under {cache_dir}")
    return candidates[-1]


def strip_tags(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", unescape(value or ""))).strip()


def split_rows(html: str) -> list[str]:
    marker = '<div class="hp-table-row hpt-data"'
    chunks = html.split(marker)[1:]
    rows: list[str] = []
    for chunk in chunks:
        next_idx = chunk.find(marker)
        row = chunk if next_idx < 0 else chunk[:next_idx]
        rows.append(marker + row)
    return rows


def extract_first(pattern: str, text: str) -> str:
    match = re.search(pattern, text, flags=re.DOTALL | re.IGNORECASE)
    return strip_tags(match.group(1)) if match else ""


def extract_all(pattern: str, text: str) -> list[str]:
    values: list[str] = []
    for match in re.finditer(pattern, text, flags=re.DOTALL | re.IGNORECASE):
        value = strip_tags(match.group(1))
        if value and value not in values:
            values.append(value)
    return values


def parse_row(row: str, source_id: str, fetched_at: str) -> dict[str, Any] | None:
    name = extract_first(r'<h5 class="cointitle">(.*?)</h5>', row)
    if not name:
        return None
    ticker = extract_first(r'<span class="cointag">(.*?)</span>', row)
    href = extract_first(r'<a class="t-project-link" href="(.*?)"', row)
    cols = extract_all(r'<div class="hpt-col3[^"]*">(.*?)</div>', row)
    round_name = cols[0] if cols else ""
    date = cols[1] if len(cols) > 1 else ""
    amount = extract_first(r'<span class="abbrusd">(.*?)</span>', row)
    categories = extract_all(r'<span[^>]*class="catitem"[^>]*>(.*?)</span>', row)
    investor_text = extract_first(r'<div class="mob-only investlist">(.*?)</div>', row)
    investors = [item.strip() for item in re.split(r"\s*,\s*", investor_text) if item.strip()]
    for value in extract_all(r'title="([^"]+)"', row):
        if value and value not in investors:
            investors.append(value)

    project_url = f"https://crypto-fundraising.info{href}" if href.startswith("/") else href or None
    funding_round = {
        "round": round_name,
        "amount": amount,
        "date": date,
        "investors": investors,
    }
    early_rounds = {"pre-seed", "pre seed", "seed", "angel", "grant"}
    token_status = "pre_token_likely" if not ticker and round_name.strip().lower() in early_rounds else "unknown"
    if ticker:
        token_status = "token_live"
    summary_parts = [f"{name} reported a {round_name or 'funding'} round"]
    if amount:
        summary_parts.append(f"raising ${amount}")
    if categories:
        summary_parts.append("across " + ", ".join(categories[:4]))
    summary = " ".join(summary_parts).strip() + "."

    signals = ["Crypto Fundraising recent deal"]
    if round_name:
        signals.append(f"Funding round: {round_name} {amount}".strip())
    if investors:
        signals.append("Investors: " + ", ".join(investors[:4]))
    if ticker:
        signals.append(f"Token ticker visible: {ticker}")

    return {
        "id": f"crypto-fundraising:{slugify(name)}:{slugify(round_name or date)}",
        "entity_key": slugify(name),
        "source_id": source_id,
        "source_type": "crypto-fundraising.recent",
        "project_name": name,
        "project_url": project_url,
        "summary": summary,
        "category": "market",
        "chains": [item.replace(" Ecosystem", "") for item in categories if item.endswith("Ecosystem")],
        "tags": categories,
        "signals": signals,
        "published_at": date,
        "observed_at": fetched_at,
        "confidence": 0.74,
        "investors": investors,
        "funding_rounds": [funding_round] if any(funding_round.values()) else [],
        "funding_signals": [signals[1]] if len(signals) > 1 else [],
        "token_status": token_status,
        "raw_ref": {"ticker": ticker, "source_url": project_url},
        "status": "candidate",
    }


def main() -> int:
    args = parse_args()
    config, _ = load_effective_yaml("config.yaml", "config.example.yaml")
    cache_dir = ROOT / str(config.get("profile", {}).get("cache_dir", "cache")) / "crypto-fundraising"
    output_dir = ROOT / str(config.get("profile", {}).get("output_dir", "output")) / "normalized"
    ensure_dir(output_dir)
    input_path = Path(args.input).resolve() if args.input else find_latest_cache(cache_dir)
    artifact = read_json_file(input_path, {})
    fetched_at = artifact.get("fetched_at") or utc_now_iso()
    html = artifact.get("response", {}).get("html", "")
    normalized = [record for row in split_rows(html) if (record := parse_row(row, args.source_id, fetched_at))]
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
    print(f"PASS  Normalized Crypto Fundraising records: {output_path.relative_to(ROOT)}")
    print(f"PASS  Opportunity records: {len(normalized)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
