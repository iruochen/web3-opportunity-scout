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


def load_module(filename: str, name: str):
    module_path = ROOT / "scripts" / filename
    spec = importlib.util.spec_from_file_location(name, module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build_combined_module = load_module("build-combined-normalized.py", "build_combined_normalized_module")
run_pipeline_module = load_module("run-pipeline.py", "run_pipeline_module")
merge_module = load_module("merge-project-entities.py", "merge_project_entities_module")


class CombinedPipelineTests(unittest.TestCase):
    def test_resolve_source_ids_uses_enabled_adapter_sources_only(self) -> None:
        sources_config = {
            "sources": {
                "discovery": [
                    {"id": "rootdata_projects", "enabled": True, "adapter": "rootdata"},
                    {"id": "github_trending_builders", "enabled": True, "adapter": "github"},
                    {"id": "opennews_projects", "enabled": False, "adapter": "opennews"},
                ],
                "market": [
                    {"id": "funding_signals", "enabled": True},
                ],
            }
        }
        self.assertEqual(
            build_combined_module.resolve_source_ids(sources_config, None),
            ["rootdata_projects", "github_trending_builders"],
        )

    def test_pipeline_capable_sources_skips_non_adapter_entries(self) -> None:
        sources_config = {
            "sources": {
                "discovery": [
                    {"id": "rootdata_projects", "enabled": True, "adapter": "rootdata"},
                    {"id": "blockbeats_original_newsflash", "enabled": True, "adapter": "blockbeats"},
                ],
                "builder": [
                    {"id": "hackathon_results", "enabled": True},
                ],
            }
        }
        self.assertEqual(
            run_pipeline_module.pipeline_capable_sources(sources_config),
            ["rootdata_projects", "blockbeats_original_newsflash"],
        )

    def test_canonical_group_key_prefers_project_domain(self) -> None:
        first = {
            "project_name": "Metal",
            "entity_key": "metal",
            "website_url": "https://metal.example/",
        }
        second = {
            "project_name": "Metal Network",
            "entity_key": "metal-network",
            "project_url": "https://metal.example/docs",
        }
        self.assertEqual(merge_module.canonical_group_key(first), merge_module.canonical_group_key(second))


if __name__ == "__main__":
    unittest.main()
