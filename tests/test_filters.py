from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FILTER_PATH = ROOT / "scripts" / "filter-candidates.py"
SPEC = importlib.util.spec_from_file_location("filter_candidates_module", FILTER_PATH)
assert SPEC and SPEC.loader
filter_candidates_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(filter_candidates_module)


class FilterCandidateTests(unittest.TestCase):
    def test_rejects_title_keyword_match(self) -> None:
        record = {
            "project_name": "美国HYPE现货ETF本月上市以来录得3亿美元资金净流入",
            "summary": "ETF flow summary",
            "confidence": 0.62,
            "tags": [],
        }
        rules = {
            "min_confidence": 0.0,
            "include_any_tags": [],
            "exclude_title_keywords": ["ETF", "净流入"],
            "exclude_summary_keywords": [],
        }
        reasons = filter_candidates_module.evaluate_record(record, rules)
        self.assertTrue(any(reason.startswith("title_keyword:") for reason in reasons))

    def test_accepts_record_when_no_rules_match(self) -> None:
        record = {
            "project_name": "Arcium launches privacy compute testnet",
            "summary": "A privacy project shipped a new testnet for builders.",
            "confidence": 0.7,
            "tags": ["infra"],
        }
        rules = {
            "min_confidence": 0.5,
            "include_any_tags": [],
            "exclude_title_keywords": ["ETF"],
            "exclude_summary_keywords": ["美股"],
        }
        self.assertEqual(filter_candidates_module.evaluate_record(record, rules), [])

    def test_rejects_when_required_opportunity_signal_is_missing(self) -> None:
        record = {
            "project_name": "BTC ETF sees market-wide inflows",
            "summary": "Macro market update about broad flows and trading volume.",
            "confidence": 0.8,
            "tags": [],
        }
        rules = {
            "min_confidence": 0.5,
            "include_any_tags": [],
            "exclude_title_keywords": [],
            "exclude_summary_keywords": [],
            "require_any_signal": ["participation", "funding", "builder", "early_stage"],
        }
        self.assertIn("missing_required_signal", filter_candidates_module.evaluate_record(record, rules))


if __name__ == "__main__":
    unittest.main()
