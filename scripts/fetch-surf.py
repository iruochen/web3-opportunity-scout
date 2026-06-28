#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from common import ROOT, default_run_state, ensure_dir, find_source_definition, load_dotenv_file, load_effective_yaml, read_json_file, resolve_reporting_locale, slugify, utc_now_iso, write_json_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Surf project AI news payloads into raw cache.")
    parser.add_argument("--source-id", default="surf_project_ai_news")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--days", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--lang", help="Override request language")
    return parser.parse_args()


def resolve_lang(config: dict[str, Any], override: str | None, default: str) -> str:
    if override:
        return override
    locale = resolve_reporting_locale(config)
    if locale == "zh":
        return "zh"
    if locale == "bilingual":
        return default
    return "en"


def build_queries(config: dict[str, Any], source_def: dict[str, Any], limit: int | None, lang: str | None) -> tuple[list[str], dict[str, Any]]:
    request_cfg = dict(source_def.get("request", {}))
    query_defaults = dict(request_cfg.get("query", {}))
    if limit is not None:
        query_defaults["limit"] = limit
    resolved_lang = resolve_lang(config, lang, str(query_defaults.get("lang", "en")))
    query_defaults["lang"] = resolved_lang
    max_queries = int(query_defaults.pop("max_queries_per_run", 1))

    queries = [str(item).strip() for item in request_cfg.get("queries", []) if str(item).strip()]
    focus = config.get("focus", {})
    for item in focus.get("chains", []) if isinstance(focus, dict) else []:
        text = str(item).strip()
        if text and text.lower() not in {q.lower() for q in queries}:
            queries.append(text)
    for item in focus.get("sectors", []) if isinstance(focus, dict) else []:
        text = str(item).strip()
        if text and text.lower() not in {q.lower() for q in queries}:
            queries.append(text)
    if not queries:
        queries = ["ethereum"]
    return queries[:max_queries], query_defaults


def perform_request(url: str, headers: dict[str, str]) -> tuple[int, Any]:
    request = Request(url=url, method="GET", headers=headers)
    with urlopen(request, timeout=30) as response:
        payload = response.read().decode("utf-8")
        return response.status, json.loads(payload)


def cache_file_path(source_id: str, cache_dir_name: str) -> Path:
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    timestamp = datetime.now(UTC).strftime("%H%M%S")
    return ROOT / cache_dir_name / "surf" / today / f"{timestamp}-{slugify(source_id)}.json"


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
    queries, query_defaults = build_queries(config, source_def, args.limit, args.lang)
    base_url = str(source_def.get("request", {}).get("base_url", "")).rstrip("/")
    path = str(source_def.get("request", {}).get("path", "")).strip()
    token = os.getenv(str(source_def.get("auth", {}).get("env", "")))
    if not token and not args.dry_run:
        raise SystemExit(f"Missing required environment variable: {source_def.get('auth', {}).get('env')}")
    headers = {str(key): str(value) for key, value in source_def.get("request", {}).get("headers", {}).items()}
    if token:
        headers[str(source_def.get("auth", {}).get("header", "Authorization"))] = f"Bearer {token}"

    if args.dry_run:
        for q in queries:
            params = dict(query_defaults)
            params["q"] = q
            print(f"Request URL: {base_url}{path}?{urlencode(params)}")
        print("Dry run only. No network call executed.")
        return 0

    combined: list[dict[str, Any]] = []
    last_url = ""
    total_credits_used = 0
    try:
        for q in queries:
            params = dict(query_defaults)
            params["q"] = q
            url = f"{base_url}{path}?{urlencode(params)}"
            last_url = url
            _, payload = perform_request(url, headers)
            meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
            total_credits_used += int(meta.get("credits_used", 0) or 0)
            for item in payload.get("data", []):
                if isinstance(item, dict):
                    item["_query"] = q
                    combined.append(item)
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
        "request": {"headers": sorted(headers.keys()), "queries": queries, "query_defaults": query_defaults},
        "response": {"status_code": 200, "payload": {"data": combined, "meta": {"credits_used": total_credits_used}}},
    }
    write_json_file(cache_path, artifact)
    update_run_state(state_dir_name, args.source_id, "success", last_url, cache_path, None, len(combined))
    print(f"PASS  Cached Surf payload: {cache_path.relative_to(ROOT)}")
    print(f"PASS  Surf records fetched: {len(combined)}")
    print(f"PASS  Surf credits used: {total_credits_used}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
