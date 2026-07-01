from __future__ import annotations

import sys
import unittest
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BUILD_BRIEFS_PATH = ROOT / "scripts" / "build-briefs.py"
SPEC = importlib.util.spec_from_file_location("build_briefs_module", BUILD_BRIEFS_PATH)
assert SPEC and SPEC.loader
build_briefs_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_briefs_module)
format_focus_list = build_briefs_module.format_focus_list
render_brief_html = build_briefs_module.render_brief_html


class BriefRenderingTests(unittest.TestCase):
    def test_format_focus_list_uses_fallback_for_empty_values(self) -> None:
        self.assertEqual(format_focus_list([], "global"), "global")

    def test_render_brief_html_handles_market_wide_focus(self) -> None:
        projects = [
            {
                "project_name": "Metal",
                "score": 90.7,
                "label": "high-priority follow",
                "project_url": "https://example.com/metal",
                "supporting_signals": ["RootData hot list rank is 6."],
                "summary": "Settlement network for tokenized finance.",
                "opportunity_thesis": ["Public financing signal is already visible, so the real edge is whether it is followed by beta, partnerships, or incentives."],
                "participation_angle": ["Prioritize testnet access, builder programs, validator or node programs, and ecosystem grants."],
                "priority_checks": ["Confirm the financing round, lead backers, and the first product or ecosystem milestone expected after the raise."],
                "investors": ["Airwallex", "Capital 49"],
                "funding_rounds": [{"round": "Seed", "amount": "$5M", "date": "2026-06-30", "investors": ["Airwallex", "Capital 49"]}],
            }
        ]
        html = render_brief_html(projects, {"chains": [], "sectors": []}, "en")
        self.assertIn("Focus chains", html)
        self.assertIn(">global<", html)
        self.assertIn(">general<", html)
        self.assertIn("Metal", html)
        self.assertIn("Funding: Seed / $5M / 2026-06-30", html)


if __name__ == "__main__":
    unittest.main()
