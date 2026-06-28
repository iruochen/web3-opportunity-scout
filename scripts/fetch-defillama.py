#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from common import ROOT, default_run_state, ensure_dir, find_source_definition, load_dotenv_file, load_effective_yaml, read_json_file, slugify, utc_now_iso, write_json_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch DeFiLlama payloads into raw cache.")
    parser.add_argument("--source-id", default="defillama_new_protocols", help="Source id in sources.yaml")
    parser.add_argument("--limit", type=int, default=None, help="Client-side limit after fetch")
    parser.add_argument("--days", type=int, default=None, help="Reserved for CLI compatibility")
    parser.add_argument("--dry-run", action="store_true", help="Print resolved request without calling the API")
    return parser.parse_args()


def build_request_config(source_def: dict[str, Any], limit: int | None) -> dict[str, Any]:
    request_cfg = dict(source_def.get("request", {}))
    headers = dict(request_cfg.get("headers", {}))
    query = dict(request_cfg.get("query", {}))
    if limit is not None:
        query["limit"] = limit
    request_cfg["headers"] = headers
    request_cfg["query"] = query
    request_cfg["method"] = str(request_cfg.get("method", "GET")).upper()
    return request_cfg


def build_url(request_cfg: dict[str, Any]) -> str:
    base_url = str(request_cfg.get("base_url", "")).rstrip("/")
    path = str(request_cfg.get("path", "")).strip()
    if not base_url or not path:
        raise ValueError("DeFiLlama request config requires both base_url and path")
    url = f"{base_url}{path}" if path.startswith("/") else f"{base_url}/{path}"
    query = {key: value for key, value in request_cfg.get("query", {}).items() if value is not None and key != "limit"}
    if query:
        url = f"{url}?{urlencode(query)}"
    return url


def perform_request(url: str, headers: dict[str, str]) -> tuple[int, Any]:
    request = Request(url=url, method="GET", headers=headers)
    with urlopen(request, timeout=30) as response:
        payload = response.read().decode("utf-8")
        return response.status, json.loads(payload)


def cache_file_path(source_id: str, cache_dir_name: str) -> Path:
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    timestamp = datetime.now(UTC).strftime("%H%M%S")
    return ROOT / cache_dir_name / "defillama" / today / f"{timestamp}-{slugify(source_id)}.json"


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
    request_cfg = build_request_config(source_def, args.limit)
    url = build_url(request_cfg)

    print(f"Resolved source id: {args.source_id}")
    print(f"Request URL: {url}")
    if args.dry_run:
        print(f"Client limit: {request_cfg.get('query', {}).get('limit')}")
        print("Dry run only. No network call executed.")
        return 0

    cache_path = cache_file_path(args.source_id, cache_dir_name)
    ensure_dir(cache_path.parent)
    headers = {str(key): str(value) for key, value in request_cfg.get("headers", {}).items()}

    try:
        status_code, payload = perform_request(url, headers)
    except HTTPError as exc:
        update_run_state(state_dir_name, args.source_id, "failed", url, None, f"HTTP {exc.code}: {exc.reason}", None)
        print(f"FAIL  HTTP error: {exc.code} {exc.reason}")
        return 1
    except URLError as exc:
        update_run_state(state_dir_name, args.source_id, "failed", url, None, str(exc.reason), None)
        print(f"FAIL  Network error: {exc.reason}")
        return 1

    if isinstance(payload, list):
        limit = request_cfg.get("query", {}).get("limit")
        if isinstance(limit, int):
            payload = payload[:limit]
        record_count = len(payload)
    else:
        record_count = None

    artifact = {
        "source_id": args.source_id,
        "fetched_at": utc_now_iso(),
        "request": {"url": url, "method": "GET", "headers": sorted(headers.keys())},
        "response": {"status_code": status_code, "payload": payload},
    }
    write_json_file(cache_path, artifact)
    update_run_state(state_dir_name, args.source_id, "success", url, cache_path, None, record_count)
    print(f"PASS  Cached DeFiLlama payload: {cache_path.relative_to(ROOT)}")
    print(f"PASS  DeFiLlama records fetched: {record_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
