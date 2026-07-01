#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from common import (
    ROOT,
    default_run_state,
    ensure_dir,
    find_source_definition,
    load_dotenv_file,
    load_effective_yaml,
    read_json_file,
    slugify,
    utc_now_iso,
    write_json_file,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch RootData detail pages for richer project enrichment.")
    parser.add_argument("--source-id", default="rootdata_projects")
    parser.add_argument("--input", help="Optional explicit RootData cache JSON path")
    parser.add_argument("--limit", type=int, default=20, help="Maximum number of projects to enrich from the latest RootData batch")
    parser.add_argument("--project-id", type=int, action="append", help="Optional explicit project ids to fetch")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--base-url", help="Override RootData detail API base URL")
    parser.add_argument("--path", help="Override RootData detail API path")
    return parser.parse_args()


def find_latest_cache(cache_dir: Path) -> Path:
    candidates = sorted(cache_dir.rglob("*.json"), key=lambda item: (item.stat().st_mtime, str(item)))
    if not candidates:
        raise FileNotFoundError(f"No RootData cache files found under {cache_dir}")
    return candidates[-1]


def cache_file_path(source_id: str, cache_dir_name: str) -> Path:
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    timestamp = datetime.now(UTC).strftime("%H%M%S")
    return ROOT / cache_dir_name / "rootdata-details" / today / f"{timestamp}-{slugify(source_id)}.json"


def build_detail_request_config(source_def: dict[str, Any], base_url: str | None, path: str | None) -> dict[str, Any]:
    request_cfg = dict(source_def.get("detail_request", {}))
    headers = dict(request_cfg.get("headers", {}))
    body = dict(request_cfg.get("body", {}))
    request_cfg["base_url"] = base_url or request_cfg.get("base_url") or "https://api.rootdata.com"
    request_cfg["path"] = path or request_cfg.get("path") or "/open/skill/get_item"
    request_cfg["method"] = str(request_cfg.get("method", "POST")).upper()
    request_cfg["headers"] = headers
    request_cfg["body"] = body
    return request_cfg


def build_url(request_cfg: dict[str, Any]) -> str:
    base_url = str(request_cfg.get("base_url", "")).rstrip("/")
    path = str(request_cfg.get("path", "")).strip()
    if not base_url or not path:
        raise ValueError("RootData detail request config requires both base_url and path")
    return f"{base_url}{path}" if path.startswith("/") else f"{base_url}/{path}"


def inject_auth(headers: dict[str, Any], source_def: dict[str, Any], dry_run: bool) -> tuple[dict[str, str], str | None]:
    final_headers = {str(key): str(value) for key, value in headers.items()}
    auth_cfg = source_def.get("auth", {})
    if not auth_cfg:
        return final_headers, None

    env_name = auth_cfg.get("env")
    if not env_name:
        raise ValueError("RootData source auth config is missing env")

    token = os.getenv(str(env_name))
    if not token and not dry_run:
        raise RuntimeError(f"Missing required environment variable: {env_name}")

    kind = str(auth_cfg.get("kind", "bearer")).lower()
    header_name = str(auth_cfg.get("header", "Authorization"))
    if token:
        if kind == "bearer":
            final_headers[header_name] = f"Bearer {token}"
        else:
            final_headers[header_name] = token
    return final_headers, str(env_name)


def update_run_state(
    state_dir_name: str,
    source_id: str,
    status: str,
    cache_path: Path | None,
    error: str | None,
    record_count: int | None,
) -> None:
    run_state_path = ROOT / state_dir_name / "run-state.json"
    run_state = read_json_file(run_state_path, default_run_state())
    run_state["updated_at"] = utc_now_iso()

    source_state = dict(run_state.get("sources", {}).get(source_id, {}))
    source_state["last_details_status"] = status
    source_state["last_details_fetch_at"] = utc_now_iso()
    source_state["last_details_cache_path"] = str(cache_path.relative_to(ROOT)) if cache_path else None
    source_state["last_details_error"] = error
    source_state["last_details_record_count"] = record_count

    run_state.setdefault("sources", {})[source_id] = source_state
    write_json_file(run_state_path, run_state)


def resolve_projects(input_path: Path, explicit_project_ids: list[int] | None, limit: int) -> list[dict[str, Any]]:
    artifact = read_json_file(input_path, {})
    items = artifact.get("response", {}).get("payload", {}).get("data", [])
    if not isinstance(items, list):
        return []
    projects = [item for item in items if isinstance(item, dict)]
    if explicit_project_ids:
        wanted = set(explicit_project_ids)
        return [item for item in projects if int(item.get("project_id", -1)) in wanted]
    return projects[:limit]


