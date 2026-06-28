from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.cli import build_parser


class CliParserTests(unittest.TestCase):
    def test_run_command_parses(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["run", "--skip-fetch", "--top", "8", "--days", "2"])
        self.assertEqual(args.command, "run")
        self.assertTrue(args.skip_fetch)
        self.assertEqual(args.top, 8)
        self.assertEqual(args.days, 2)

    def test_fetch_rootdata_dry_run_parses(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["fetch-rootdata", "--dry-run", "--days", "3"])
        self.assertEqual(args.command, "fetch-rootdata")
        self.assertTrue(args.dry_run)
        self.assertEqual(args.days, 3)

    def test_generic_fetch_parses_source(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["fetch", "--source", "rootdata_projects", "--dry-run"])
        self.assertEqual(args.command, "fetch")
        self.assertEqual(args.source, "rootdata_projects")
        self.assertTrue(args.dry_run)

    def test_run_parses_source(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["run", "--source", "rootdata_projects", "--skip-fetch"])
        self.assertEqual(args.command, "run")
        self.assertEqual(args.source, "rootdata_projects")
        self.assertTrue(args.skip_fetch)


if __name__ == "__main__":
    unittest.main()
