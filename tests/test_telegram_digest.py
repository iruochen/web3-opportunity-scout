from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODULE_PATH = ROOT / "scripts" / "build-telegram-digest.py"
SPEC = importlib.util.spec_from_file_location("build_telegram_digest_module", MODULE_PATH)
assert SPEC and SPEC.loader
telegram_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(telegram_module)


class TelegramDigestTests(unittest.TestCase):
    def test_intraday_renders_empty_when_no_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertEqual(telegram_module.render_intraday([], Path(tmpdir)), "")

    def test_early_selection_requires_pre_token_and_funding(self) -> None:
        projects = [
            {
                "project_name": "LiveToken",
                "token_status": "token_live",
                "score": 95,
                "funding_rounds": [{"round": "Seed"}],
                "opportunity_tier": "Tier-1 actionable",
            },
            {
                "project_name": "EarlyFunded",
                "token_status": "pre_token_likely",
                "score": 90,
                "funding_rounds": [{"round": "Seed"}],
                "opportunity_tier": "Tier-1 actionable",
            },
        ]
        selected = telegram_module.select_early(projects, 8)
        self.assertEqual([item["project_name"] for item in selected], ["EarlyFunded"])


if __name__ == "__main__":
    unittest.main()