def split_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def between(lines: list[str], start: str, end: str | None) -> list[str]:
    try:
        start_idx = lines.index(start) + 1
    except ValueError:
        return []
    end_idx = len(lines)
    if end is not None:
        try:
            end_idx = lines.index(end, start_idx)
        except ValueError:
            pass
    return lines[start_idx:end_idx]


def clean_short_lines(lines: list[str]) -> list[str]:
    results: list[str] = []
    for line in lines:
        if len(line) == 1 and line.isalpha():
            continue
        results.append(line)
    return results


def parse_team(lines: list[str]) -> list[dict[str, str]]:
    cleaned = [line for line in clean_short_lines(lines) if line not in {"Active"}]
    people: list[dict[str, str]] = []
    index = 0
    while index < len(cleaned) - 1:
        name = cleaned[index]
        role = cleaned[index + 1]
        if name in {"Fundraising", "Related News"} or role in {"Fundraising", "Related News"}:
            break
        people.append({"name": name, "role": role})
        index += 2
    return people


def parse_investors(lines: list[str], project_name: str = "", one_liner: str = "", website_url: str = "") -> list[str]:
    cleaned = [
        line
        for line in clean_short_lines(lines)
        if line not in {"Investors/Shareholders", "Rounds", "Lead"}
    ]
    results: list[str] = []
    for line in cleaned:
        if line in {"Related News", "Follow Updates", "Follow Lists"}:
            break
        if line not in results:
            results.append(line)
    return sanitize_names(results, project_name=project_name, one_liner=one_liner, website_url=website_url)


def parse_funding_rounds(lines: list[str], investors: list[str] | None = None) -> list[dict[str, Any]]:
    label_values = {
        "Rounds",
        "Round",
        "Amount",
        "Valuation",
        "Date",
        "Investors",
        "Investors/Shareholders",
        "Lead",
        "Fundraising",
    }
    round_names = {
        "Pre-Seed",
        "Pre Seed",
        "Seed",
        "Strategic",
        "Angel",
        "Pre-A",
        "Series A",
        "Series B",
        "Series C",
        "Series D",
        "Public Sale",
        "Private Sale",
        "Grant",
    }
    amount_re = re.compile(r"(?i)(?:US\$|\$|USD\s*)\s?[\d,.]+\s*(?:k|m|b|million|billion)?|[\d,.]+\s*(?:million|billion)\s*(?:usd|dollars)?")
    date_re = re.compile(r"^\d{4}(?:[-/.]\d{1,2}(?:[-/.]\d{1,2})?)?$|^[A-Z][a-z]{2,9}\s+\d{1,2},\s+\d{4}$")
    investor_set = {item.strip() for item in investors or [] if item.strip()}
    rounds: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal current
        if current and any(current.get(key) for key in ("round", "amount", "date", "investors")):
            if current not in rounds:
                rounds.append(current)
        current = None

    for raw_line in lines:
        line = str(raw_line).strip()
        if not line or line in label_values or line == "Related News":
            continue
        if line in round_names or re.fullmatch(r"Series\s+[A-Z](?:\+)?", line, flags=re.IGNORECASE):
            flush()
            current = {"round": line}
            continue
        if amount_re.search(line):
            if current is None:
                current = {}
            current.setdefault("amount", line)
            continue
        if date_re.search(line):
            if current is None:
                current = {}
            current.setdefault("date", line)
            continue
        if line in investor_set:
            if current is None:
                continue
            current.setdefault("investors", [])
            if line not in current["investors"]:
                current["investors"].append(line)

    flush()
    return rounds[:5]


def parse_team_links(links: list[dict[str, str]]) -> list[dict[str, str]]:
    people: list[dict[str, str]] = []
    for item in links:
        href = item.get("href", "")
        if "/member/" not in href:
            continue
        parts = [part.strip() for part in item.get("text", "").splitlines() if part.strip()]
        cleaned = [part for part in parts if not (len(part) == 1 and part.isalpha())]
        if len(cleaned) >= 2:
            people.append({"name": cleaned[0], "role": cleaned[1]})
    return people


def parse_investor_links(
    links: list[dict[str, str]],
    project_name: str,
    one_liner: str = "",
    website_url: str = "",
) -> list[str]:
    investors: list[str] = []
    for item in links:
        href = item.get("href", "")
        if "/investors/detail/" not in href and "/projects/detail/" not in href:
            continue
        parts = [part.strip() for part in item.get("text", "").splitlines() if part.strip()]
        cleaned = [
            part
            for part in parts
            if part not in {"Lead"} and not (len(part) == 1 and part.isalpha()) and part != project_name
        ]
        if cleaned:
            name = cleaned[-1]
            if name not in investors:
                investors.append(name)
    return sanitize_names(investors, project_name=project_name, one_liner=one_liner, website_url=website_url)


