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


fetch_rootdata_details = load_module("fetch-rootdata-details.py", "fetch_rootdata_details_module")


class RootDataDetailParsingTests(unittest.TestCase):
    def test_parse_team_extracts_pairs(self) -> None:
        team = fetch_rootdata_details.parse_team(
            ["Active", "L", "Loong Wang", "Founder", "C", "Catherine Porter", "President and CoFounder"]
        )
        self.assertEqual(team[0]["name"], "Loong Wang")
        self.assertEqual(team[1]["role"], "President and CoFounder")

    def test_parse_investors_skips_labels(self) -> None:
        investors = fetch_rootdata_details.parse_investors(
            ["Investors/Shareholders", "Rounds", "Lead", "A", "Airwallex", "Lead", "C", "Capital 49"]
        )
        self.assertEqual(investors, ["Airwallex", "Capital 49"])

    def test_parse_investors_filters_project_metadata_noise(self) -> None:
        investors = fetch_rootdata_details.parse_investors(
            [
                "Investors/Shareholders",
                "Ethlabs",
                "Non-profit R&D lab for Ethereum",
                "ethlabs.org",
                "Analytics",
                "Comparison",
                "Framework Ventures",
            ],
            project_name="Ethlabs",
            one_liner="Non-profit R&D lab for Ethereum",
            website_url="https://ethlabs.org/",
        )
        self.assertEqual(investors, ["Framework Ventures"])

    def test_classify_links_picks_official_site_and_x(self) -> None:
        links = [
            {"text": "metalntwx.com", "href": "https://metalntwx.com/"},
            {"text": "X", "href": "https://x.com/metalntwx"},
            {"text": "Article", "href": "https://www.chaincatcher.com/article/2273772"},
        ]
        info = fetch_rootdata_details.classify_links(links, None)
        self.assertEqual(info["website_url"], "https://metalntwx.com/")
        self.assertEqual(info["x_url"], "https://x.com/metalntwx")
        self.assertEqual(info["news_links"][0]["title"], "Article")

    def test_parse_team_links_extracts_member_roles(self) -> None:
        links = [
            {
                "text": "L\nLoong Wang\nFounder",
                "href": "https://www.rootdata.com/member/Loong%20Wang?k=MTAzMzQ%3D",
            }
        ]
        people = fetch_rootdata_details.parse_team_links(links)
        self.assertEqual(people, [{"name": "Loong Wang", "role": "Founder"}])

    def test_parse_investor_links_extracts_names(self) -> None:
        links = [
            {
                "text": "Lead\nA\nAirwallex",
                "href": "https://www.rootdata.com/projects/detail/Airwallex?k=MjQ2ODE%3D",
            },
            {
                "text": "Lead\nC\nCapital 49",
                "href": "https://www.rootdata.com/investors/detail/Capital%2049?k=MTMxMjE%3D",
            },
        ]
        investors = fetch_rootdata_details.parse_investor_links(links, "Metal")
        self.assertEqual(investors, ["Airwallex", "Capital 49"])

    def test_parse_investor_links_filters_project_name_and_website(self) -> None:
        links = [
            {
                "text": "Ethlabs",
                "href": "https://www.rootdata.com/projects/detail/Ethlabs?k=MTIz",
            },
            {
                "text": "ethlabs.org",
                "href": "https://www.rootdata.com/projects/detail/ethlabs.org?k=MTIzNA==",
            },
            {
                "text": "Paradigm",
                "href": "https://www.rootdata.com/investors/detail/Paradigm?k=NTY3OA==",
            },
        ]
        investors = fetch_rootdata_details.parse_investor_links(
            links,
            "Ethlabs",
            one_liner="Non-profit R&D lab for Ethereum",
            website_url="https://ethlabs.org/",
        )
        self.assertEqual(investors, ["Paradigm"])

    def test_parse_investor_links_filters_www_website_variant(self) -> None:
        links = [
            {
                "text": "world.xyz",
                "href": "https://www.rootdata.com/projects/detail/world.xyz?k=MTIz",
            },
            {
                "text": "Firefly",
                "href": "https://www.rootdata.com/investors/detail/Firefly?k=NTY3OA==",
            },
        ]
        investors = fetch_rootdata_details.parse_investor_links(
            links,
            "world",
            one_liner="Decentralized trading platform based on Solana",
            website_url="https://www.world.xyz/",
        )
        self.assertEqual(investors, ["Firefly"])

    def test_parse_funding_rounds_extracts_amount_and_date(self) -> None:
        rounds = fetch_rootdata_details.parse_funding_rounds(
            [
                "Fundraising",
                "Rounds",
                "Amount",
                "Date",
                "Investors/Shareholders",
                "Seed",
                "$5M",
                "2026-06-30",
                "Lead",
                "Airwallex",
                "Capital 49",
            ],
            ["Airwallex", "Capital 49"],
        )
        self.assertEqual(rounds[0]["round"], "Seed")
        self.assertEqual(rounds[0]["amount"], "$5M")
        self.assertEqual(rounds[0]["date"], "2026-06-30")
        self.assertEqual(rounds[0]["investors"], ["Airwallex", "Capital 49"])

    def test_parse_funding_rounds_ignores_avatar_initials(self) -> None:
        rounds = fetch_rootdata_details.parse_funding_rounds(
            ["Investors/Shareholders", "Lead", "P", "Polychain", "H", "HSG"],
            ["Polychain", "HSG"],
        )
        self.assertEqual(rounds, [])


if __name__ == "__main__":
    unittest.main()
