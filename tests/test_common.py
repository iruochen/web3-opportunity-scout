from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.common import (
    finish_pipeline_run,
    infer_participation_angle,
    infer_validation_sources,
    read_json_file,
    load_dotenv_file,
    load_run_state,
    latest_json_file_for_source,
    project_actionability_score,
    project_participation_signals,
    start_pipeline_run,
    update_pipeline_stage,
    latest_json_file,
    write_json_file,
)


class DotenvTests(unittest.TestCase):
    def test_load_dotenv_file_sets_variables(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text(
                "# comment\nROOTDATA_API_KEY=test-key\nEXTRA_VALUE='hello world'\n",
                encoding="utf-8",
            )

            os.environ.pop("ROOTDATA_API_KEY", None)
            os.environ.pop("EXTRA_VALUE", None)
            loaded = load_dotenv_file(env_path)

            self.assertEqual(loaded, env_path)
            self.assertEqual(os.environ["ROOTDATA_API_KEY"], "test-key")
            self.assertEqual(os.environ["EXTRA_VALUE"], "hello world")

    def test_load_dotenv_file_does_not_override_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text("ROOTDATA_API_KEY=file-value\n", encoding="utf-8")
            os.environ["ROOTDATA_API_KEY"] = "existing"

            load_dotenv_file(env_path)
            self.assertEqual(os.environ["ROOTDATA_API_KEY"], "existing")


class InferenceTests(unittest.TestCase):
    def test_participation_angle_uses_project_facts(self) -> None:
        project = {
            "tags": ["DeFi", "AI"],
            "summary": "consumer trading network",
            "investors": ["Firefly"],
        }
        results = infer_participation_angle(project)
        self.assertTrue(any("liquidity incentives" in item for item in results))
        self.assertTrue(any("developer previews" in item for item in results))
        self.assertTrue(any("financing event" in item for item in results))

    def test_validation_sources_include_rootdata_and_defi(self) -> None:
        project = {
            "tags": ["DeFi", "Layer1"],
            "source_ids": ["rootdata_projects"],
            "website_url": "https://example.com",
        }
        results = infer_validation_sources(project)
        self.assertIn("RootData project detail page", results)
        self.assertIn("DeFiLlama or on-chain dashboards", results)

    def test_actionability_prefers_participation_and_funding_evidence(self) -> None:
        project = {
            "summary": "Open beta waitlist with points campaign after seed funding.",
            "signals": ["Funding signal: Seed round closed", "Tags: DeFi"],
            "investors": ["Firefly"],
            "source_ids": ["rootdata_projects", "surf_project_ai_news"],
        }
        self.assertIn("waitlist", project_participation_signals(project))
        self.assertGreater(project_actionability_score(project), 40.0)


class RunStateTests(unittest.TestCase):
    def test_run_lifecycle_updates_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir)
            run_id = start_pipeline_run(state_dir, "rootdata_projects", 10, True)
            update_pipeline_stage(state_dir, run_id, "normalize", completed=True)
            finish_pipeline_run(state_dir, run_id, "completed")

            run_state = load_run_state(state_dir)
            self.assertEqual(run_state["active_run"], None)
            self.assertEqual(run_state["last_completed_run"], run_id)
            self.assertEqual(len(run_state["runs"]), 1)
            self.assertEqual(run_state["runs"][0]["status"], "completed")
            self.assertIn("normalize", run_state["runs"][0]["completed_stages"])


class FileSelectionTests(unittest.TestCase):
    def test_latest_json_file_prefers_newest_mtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            older = root / "z-old.json"
            newer = root / "a-new.json"
            older.write_text("{}", encoding="utf-8")
            time.sleep(0.01)
            newer.write_text("{}", encoding="utf-8")
            self.assertEqual(latest_json_file(root), newer)

    def test_latest_json_file_for_source_filters_by_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            first = root / "111-rootdata_projects-normalized.json"
            second = root / "222-surf_project_ai_news-normalized.json"
            first.write_text("{}", encoding="utf-8")
            time.sleep(0.01)
            second.write_text("{}", encoding="utf-8")
            self.assertEqual(latest_json_file_for_source(root, "surf_project_ai_news"), second)

    def test_write_json_file_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state.json"
            payload = {"hello": "world", "count": 2}
            write_json_file(path, payload)
            self.assertEqual(read_json_file(path, {}), payload)


if __name__ == "__main__":
    unittest.main()