def sanitize_names(values: list[str], project_name: str = "", one_liner: str = "", website_url: str = "") -> list[str]:
    blocked_exact = {
        "Calendar",
        "Exchanges",
        "Discover",
        "DashBoard",
        "/",
        "Home",
        "Projects",
        "Moderate",
        "Low Transparency",
        "High",
        "LinkedIn",
        "Analytics",
        "Comparison",
        "Essentials",
        "Details",
        "Team",
        "News",
        "𝕏 Data",
        "Performances",
        "Official Website",
    }
    blocked_contains = (
        "Search project, VC, person",
        "Select Metrics",
        "Share poster",
        "Add Comparison Project",
        "Project Rank:",
        "RD Growth Index",
        "RD Popularity Index",
    )
    normalized_project_name = project_name.strip().casefold()
    normalized_one_liner = one_liner.strip().casefold()
    normalized_website = website_url.strip().casefold().removeprefix("https://").removeprefix("http://").strip("/")
    normalized_website = normalized_website.removeprefix("www.")
    results: list[str] = []
    for value in values:
        text = str(value).strip()
        normalized = text.casefold()
        normalized_domain = normalized.removeprefix("www.").strip("/")
        if not text or text in blocked_exact:
            continue
        if any(token in text for token in blocked_contains):
            continue
        if re.fullmatch(r"[\d.%()\-–— ]+", text):
            continue
        if normalized_project_name and normalized == normalized_project_name:
            continue
        if normalized_one_liner and normalized == normalized_one_liner:
            continue
        if normalized_website and normalized_domain == normalized_website:
            continue
        if text not in results:
            results.append(text)
    return results


def extract_first_after(lines: list[str], marker: str) -> str | None:
    try:
        index = lines.index(marker)
    except ValueError:
        return None
    for line in lines[index + 1:]:
        if line:
            return line
    return None


def classify_links(links: list[dict[str, str]], fallback_x: str | None) -> dict[str, Any]:
    website_url = None
    x_url = fallback_x
    news_links: list[dict[str, str]] = []
    project_links: list[str] = []

    for item in links:
        href = item.get("href", "")
        text = item.get("text", "")
        hostname = urlparse(href).netloc.lower()
        if not href.startswith("http"):
            continue
        if "rootdata.com" in hostname:
            continue
        if "chaincatcher.com" in hostname:
            if text:
                news_links.append({"title": text, "url": href})
            continue
        if hostname == "x.com" or hostname.endswith(".x.com") or hostname == "twitter.com" or hostname.endswith(".twitter.com"):
            if text in {"X", f"@{href.rstrip('/').split('/')[-1]}"} or x_url is None:
                x_url = href
            continue
        if hostname == "linkedin.com" or hostname.endswith(".linkedin.com"):
            continue
        looks_like_domain = bool(re.fullmatch(r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text.strip()))
        if website_url is None and looks_like_domain and href.rstrip("/") != (x_url or "").rstrip("/"):
            website_url = href
        if href not in project_links and looks_like_domain:
            project_links.append(href)

    return {
        "website_url": website_url,
        "x_url": x_url,
        "project_links": project_links[:8],
        "news_links": news_links[:5],
    }


def normalize_api_team(values: Any) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []
    people: list[dict[str, str]] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("people_name") or item.get("member_name") or "").strip()
        role = str(item.get("role") or item.get("title") or item.get("position") or "").strip()
        if name:
            people.append({"name": name, "role": role})
    return people


