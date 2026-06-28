#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from common import ROOT, default_run_state, ensure_dir, find_source_definition, load_dotenv_file, load_effective_yaml, read_json_file, slugify, utc_now_iso, write_json_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch GitHub search payloads into raw cache.")
    parser.add_argument("--source-id", default="github_trending_builders")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--days", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def build_query_strings(source_def: dict[str, Any], limit: int | None, days: int | None) -> tuple[list[str], dict[str, Any]]:
    request_cfg = dict(source_def.get("request", {}))
    base_query = dict(request_cfg.get("query", {}))
    queries = [str(item).strip() for item in request_cfg.get("queries", []) if str(item).strip()]
    per_page = int(limit or base_query.get("per_page", 10))
    if days is not None:
        cutoff = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")
    else:
        cutoff = None
    search_queries = []
    for item in queries or ["web3"]:
        q = f"{item} pushed:>={cutoff}" if cutoff else item
        search_queries.append(q)
    base_query["per_page"] = per_page
    request_cfg["query"] = base_query
    return search_queries, request_cfg


def perform_request(url: str, headers: dict[str, str]) -> tuple[int, Any]:
    request = Request(url=url, method="GET", headers=headers)
    with urlopen(request, timeout=30) as response:
        payload = response.read().decode("utf-8")
        return response.status, json.loads(payload)


def cache_file_path(source_id: str, cache_dir_name: str) -> Path:
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    timestamp = datetime.now(UTC).strftime("%H%M%S")
    return ROOT / cache_dir_name / "github" / today / f"{timestamp}-{slugify(source_id)}.json"


def update_run_state(state_dir_name: str, source_id: str, status: str, url: str, cache_path: Path | None, error: str | None, record_count: int | None) -> None:
    run_state_path = ROOT / state_dir_name / "run-state.json"
    run_state = read_json_file(run_state_path, default_run_state())
    run_state["updated_at"] = utc_now_iso()
    source_state = dict(run_state.get("sources", {}).get(source_id, {}))
    source_state["last_status"] = status
    source_state["last_fetch_at"] = utc_now_iso()
    source_state["last_request_url"] = url
    source_state["last_cache_path"] = str(cache_path.relative_to(ROOT)) if cache_path else None
    source_state["last_error"] = error
    source_state["last_record_count"] = record_count
    run_state.setdefault("sources", {})[source_id] = source_state
    write_json_file(run_state_path, run_state)


def main() -> int:
    load_dotenv_file()
    args = parse_args()
    config, _ = load_effective_yaml("config.yaml", "config.example.yaml")
    sources_config, _ = load_effective_yaml("sources.yaml", "sources.example.yaml")
    _, source_def = find_source_definition(sources_config, args.source_id)
    profile = config.get("profile", {})
    cache_dir_name = str(profile.get("cache_dir", "cache"))
    state_dir_name = str(profile.get("state_dir", "state"))
    search_queries, request_cfg = build_query_strings(source_def, args.limit, args.days)
    base_url = str(request_cfg.get("base_url", "")).rstrip("/")
    path = str(request_cfg.get("path", "")).strip()
    headers = {str(key): str(value) for key, value in request_cfg.get("headers", {}).items()}
    token = os.getenv(str(source_def.get("auth", {}).get("env", "")))
    if token:
        headers[str(source_def.get("auth", {}).get("header", "Authorization"))] = f"Bearer {token}"

    if args.dry_run:
        for q in search_queries:
            params = dict(request_cfg.get("query", {}))
            params["q"] = q
            url = f"{base_url}{path}?{urlencode(params)}"
            print(f"Request URL: {url}")
        print("Dry run only. No network call executed.")
        return 0

    combined_items: list[dict[str, Any]] = []
    last_url = ""
    try:
        for q in search_queries:
            params = dict(request_cfg.get("query", {}))
            params["q"] = q
            url = f"{base_url}{path}?{urlencode(params)}"
            last_url = url
            _, payload = perform_request(url, headers)
            for item in payload.get("items", []):
                if isinstance(item, dict):
                    item["_query"] = q
                    combined_items.append(item)
    except HTTPError as exc:
        update_run_state(state_dir_name, args.source_id, "failed", last_url, None, f"HTTP {exc.code}: {exc.reason}", None)
        print(f"FAIL  HTTP error: {exc.code} {exc.reason}")
        return 1
    except URLError as exc:
        update_run_state(state_dir_name, args.source_id, "failed", last_url, None, str(exc.reason), None)
        print(f"FAIL  Network error: {exc.reason}")
        return 1

    cache_path = cache_file_path(args.source_id, cache_dir_name)
    ensure_dir(cache_path.parent)
    artifact = {
        "source_id": args.source_id,
        "fetched_at": utc_now_iso(),
        "request": {"headers": sorted(headers.keys()), "queries": search_queries, "query_defaults": request_cfg.get("query", {})},
        "response": {"status_code": 200, "payload": {"items": combined_items}},
    }
    write_json_file(cache_path, artifact)
    update_run_state(state_dir_name, args.source_id, "success", last_url, cache_path, None, len(combined_items))
    print(f"PASS  Cached GitHub payload: {cache_path.relative_to(ROOT)}")
    print(f"PASS  GitHub records fetched: {len(combined_items)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
