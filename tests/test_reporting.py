#!/usr/bin/env python3

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from scripts.common import resolve_reporting_formats, resolve_reporting_locale


class ReportingConfigTests(unittest.TestCase):
    def test_explicit_locale_wins(self) -> None:
        config = {"reporting": {"locale": "zh"}}
        self.assertEqual(resolve_reporting_locale(config), "zh")

    def test_auto_locale_uses_environment(self) -> None:
        config = {"profile": {"timezone": "UTC"}, "reporting": {"locale": "auto"}}
        with patch.dict(os.environ, {"LANG": "zh_CN.UTF-8"}, clear=False):
            self.assertEqual(resolve_reporting_locale(config), "zh")

    def test_auto_locale_falls_back_to_timezone(self) -> None:
        config = {"profile": {"timezone": "Asia/Shanghai"}, "reporting": {"locale": "auto"}}
        with patch.dict(os.environ, {"LANG": "", "LC_ALL": "", "LC_MESSAGES": ""}, clear=False):
            self.assertEqual(resolve_reporting_locale(config), "zh")

    def test_formats_filter_unknown_values(self) -> None:
        config = {"reporting": {"generate_formats": ["html", "pdf", "md", "html"]}}
        self.assertEqual(resolve_reporting_formats(config), ["html", "md"])


if __name__ == "__main__":
    unittest.main()