def normalize_api_investors(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    investors: list[str] = []
    for item in values:
        name = item.get("name") if isinstance(item, dict) else item
        text = str(name or "").strip()
        if text and text not in investors:
            investors.append(text)
    return investors


def normalize_api_links(payload: dict[str, Any], fallback_x: str | None) -> dict[str, Any]:
    social_media = payload.get("social_media")
    social_media = social_media if isinstance(social_media, dict) else {}
    website_url = str(social_media.get("website") or "").strip() or None
    x_url = str(social_media.get("X") or social_media.get("twitter") or fallback_x or "").strip() or None
    project_links = []
    for key, value in social_media.items():
        url = str(value or "").strip()
        if key in {"website", "X", "twitter"} or not url.startswith("http"):
            continue
        if url not in project_links:
            project_links.append(url)
    return {
        "website_url": website_url,
        "x_url": x_url,
        "project_links": project_links[:8],
        "news_links": [],
    }


def perform_detail_request(url: str, method: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if method != "GET" else None
    request = Request(url=url, method=method, headers=headers, data=data)
    with urlopen(request, timeout=30) as response:
        payload = response.read().decode("utf-8")
        return json.loads(payload)


def fetch_project_detail(url: str, method: str, headers: dict[str, str], request_body: dict[str, Any], project: dict[str, Any]) -> dict[str, Any]:
    project_id = int(project.get("project_id"))
    body = dict(request_body)
    body["project_id"] = project_id
    payload = perform_detail_request(url, method, headers, body)
    if payload.get("result") != 200:
        raise RuntimeError(str(payload.get("message") or payload.get("msg") or payload))
    data = payload.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("RootData detail API returned no project data")

    link_info = normalize_api_links(data, project.get("X"))
    investors = normalize_api_investors(data.get("investors"))
    team = normalize_api_team(data.get("team"))
    tags = data.get("tags") if isinstance(data.get("tags"), list) else []

    return {
        "project_id": project_id,
        "project_name": data.get("project_name") or project.get("project_name"),
        "detail_url": data.get("rootdataurl") or project.get("rootdataurl"),
        "one_liner": data.get("one_liner") or project.get("one_liner"),
        "details": data.get("description") or None,
        "founded": data.get("establishment_date"),
        "tags": [str(tag).strip() for tag in tags if str(tag).strip()],
        "website_url": link_info["website_url"],
        "x_url": link_info["x_url"],
        "project_links": link_info["project_links"],
        "team": team,
        "investors": investors[:12],
        "funding_rounds": [],
        "news_links": link_info["news_links"],
        "funding_signals": [],
        "api_payload": {
            "contracts": data.get("contracts", []),
            "similar_project": data.get("similar_project", []),
            "active": data.get("active"),
        },
        "fetched_at": utc_now_iso(),
    }


def main() -> int:
    load_dotenv_file()
    args = parse_args()
    config, _ = load_effective_yaml("config.yaml", "config.example.yaml")
    sources_config, _ = load_effective_yaml("sources.yaml", "sources.example.yaml")
    _, source_def = find_source_definition(sources_config, args.source_id)
    profile = config.get("profile", {})
    cache_dir_name = str(profile.get("cache_dir", "cache"))
    state_dir_name = str(profile.get("state_dir", "state"))
    cache_dir = ROOT / cache_dir_name / "rootdata"
    input_path = Path(args.input).resolve() if args.input else find_latest_cache(cache_dir)
    projects = resolve_projects(input_path, args.project_id, args.limit)
    request_cfg = build_detail_request_config(source_def, args.base_url, args.path)
    url = build_url(request_cfg)
    headers, auth_env = inject_auth(request_cfg.get("headers", {}), source_def, args.dry_run)

    if args.dry_run:
        print(f"Input cache: {input_path.relative_to(ROOT)}")
        print(f"Request URL: {url}")
        print(f"Method: {request_cfg['method']}")
        if auth_env:
            print(f"Auth env: {auth_env}")
        print(f"Request body template: {json.dumps(request_cfg.get('body', {}), ensure_ascii=False)}")
        print(f"Projects selected: {len(projects)}")
        for item in projects[: min(len(projects), 10)]:
            print(f"- {item.get('project_id')}: {item.get('project_name')} -> {item.get('rootdataurl')}")
        return 0

    detail_records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for project in projects:
        try:
            detail_records.append(
                fetch_project_detail(
                    url,
                    request_cfg["method"],
                    headers,
                    request_cfg.get("body", {}),
                    project,
                )
            )
        except (HTTPError, URLError, ValueError, RuntimeError, Exception) as exc:
            errors.append(
                {
                    "project_id": project.get("project_id"),
                    "project_name": project.get("project_name"),
                    "error": str(exc),
                }
            )

    cache_path = cache_file_path(args.source_id, cache_dir_name)
    artifact = {
        "source_id": args.source_id,
        "fetched_at": utc_now_iso(),
        "input_cache": str(input_path.relative_to(ROOT)),
        "request": {
            "url": url,
            "method": request_cfg["method"],
            "headers": sorted(headers.keys()),
            "body_template": request_cfg.get("body", {}),
        },
        "project_count": len(projects),
        "detail_count": len(detail_records),
        "records": detail_records,
        "errors": errors,
    }
    write_json_file(cache_path, artifact)

    status = "success" if detail_records else "failed"
    update_run_state(state_dir_name, args.source_id, status, cache_path, None if detail_records else "No detail pages fetched", len(detail_records))
    print(f"PASS  Cached RootData detail payload: {cache_path.relative_to(ROOT)}")
    print(f"PASS  RootData detail records fetched: {len(detail_records)}")
    if errors:
        print(f"WARN  RootData detail errors: {len(errors)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
