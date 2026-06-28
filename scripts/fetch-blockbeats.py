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

from common import (
    ROOT,
    default_run_state,
    ensure_dir,
    find_source_definition,
    load_dotenv_file,
    load_effective_yaml,
    read_json_file,
    resolve_reporting_locale,
    slugify,
    utc_now_iso,
    write_json_file,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch BlockBeats payloads into raw cache.")
    parser.add_argument("--source-id", default="blockbeats_original_newsflash", help="Source id in sources.yaml")
    parser.add_argument("--page", type=int, default=None, help="Override page")
    parser.add_argument("--limit", type=int, default=None, help="Override request size")
    parser.add_argument("--days", type=int, default=None, help="Reserved for CLI compatibility; not used by BlockBeats")
    parser.add_argument("--lang", help="Override request language, e.g. cn or en")
    parser.add_argument("--dry-run", action="store_true", help="Print resolved request without calling the API")
    parser.add_argument("--base-url", help="Override request base URL")
    parser.add_argument("--path", help="Override request path")
    return parser.parse_args()


def resolve_blockbeats_lang(config: dict[str, Any], override: str | None) -> str:
    if override:
        return override
    locale = resolve_reporting_locale(config)
    if locale == "en":
        return "en"
    return "cn"


def build_request_config(
    source_def: dict[str, Any],
    config: dict[str, Any],
    page: int | None,
    limit: int | None,
    lang: str | None,
    base_url: str | None,
    path: str | None,
) -> dict[str, Any]:
    request_cfg = dict(source_def.get("request", {}))
    headers = dict(request_cfg.get("headers", {}))
    query = dict(request_cfg.get("query", {}))

    if page is not None:
        query["page"] = page
    if limit is not None:
        query["size"] = limit
    query["lang"] = resolve_blockbeats_lang(config, lang)

    request_cfg["base_url"] = base_url or request_cfg.get("base_url", "")
    request_cfg["path"] = path or request_cfg.get("path", "")
    request_cfg["method"] = str(request_cfg.get("method", "GET")).upper()
    request_cfg["headers"] = headers
    request_cfg["query"] = query
    return request_cfg


def build_url(request_cfg: dict[str, Any]) -> str:
    base_url = str(request_cfg.get("base_url", "")).rstrip("/")
    path = str(request_cfg.get("path", "")).strip()
    if not base_url or not path:
        raise ValueError("BlockBeats request config requires both base_url and path")

    url = f"{base_url}{path}" if path.startswith("/") else f"{base_url}/{path}"
    query = {key: value for key, value in request_cfg.get("query", {}).items() if value is not None}
    if query:
        url = f"{url}?{urlencode(query)}"
    return url


def inject_auth(headers: dict[str, Any], source_def: dict[str, Any], dry_run: bool) -> tuple[dict[str, str], str | None]:
    final_headers = {str(key): str(value) for key, value in headers.items()}
    auth_cfg = source_def.get("auth", {})

    if not auth_cfg:
        return final_headers, None

    env_name = auth_cfg.get("env")
    if not env_name:
        raise ValueError("BlockBeats source auth config is missing env")

    token = os.getenv(str(env_name))
    if not token and not dry_run:
        raise RuntimeError(f"Missing required environment variable: {env_name}")

    header_name = str(auth_cfg.get("header", "api-key"))
    if token:
        final_headers[header_name] = token

    return final_headers, str(env_name)


def perform_request(url: str, method: str, headers: dict[str, str]) -> tuple[int, Any]:
    request = Request(url=url, method=method, headers=headers)
    with urlopen(request, timeout=30) as response:
        payload = response.read().decode("utf-8")
        content_type = response.headers.get("Content-Type", "")
        if "json" in content_type.lower():
            return response.status, json.loads(payload)
        return response.status, {"raw_text": payload}


def cache_file_path(source_id: str, cache_dir_name: str) -> Path:
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    timestamp = datetime.now(UTC).strftime("%H%M%S")
    return ROOT / cache_dir_name / "blockbeats" / today / f"{timestamp}-{slugify(source_id)}.json"


def update_run_state(
    state_dir_name: str,
    source_id: str,
    status: str,
    url: str,
    cache_path: Path | None,
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


def extract_record_count(payload: Any) -> int | None:
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        return len(data["data"])
    if isinstance(data, list):
        return len(data)
    return None


def main() -> int:
    load_dotenv_file()
    args = parse_args()
    config, config_path = load_effective_yaml("config.yaml", "config.example.yaml")
    sources_config, sources_path = load_effective_yaml("sources.yaml", "sources.example.yaml")
    _, source_def = find_source_definition(sources_config, args.source_id)

    profile = config.get("profile", {})
    cache_dir_name = str(profile.get("cache_dir", "cache"))
    state_dir_name = str(profile.get("state_dir", "state"))
    request_cfg = build_request_config(source_def, config, args.page, args.limit, args.lang, args.base_url, args.path)
    url = build_url(request_cfg)
    headers, auth_env = inject_auth(request_cfg.get("headers", {}), source_def, args.dry_run)

    print(f"Using config: {config_path.relative_to(ROOT)}")
    print(f"Using sources: {sources_path.relative_to(ROOT)}")
    print(f"Resolved source id: {args.source_id}")
    print(f"Request URL: {url}")
    print(f"Method: {request_cfg['method']}")
    if auth_env:
        print(f"Auth env: {auth_env}")

    if args.dry_run:
        print(f"Request query: {json.dumps(request_cfg.get('query', {}), ensure_ascii=False)}")
        print("Dry run only. No network call executed.")
        return 0

    cache_path = cache_file_path(args.source_id, cache_dir_name)
    ensure_dir(cache_path.parent)

    try:
        status_code, payload = perform_request(url, request_cfg["method"], headers)
    except HTTPError as exc:
        update_run_state(state_dir_name, args.source_id, "failed", url, None, f"HTTP {exc.code}: {exc.reason}", None)
        print(f"FAIL  HTTP error: {exc.code} {exc.reason}")
        return 1
    except URLError as exc:
        update_run_state(state_dir_name, args.source_id, "failed", url, None, str(exc.reason), None)
        print(f"FAIL  Network error: {exc.reason}")
        return 1
    except Exception as exc:
        update_run_state(state_dir_name, args.source_id, "failed", url, None, str(exc), None)
        print(f"FAIL  Unexpected error: {exc}")
        return 1

    record_count = extract_record_count(payload)
    artifact = {
        "source_id": args.source_id,
        "fetched_at": utc_now_iso(),
        "request": {
            "url": url,
            "method": request_cfg["method"],
            "headers": sorted(headers.keys()),
            "query": request_cfg.get("query", {}),
        },
        "response": {
            "status_code": status_code,
            "payload": payload,
        },
    }
    write_json_file(cache_path, artifact)
    update_run_state(state_dir_name, args.source_id, "success", url, cache_path, None, record_count)

    print(f"PASS  Cached BlockBeats payload: {cache_path.relative_to(ROOT)}")
    if record_count is not None:
        print(f"PASS  BlockBeats records fetched: {record_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
