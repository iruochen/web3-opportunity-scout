from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

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


fetch_defillama = load_module("fetch-defillama.py", "fetch_defillama_module")
normalize_defillama = load_module("normalize-defillama.py", "normalize_defillama_module")
fetch_github = load_module("fetch-github.py", "fetch_github_module")
normalize_github = load_module("normalize-github.py", "normalize_github_module")
fetch_surf = load_module("fetch-surf.py", "fetch_surf_module")
normalize_surf = load_module("normalize-surf.py", "normalize_surf_module")


class DeFiLlamaTests(unittest.TestCase):
    def test_build_request_config_applies_client_limit(self) -> None:
        source_def = {"request": {"base_url": "https://api.llama.fi", "path": "/protocols", "query": {"limit": 20}}}
        request_cfg = fetch_defillama.build_request_config(source_def, 5)
        self.assertEqual(request_cfg["query"]["limit"], 5)

    def test_normalize_defillama_record_extracts_signals(self) -> None:
        record = normalize_defillama.build_record(
            {
                "name": "Jupiter",
                "slug": "jupiter",
                "category": "DEX",
                "chains": ["Solana"],
                "tvl": 123.4,
                "change_1d": 4.2,
                "url": "https://jup.ag",
            },
            "defillama_new_protocols",
            "2026-06-28T00:00:00Z",
        )
        self.assertEqual(record["project_name"], "Jupiter")
        self.assertIn("Solana", record["chains"])
        self.assertTrue(any("TVL" in signal for signal in record["signals"]))


class GitHubTests(unittest.TestCase):
    def test_build_query_strings_adds_cutoff(self) -> None:
        search_queries, request_cfg = fetch_github.build_query_strings(
            {"request": {"queries": ["web3"], "created_within_days": 730, "query": {"per_page": 10}}},
            3,
            7,
        )
        self.assertEqual(request_cfg["query"]["per_page"], 3)
        self.assertEqual(len(search_queries), 1)
        self.assertIn("created:>=", search_queries[0])
        self.assertIn("pushed:>=", search_queries[0])

    def test_github_quality_filter_skips_low_signal_repos(self) -> None:
        filters = {
            "min_stars": 3,
            "max_stars": 1500,
            "min_description_chars": 20,
            "exclude_keywords": ["boilerplate", "bot"],
        }
        self.assertEqual(
            fetch_github.quality_skip_reason(
                {"stargazers_count": 1, "description": "Useful Web3 project with real code"},
                filters,
            ),
            "stars_below_3",
        )
        self.assertEqual(
            fetch_github.quality_skip_reason(
                {
                    "stargazers_count": 10,
                    "description": "Ethereum dapp boilerplate for demos",
                    "name": "ethereum-dapp-boilerplate",
                    "topics": [],
                },
                filters,
            ),
            "excluded_keyword:boilerplate",
        )
        self.assertEqual(
            fetch_github.quality_skip_reason(
                {
                    "stargazers_count": 10,
                    "description": "Solana new pairs bot for token alerts",
                    "name": "SolanaNewPairsBot",
                    "topics": [],
                },
                filters,
            ),
            "excluded_keyword:bot",
        )

    def test_normalize_github_record_infers_chains_and_tags(self) -> None:
        record = normalize_github.build_record(
            {
                "full_name": "acme/solana-wallet",
                "description": "Solana consumer wallet for web3 users",
                "html_url": "https://github.com/acme/solana-wallet",
                "topics": ["wallet", "consumer"],
                "language": "TypeScript",
                "stargazers_count": 42,
                "forks_count": 3,
                "_query": "solana",
                "created_at": "2026-06-27T00:00:00Z",
                "pushed_at": "2026-06-28T00:00:00Z",
            },
            "github_trending_builders",
            "2026-06-28T00:00:00Z",
        )
        self.assertIn("Solana", record["chains"])
        self.assertIn("consumer", record["tags"])
        self.assertTrue(any("GitHub builder signal" in signal for signal in record["signals"]))
        self.assertTrue(any("Matched query" in signal for signal in record["signals"]))


class SurfTests(unittest.TestCase):
    def test_build_queries_prefers_profile_locale_and_caps_requests(self) -> None:
        config = {
            "reporting": {"locale": "zh"},
            "focus": {"chains": ["Base"], "sectors": ["AI x Crypto"]},
        }
        source_def = {
            "request": {
                "queries": ["ethereum"],
                "query": {"limit": 5, "lang": "en", "max_queries_per_run": 2},
            }
        }
        queries, query_defaults = fetch_surf.build_queries(config, source_def, 3, None)
        self.assertEqual(query_defaults["limit"], 3)
        self.assertEqual(query_defaults["lang"], "zh")
        self.assertEqual(len(queries), 2)

    def test_resolve_lang_uses_environment_when_auto(self) -> None:
        with patch.dict(os.environ, {"LANG": "zh_CN.UTF-8", "LC_ALL": "", "LC_MESSAGES": ""}, clear=False):
            lang = fetch_surf.resolve_lang({"reporting": {"locale": "auto"}}, None, "en")
        self.assertEqual(lang, "zh")

    def test_normalize_surf_record_uses_tweet_fallback_url(self) -> None:
        record = normalize_surf.build_record(
            {
                "id": "item-1",
                "title": "New infra stack",
                "subtitle": "Low-key infra rollout",
                "tldr": ["Shipped early testnet", "Quiet traction"],
                "signal_type": "early_signal",
                "source_tweet": {"tweet_id": "12345"},
                "_query": "infra",
                "timestamp": "2026-06-28T00:00:00Z",
            },
            "surf_project_ai_news",
            "2026-06-28T00:00:00Z",
        )
        self.assertEqual(record["project_url"], "https://x.com/i/web/status/12345")
        self.assertIn("early signal", record["tags"])
        self.assertTrue(record["summary"].startswith("Low-key infra rollout"))


if __name__ == "__main__":
    unittest.main()
