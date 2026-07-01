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

SCORE_PATH = ROOT / "scripts" / "score-opportunities.py"
SPEC = importlib.util.spec_from_file_location("score_opportunities_module", SCORE_PATH)
assert SPEC and SPEC.loader
score_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(score_module)


class ScoringTests(unittest.TestCase):
    def test_pre_token_testnet_project_can_reach_actionable_tier(self) -> None:
        project = {
            "canonical_name": "Arcium",
            "summary": "Pre-token privacy infra opens testnet waitlist, developer SDK, and points campaign.",
            "signals": ["Funding signal: Seed round closed", "GitHub commits active"],
            "source_ids": ["github_trending_builders", "blockbeats_financing_newsflash"],
            "tags": ["infra", "privacy"],
            "investors": ["Example Capital"],
            "confidence": 0.78,
        }

        traction = score_module.compute_traction(project)
        asymmetry = score_module.compute_asymmetry(project, {"sectors": ["infra"]})
        viability = score_module.compute_viability(project)
        score = round(90.0 * 0.16 + traction * 0.26 + asymmetry * 0.24 + viability * 0.34, 1)

        self.assertGreaterEqual(score, 80.0)
        self.assertIn("Tier-", score_module.tier_for_project(score, project, {"strong_candidate_score": 80, "tier1_score": 84}))

    def test_established_or_listed_project_is_penalized(self) -> None:
        project = {
            "canonical_name": "Solana",
            "summary": "Listed on Binance and already widely traded.",
            "signals": ["RootData hot rank: 1"],
            "source_ids": ["rootdata_projects"],
            "tags": ["Layer1"],
            "confidence": 0.9,
        }

        self.assertLess(score_module.compute_viability(project), 30.0)
        self.assertEqual(score_module.tier_for_project(82.0, project, {"strong_candidate_score": 80, "tier1_score": 84}), "Tier-3 monitor")

    def test_watchlist_eligibility_respects_minimum_score(self) -> None:
        projects = [
            {"project_name": "Low", "opportunity_score": 51.3},
            {"project_name": "Good", "opportunity_score": 82.0},
        ]
        self.assertEqual(
            [item["project_name"] for item in score_module.eligible_projects(projects, {"min_opportunity_score": 72})],
            ["Good"],
        )


if __name__ == "__main__":
    unittest.main()
