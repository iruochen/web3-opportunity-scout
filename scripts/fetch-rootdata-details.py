#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

from common import (
    ROOT,
    default_run_state,
    ensure_dir,
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


def scrape_project(driver: webdriver.Chrome, project: dict[str, Any]) -> dict[str, Any]:
    project_id = int(project.get("project_id"))
    detail_url = str(project.get("rootdataurl") or "")
    if not detail_url:
        raise ValueError(f"Project {project_id} is missing rootdataurl")

    driver.get(detail_url)
    links = [
        {"text": element.text.strip(), "href": element.get_attribute("href") or ""}
        for element in driver.find_elements(By.CSS_SELECTOR, "a[href]")
    ]
    body_text = driver.find_element(By.TAG_NAME, "body").text
    body_lines = split_lines(body_text)

    one_liner = None
    try:
        one_liner = driver.find_element(By.CSS_SELECTOR, "h1 + p").text.strip()
    except Exception:
        pass

    details_section = driver.find_element(By.ID, "detail_section_essentials_details")
    details_lines = split_lines(details_section.text)
    details_block = between(details_lines, "Details", "Tags:")
    tags_block = between(details_lines, "Tags:", "Founded:")
    founded = extract_first_after(details_lines, "Founded:")

    team_links = []
    try:
        team_section = driver.find_element(By.ID, "detail_section_essentials_team")
        team_lines = split_lines(team_section.text)
        team_links = [{"text": item.text.strip(), "href": item.get_attribute("href") or ""} for item in team_section.find_elements(By.CSS_SELECTOR, "a[href]")]
    except Exception:
        team_lines = between(body_lines, "Team", "Fundraising")

    investor_links = []
    try:
        fundraising_section = driver.find_element(By.ID, "detail_section_financials_fundraising")
        fundraising_lines = split_lines(fundraising_section.text)
        investor_links = [
            {"text": item.text.strip(), "href": item.get_attribute("href") or ""}
            for item in fundraising_section.find_elements(By.CSS_SELECTOR, "a[href]")
        ]
    except Exception:
        fundraising_lines = between(body_lines, "Fundraising", "Related News")

    link_info = classify_links(links, project.get("X"))

    detail_summary = " ".join(details_block).strip()
    investors = parse_investor_links(
        investor_links,
        str(project.get("project_name") or ""),
        one_liner=str(one_liner or project.get("one_liner") or ""),
        website_url=str(link_info["website_url"] or ""),
    )
    if not investors:
        investors = parse_investors(
            fundraising_lines,
            project_name=str(project.get("project_name") or ""),
            one_liner=str(one_liner or project.get("one_liner") or ""),
            website_url=str(link_info["website_url"] or ""),
        )
    funding_rounds = parse_funding_rounds(fundraising_lines, investors)
    team = parse_team_links(team_links)
    if not team:
        team = parse_team(team_lines)
    news_links = link_info["news_links"]
    funding_signals = [
        item["title"]
        for item in news_links
        if re.search(r"\b(seed|series|funding|raised|round)\b", item["title"], flags=re.IGNORECASE)
    ]

    return {
        "project_id": project_id,
        "project_name": project.get("project_name"),
        "detail_url": detail_url,
        "one_liner": one_liner or project.get("one_liner"),
        "details": detail_summary or None,
        "founded": founded,
        "tags": [line for line in tags_block if line not in {"Tags:"}],
        "website_url": link_info["website_url"],
        "x_url": link_info["x_url"],
        "project_links": link_info["project_links"],
        "team": team,
        "investors": investors[:12],
        "funding_rounds": funding_rounds,
        "news_links": news_links,
        "funding_signals": funding_signals[:3],
        "fetched_at": utc_now_iso(),
    }


def build_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1440,2000")
    chrome_binary = os.getenv("ROOTDATA_CHROME_BINARY") or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if Path(chrome_binary).exists():
        options.binary_location = chrome_binary
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(25)
    return driver


def main() -> int:
    load_dotenv_file()
    args = parse_args()
    config, _ = load_effective_yaml("config.yaml", "config.example.yaml")
    profile = config.get("profile", {})
    cache_dir_name = str(profile.get("cache_dir", "cache"))
    state_dir_name = str(profile.get("state_dir", "state"))
    cache_dir = ROOT / cache_dir_name / "rootdata"
    input_path = Path(args.input).resolve() if args.input else find_latest_cache(cache_dir)
    projects = resolve_projects(input_path, args.project_id, args.limit)

    if args.dry_run:
        print(f"Input cache: {input_path.relative_to(ROOT)}")
        print(f"Projects selected: {len(projects)}")
        for item in projects[: min(len(projects), 10)]:
            print(f"- {item.get('project_id')}: {item.get('project_name')} -> {item.get('rootdataurl')}")
        return 0

    driver = None
    detail_records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    try:
        driver = build_driver()
        for project in projects:
            try:
                detail_records.append(scrape_project(driver, project))
            except (TimeoutException, WebDriverException, ValueError, Exception) as exc:
                errors.append(
                    {
                        "project_id": project.get("project_id"),
                        "project_name": project.get("project_name"),
                        "error": str(exc),
                    }
                )
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass

    cache_path = cache_file_path(args.source_id, cache_dir_name)
    artifact = {
        "source_id": args.source_id,
        "fetched_at": utc_now_iso(),
        "input_cache": str(input_path.relative_to(ROOT)),
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
