#!/usr/bin/env python3

from __future__ import annotations

import argparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Template fetcher for a new source adapter.")
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print("Implement source-specific fetch logic here.")
    print(f"Source id: {args.source_id}")
    print(f"Dry run: {args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
