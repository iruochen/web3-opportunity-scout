#!/usr/bin/env python3

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


@dataclass
class CheckResult:
    level: str
    message: str


def load_yaml_support() -> tuple[bool, str | None]:
    try:
        import yaml  # type: ignore  # noqa: F401
    except Exception as exc:
        return False, str(exc)
    return True, None


def check_paths() -> list[CheckResult]:
    required_files = [
        ROOT / "SKILL.md",
        ROOT / "README.md",
        ROOT / "config.example.yaml",
        ROOT / "sources.example.yaml",
        ROOT / "requirements.txt",
        ROOT / "references" / "init-flow.md",
        ROOT / "references" / "scoring-rules.example.md",
        ROOT / "prompts" / "summary-template.md",
        ROOT / "prompts" / "project-thesis-template.md",
        ROOT / "scripts" / "common.py",
        ROOT / "scripts" / "doctor.py",
        ROOT / "scripts" / "init.py",
        ROOT / "scripts" / "check-run-state.py",
        ROOT / "scripts" / "fetch-rootdata.py",
        ROOT / "scripts" / "normalize-rootdata.py",
    ]

    recommended_dirs = [
        ROOT / "cache",
        ROOT / "output",
        ROOT / "state",
        ROOT / "tests",
    ]

    results: list[CheckResult] = []

    for path in required_files:
        if path.exists():
            results.append(CheckResult("PASS", f"Found required file: {path.relative_to(ROOT)}"))
        else:
            results.append(CheckResult("FAIL", f"Missing required file: {path.relative_to(ROOT)}"))

    for path in recommended_dirs:
        if path.exists():
            results.append(CheckResult("PASS", f"Found working directory: {path.relative_to(ROOT)}"))
        else:
            results.append(CheckResult("WARN", f"Missing working directory: {path.relative_to(ROOT)}"))

    return results


def check_runtime() -> list[CheckResult]:
    results: list[CheckResult] = []

    python_name = Path(sys.executable).name
    results.append(CheckResult("PASS", f"Python executable: {python_name}"))

    venv_path = ROOT / ".venv"
    if venv_path.exists():
        results.append(CheckResult("PASS", "Project virtual environment exists at .venv"))
    else:
        results.append(CheckResult("WARN", "Project virtual environment not found; create it with python3 -m venv .venv"))

    if shutil.which("python3"):
        results.append(CheckResult("PASS", "python3 is available on PATH"))
    else:
        results.append(CheckResult("WARN", "python3 is not available on PATH"))

    yaml_ok, yaml_error = load_yaml_support()
    if yaml_ok:
        results.append(CheckResult("PASS", "PyYAML is available for config parsing"))
    else:
        results.append(CheckResult("WARN", f"PyYAML is not available yet: {yaml_error}"))

    return results


def check_local_configs() -> list[CheckResult]:
    results: list[CheckResult] = []

    config_path = ROOT / "config.yaml"
    sources_path = ROOT / "sources.yaml"

    if config_path.exists():
        results.append(CheckResult("PASS", "Found local config.yaml"))
    else:
        results.append(CheckResult("WARN", "config.yaml not found; copy from config.example.yaml"))

    if sources_path.exists():
        results.append(CheckResult("PASS", "Found local sources.yaml"))
    else:
        results.append(CheckResult("WARN", "sources.yaml not found; copy from sources.example.yaml"))

    return results


def print_section(title: str, results: list[CheckResult]) -> None:
    print(f"\n[{title}]")
    for item in results:
        print(f"{item.level:>4}  {item.message}")


def summarize(all_results: list[CheckResult]) -> int:
    fail_count = sum(1 for item in all_results if item.level == "FAIL")
    warn_count = sum(1 for item in all_results if item.level == "WARN")

    print("\n[Summary]")
    print(f"FAIL: {fail_count}")
    print(f"WARN: {warn_count}")

    if fail_count:
        print("Repository skeleton is incomplete. Fix FAIL items first.")
        return 1

    if warn_count:
        print("Skeleton is usable, but setup is incomplete. Address WARN items before running full pipelines.")
        return 0

    print("Skeleton looks healthy.")
    return 0


def main() -> int:
    print("web3-opportunity-scout doctor")
    print(f"Repository root: {ROOT}")

    sections = {
        "Runtime": check_runtime(),
        "Repository": check_paths(),
        "Local Config": check_local_configs(),
    }

    all_results: list[CheckResult] = []
    for title, results in sections.items():
        print_section(title, results)
        all_results.extend(results)

    return summarize(all_results)


if __name__ == "__main__":
    raise SystemExit(main())
