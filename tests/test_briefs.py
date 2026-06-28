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
                "reasoning": ["This project looks newly surfaced in current memory."],
                "supporting_signals": ["RootData hot list rank is 6."],
                "participation_angle": ["Track testnet, validator, or ecosystem builder programs."],
                "follow_up_questions": [
                    "Does this project show evidence beyond current hot-list visibility?",
                    "Is there a concrete participation angle for the configured user profile?",
                    "What source should be checked next for validation?",
                ],
            }
        ]
        html = render_brief_html(projects, {"chains": [], "sectors": []}, "en")
        self.assertIn("Focus chains", html)
        self.assertIn(">global<", html)
        self.assertIn(">general<", html)
        self.assertIn("Metal", html)


if __name__ == "__main__":
    unittest.main()
