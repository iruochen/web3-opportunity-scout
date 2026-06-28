#!/usr/bin/env python3

from __future__ import annotations

import argparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Template normalizer for a new source adapter.")
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--input")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print("Implement source-specific normalization logic here.")
    print(f"Source id: {args.source_id}")
    print(f"Input: {args.input}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
