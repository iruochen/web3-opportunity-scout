#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import time
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
    created_within_days = int(request_cfg.get("created_within_days", 0) or 0)
    created_cutoff = (datetime.now(UTC) - timedelta(days=created_within_days)).strftime("%Y-%m-%d") if created_within_days else None
    search_queries = []
    for item in queries or ["web3"]:
        q = item
        if created_cutoff and "created:" not in q:
            q = f"{q} created:>={created_cutoff}"
        if cutoff and "pushed:" not in q:
            q = f"{q} pushed:>={cutoff}"
        search_queries.append(q)
    base_query["per_page"] = per_page
    request_cfg["query"] = base_query
    return search_queries, request_cfg


def perform_request(url: str, headers: dict[str, str], attempts: int = 3) -> tuple[int, Any]:
    request = Request(url=url, method="GET", headers=headers)
    last_error: URLError | TimeoutError | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(request, timeout=30) as response:
                payload = response.read().decode("utf-8")
                return response.status, json.loads(payload)
        except HTTPError:
            raise
        except (URLError, TimeoutError) as exc:
            last_error = exc
            if attempt == attempts:
                raise
            time.sleep(0.8 * attempt)
    raise last_error or URLError("unknown GitHub request failure")


def _contains_keyword(text: str, keywords: list[str]) -> str | None:
    lowered = text.lower()
    for keyword in keywords:
        normalized = str(keyword).strip().lower()
        if normalized and normalized in lowered:
            return normalized
    return None


def quality_skip_reason(item: dict[str, Any], filters: dict[str, Any]) -> str | None:
    if not filters:
        return None
    stars = int(item.get("stargazers_count") or 0)
    min_stars = int(filters.get("min_stars", 0))
    max_stars = int(filters.get("max_stars", 0))
    if min_stars and stars < min_stars:
        return f"stars_below_{min_stars}"
    if max_stars and stars > max_stars:
        return f"stars_above_{max_stars}"

    description = str(item.get("description") or "").strip()
    min_description_chars = int(filters.get("min_description_chars", 0))
    if min_description_chars and len(description) < min_description_chars:
        return f"description_shorter_than_{min_description_chars}"

    owner = str(item.get("owner", {}).get("login") or "").strip()
    excluded_owners = {str(value).strip().lower() for value in filters.get("exclude_owners", [])}
    if owner.lower() in excluded_owners:
        return f"excluded_owner:{owner}"

    name_text = " ".join(
        str(value)
        for value in [
            item.get("name"),
            item.get("full_name"),
            item.get("description"),
            " ".join(str(topic) for topic in item.get("topics", [])),
        ]
        if value
    )
    keyword = _contains_keyword(name_text, [str(value) for value in filters.get("exclude_keywords", [])])
    if keyword:
        return f"excluded_keyword:{keyword}"
    if item.get("archived"):
        return "archived"
    if item.get("fork"):
        return "fork"
    return None


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
    skipped: dict[str, int] = {}
    seen_full_names: set[str] = set()
    quality_filters = dict(request_cfg.get("quality_filters", {}))
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
                    full_name = str(item.get("full_name") or "").strip().lower()
                    if full_name and full_name in seen_full_names:
                        skipped["duplicate_repo"] = skipped.get("duplicate_repo", 0) + 1
                        continue
                    skip_reason = quality_skip_reason(item, quality_filters)
                    if skip_reason:
                        skipped[skip_reason] = skipped.get(skip_reason, 0) + 1
                        continue
                    if full_name:
                        seen_full_names.add(full_name)
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
        "request": {
            "headers": sorted(headers.keys()),
            "queries": search_queries,
            "query_defaults": request_cfg.get("query", {}),
            "quality_filters": quality_filters,
        },
        "skipped": skipped,
        "response": {"status_code": 200, "payload": {"items": combined_items}},
    }
    write_json_file(cache_path, artifact)
    update_run_state(state_dir_name, args.source_id, "success", last_url, cache_path, None, len(combined_items))
    print(f"PASS  Cached GitHub payload: {cache_path.relative_to(ROOT)}")
    print(f"PASS  GitHub records fetched: {len(combined_items)}")
    if skipped:
        print("PASS  GitHub records skipped: " + ", ".join(f"{key}={value}" for key, value in sorted(skipped.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
