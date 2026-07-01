#!/usr/bin/env python3

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from common import (
    ROOT,
    default_run_state,
    ensure_dir,
    find_source_definition,
    load_effective_yaml,
    read_json_file,
    slugify,
    utc_now_iso,
    write_json_file,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Crypto Fundraising public pages into raw cache.")
    parser.add_argument("--source-id", default="crypto_fundraising_recent")
    parser.add_argument("--days", type=int, default=None, help="Reserved for pipeline CLI compatibility")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def build_url(request_cfg: dict[str, Any]) -> str:
    base_url = str(request_cfg.get("base_url", "")).rstrip("/")
    path = str(request_cfg.get("path", "/")).strip() or "/"
    if not base_url:
        raise ValueError("Crypto Fundraising request config requires base_url")
    return f"{base_url}{path}" if path.startswith("/") else f"{base_url}/{path}"


def cache_file_path(source_id: str, cache_dir_name: str):
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    timestamp = datetime.now(UTC).strftime("%H%M%S")
    return ROOT / cache_dir_name / "crypto-fundraising" / today / f"{timestamp}-{slugify(source_id)}.json"


def update_run_state(
    state_dir_name: str,
    source_id: str,
    status: str,
    url: str,
    cache_path,
    error: str | None,
    record_count: int | None,
) -> None:
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
    args = parse_args()
    config, _ = load_effective_yaml("config.yaml", "config.example.yaml")
    sources_config, _ = load_effective_yaml("sources.yaml", "sources.example.yaml")
    _, source_def = find_source_definition(sources_config, args.source_id)
    profile = config.get("profile", {})
    cache_dir_name = str(profile.get("cache_dir", "cache"))
    state_dir_name = str(profile.get("state_dir", "state"))
    request_cfg = dict(source_def.get("request", {}))
    url = build_url(request_cfg)
    headers = {str(key): str(value) for key, value in request_cfg.get("headers", {}).items()}

    print(f"Resolved source id: {args.source_id}")
    print(f"Request URL: {url}")
    if args.dry_run:
        print("Dry run only. No network call executed.")
        return 0

    cache_path = cache_file_path(args.source_id, cache_dir_name)
    ensure_dir(cache_path.parent)
    try:
        request = Request(url=url, method="GET", headers=headers)
        with urlopen(request, timeout=30) as response:
            html = response.read().decode("utf-8", errors="replace")
            status_code = response.status
    except HTTPError as exc:
        update_run_state(state_dir_name, args.source_id, "failed", url, None, f"HTTP {exc.code}: {exc.reason}", None)
        print(f"FAIL  HTTP error: {exc.code} {exc.reason}")
        return 1
    except URLError as exc:
        update_run_state(state_dir_name, args.source_id, "failed", url, None, str(exc.reason), None)
        print(f"FAIL  Network error: {exc.reason}")
        return 1

    record_count = html.count('class="hp-table-row hpt-data"')
    write_json_file(
        cache_path,
        {
            "source_id": args.source_id,
            "fetched_at": utc_now_iso(),
            "request": {"url": url, "method": "GET", "headers": sorted(headers.keys())},
            "response": {"status_code": status_code, "html": html},
        },
    )
    update_run_state(state_dir_name, args.source_id, "success", url, cache_path, None, record_count)
    print(f"PASS  Cached Crypto Fundraising page: {cache_path.relative_to(ROOT)}")
    print(f"PASS  Raw fundraising rows detected: {record_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
