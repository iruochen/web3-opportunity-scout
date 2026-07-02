from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from common import load_yaml_file


class SourceConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sources = load_yaml_file(ROOT / "sources.example.yaml")
        self.config = load_yaml_file(ROOT / "config.example.yaml")

    def source_by_id(self, source_id: str) -> dict:
        for entries in self.sources.get("sources", {}).values():
            for entry in entries:
                if entry.get("id") == source_id:
                    return entry
        raise AssertionError(f"missing source {source_id}")

    def test_rootdata_funding_source_is_primary_enabled_source(self) -> None:
        source = self.source_by_id("rootdata_funding_rounds")
        self.assertTrue(source["enabled"])
        self.assertEqual(source["adapter"], "rootdata")
        self.assertEqual(source["request"]["path"], "/open/skill/get_fac")
        self.assertEqual(source["request"]["body"]["start_time_relative_days"], 14)

    def test_blockbeats_opportunity_endpoints_are_configured(self) -> None:
        expected = {
            "blockbeats_financing_newsflash": "/v1/newsflash/financing",
            "blockbeats_important_newsflash": "/v1/newsflash/important",
            "blockbeats_ai_newsflash": "/v1/newsflash/ai",
            "blockbeats_first_newsflash": "/v1/newsflash/first",
        }
        for source_id, path in expected.items():
            source = self.source_by_id(source_id)
            self.assertTrue(source["enabled"])
            self.assertEqual(source["adapter"], "blockbeats")
            self.assertEqual(source["request"]["path"], path)

    def test_opennews_and_opentwitter_are_enabled_for_preflight(self) -> None:
        self.assertTrue(self.source_by_id("opennews_projects")["enabled"])
        self.assertEqual(self.source_by_id("opennews_projects")["adapter"], "opennews")
        self.assertTrue(self.source_by_id("curated_twitter_list")["enabled"])
        self.assertEqual(self.source_by_id("curated_twitter_list")["adapter"], "opentwitter")

    def test_minimum_score_matches_early_project_bar(self) -> None:
        self.assertGreaterEqual(float(self.config["risk"]["min_opportunity_score"]), 70.0)


if __name__ == "__main__":
    unittest.main()
