#!/usr/bin/env python3
"""Regression tests for OpenAlex pagination failure handling."""

from __future__ import annotations

import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import openalex_search as module
from openalex_search import main, openalex_get, search_openalex


class PaginationFailureTests(unittest.TestCase):
    def test_single_page_result_does_not_fetch_a_second_page(self):
        first_page = {
            "meta": {"count": 400, "next_cursor": "next"},
            "results": [{"id": f"W{i}", "title": f"Paper {i}"} for i in range(200)],
        }

        with (
            mock.patch.object(module, "openalex_get", return_value=first_page) as get_page,
            mock.patch.object(module.time, "sleep"),
        ):
            papers, count = search_openalex(["digital governance"], max_results=1)

        self.assertEqual(len(papers), 1)
        self.assertEqual(count, 200)
        self.assertEqual(get_page.call_count, 1)

    def test_partial_page_failure_is_reported(self):
        first_page = {
            "meta": {"count": 400, "next_cursor": "next"},
            "results": [{"id": f"W{i}", "title": f"Paper {i}"} for i in range(200)],
        }

        with (
            mock.patch.object(module, "openalex_get", side_effect=[first_page, None]),
            mock.patch.object(module.time, "sleep"),
            self.assertRaisesRegex(RuntimeError, "分页请求失败"),
        ):
            search_openalex(["digital governance"], max_results=250)

    def test_main_exits_nonzero_when_search_is_incomplete(self):
        output = io.StringIO()

        with (
            mock.patch.object(sys, "argv", ["openalex_search.py", "--keywords", "test"]),
            mock.patch.object(
                module,
                "search_openalex",
                side_effect=RuntimeError("分页请求失败"),
            ),
            redirect_stdout(output),
        ):
            result = main()

        self.assertEqual(result, 1)
        self.assertIn("分页请求失败", output.getvalue())

    def test_environment_api_key_is_sent(self):
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = b"{}"

        with (
            mock.patch.dict(os.environ, {"OPENALEX_API_KEY": "test-key"}),
            mock.patch.object(module.urllib.request, "urlopen", return_value=response) as open_url,
        ):
            self.assertEqual(openalex_get("works", {"search": "test"}), {})

        request = open_url.call_args.args[0]
        self.assertIn("api_key=test-key", request.full_url)

    def test_failure_output_does_not_reveal_api_key(self):
        output = io.StringIO()

        with (
            mock.patch.dict(os.environ, {"OPENALEX_API_KEY": "test-key"}),
            mock.patch.object(
                module.urllib.request,
                "urlopen",
                side_effect=RuntimeError("network failed with test-key"),
            ),
            mock.patch.object(module.time, "sleep"),
            redirect_stdout(output),
        ):
            self.assertIsNone(openalex_get("works", {"search": "test"}))

        self.assertNotIn("test-key", output.getvalue())
        self.assertIn("https://api.openalex.org/works", output.getvalue())


if __name__ == "__main__":
    unittest.main()
