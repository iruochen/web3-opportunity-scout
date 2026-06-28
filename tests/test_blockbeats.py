from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from unittest.mock import patch
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


fetch_blockbeats = load_module("fetch-blockbeats.py", "fetch_blockbeats_module")
normalize_blockbeats = load_module("normalize-blockbeats.py", "normalize_blockbeats_module")


class BlockBeatsFetchTests(unittest.TestCase):
    def test_build_request_config_uses_cn_for_auto_zh_locale(self) -> None:
        config = {"profile": {"timezone": "Asia/Shanghai"}, "reporting": {"locale": "auto"}}
        source_def = {
            "request": {
                "base_url": "https://api-pro.theblockbeats.info",
                "path": "/v1/newsflash/original",
                "method": "GET",
                "headers": {"Accept": "application/json"},
                "query": {"page": 1, "size": 20, "lang": "en"},
            }
        }
        with patch.dict(os.environ, {"LANG": "", "LC_ALL": "", "LC_MESSAGES": ""}, clear=False):
            request_cfg = fetch_blockbeats.build_request_config(source_def, config, None, 5, None, None, None)
        self.assertEqual(request_cfg["query"]["size"], 5)
        self.assertEqual(request_cfg["query"]["lang"], "cn")

    def test_build_request_config_allows_explicit_lang_override(self) -> None:
        config = {"reporting": {"locale": "zh"}}
        source_def = {"request": {"query": {"page": 1, "size": 20, "lang": "cn"}}}
        request_cfg = fetch_blockbeats.build_request_config(source_def, config, 2, None, "en", "https://api-pro.theblockbeats.info", "/v1/newsflash/original")
        self.assertEqual(request_cfg["query"]["page"], 2)
        self.assertEqual(request_cfg["query"]["lang"], "en")


class BlockBeatsNormalizeTests(unittest.TestCase):
    def test_extract_records_reads_nested_data(self) -> None:
        payload = {"data": {"page": 1, "data": [{"id": 1}, {"id": 2}]}}
        records = normalize_blockbeats.extract_records(payload)
        self.assertEqual(len(records), 2)

    def test_build_record_normalizes_html_and_links(self) -> None:
        item = {
            "id": 330275,
            "title": "Solana Meme token spikes",
            "content": "<p>GMGN monitored Solana meme activity and trading.</p>",
            "link": "https://m.theblockbeats.info/flash/330275",
            "url": "https://gmgn.ai/example",
            "create_time": "2026-01-29 14:31:06",
        }
        record = normalize_blockbeats.build_record(item, "blockbeats_original_newsflash", "2026-06-28T00:00:00Z")
        self.assertEqual(record["source_type"], "blockbeats.newsflash.original")
        self.assertEqual(record["project_url"], "https://gmgn.ai/example")
        self.assertIn("consumer", record["tags"])
        self.assertIn("Solana", record["chains"])
        self.assertTrue(record["summary"].startswith("GMGN monitored"))


if __name__ == "__main__":
    unittest.main()
