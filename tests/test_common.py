from __future__ import annotations

import os
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

from scripts.common import infer_participation_angle, infer_validation_sources, load_dotenv_file


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
    def test_participation_angle_infers_defi_and_ai(self) -> None:
        results = infer_participation_angle(["DeFi", "AI"], "consumer network")
        self.assertTrue(any("liquidity programs" in item for item in results))
        self.assertTrue(any("developer previews" in item for item in results))

    def test_validation_sources_include_rootdata_and_defi(self) -> None:
        results = infer_validation_sources(["DeFi", "Layer1"], ["rootdata_projects"])
        self.assertIn("RootData project detail page", results)
        self.assertIn("DeFiLlama listings or TVL changes", results)


if __name__ == "__main__":
    unittest.main()
