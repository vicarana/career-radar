#!/usr/bin/env python3
"""Small stdlib-only unit tests for radar.py's pure helper functions.

No existing test suite existed in this repo before this change (confirmed
via a repo-wide grep for unittest/pytest, zero hits), and radar.py is
explicitly "pure stdlib" by design, so this stays stdlib-only too rather
than pulling in pytest as a new dependency for two small functions.

Covers only what changed in this commit: humanize_company() and
company_career_pages(), both pure functions with no network I/O, added
so the Dashboard could surface direct links to companies that actually
produced a real match today (Vic, 2026-09-14), rather than testing the
network-calling src_* functions, which would need HTTP mocking that
isn't justified for this small a change (YAGNI).

Run: python3 radar/test_radar.py
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import radar  # noqa: E402


class HumanizeCompanyTests(unittest.TestCase):
    def setUp(self):
        self.companies = {
            "display_names": {
                "gitlab": "GitLab",
                "grafanalabs": "Grafana Labs",
                "scaleai": "Scale AI",
            }
        }

    def test_uses_explicit_override_when_present(self):
        self.assertEqual(radar.humanize_company("gitlab", self.companies), "GitLab")
        self.assertEqual(radar.humanize_company("grafanalabs", self.companies), "Grafana Labs")
        self.assertEqual(radar.humanize_company("scaleai", self.companies), "Scale AI")

    def test_falls_back_to_title_case_for_unlisted_slug(self):
        self.assertEqual(radar.humanize_company("samsara", self.companies), "Samsara")
        self.assertEqual(radar.humanize_company("brand-new-slug", self.companies), "Brand New Slug")

    def test_handles_missing_display_names_key(self):
        self.assertEqual(radar.humanize_company("samsara", {}), "Samsara")


class CompanyCareerPagesTests(unittest.TestCase):
    def test_only_greenhouse_lever_ashby_jobs_with_career_root_included(self):
        buckets = {
            "B": [
                {"company": "Samsara", "url": "https://www.samsara.com/x",
                 "_career_root": "https://job-boards.greenhouse.io/samsara"},
                {"company": "Samsara", "url": "https://www.samsara.com/y",
                 "_career_root": "https://job-boards.greenhouse.io/samsara"},
                # Aggregator source (Remotive/Jobicy/etc.), no _career_root: must be excluded.
                {"company": "Remotive Aggregator Co", "url": "https://remotive.com/z"},
            ],
            "C": [
                {"company": "OpenAI", "url": "https://jobs.ashbyhq.com/openai/1",
                 "_career_root": "https://jobs.ashbyhq.com/openai"},
            ],
        }
        result = radar.company_career_pages(buckets)
        self.assertEqual(result, [
            {"company": "OpenAI", "url": "https://jobs.ashbyhq.com/openai"},
            {"company": "Samsara", "url": "https://job-boards.greenhouse.io/samsara"},
        ])

    def test_empty_buckets_yield_empty_list(self):
        self.assertEqual(radar.company_career_pages({"B": [], "C": []}), [])

    def test_no_career_root_anywhere_yields_empty_list(self):
        buckets = {"B": [{"company": "Foo", "url": "https://remotive.com/1"}]}
        self.assertEqual(radar.company_career_pages(buckets), [])


if __name__ == "__main__":
    unittest.main()
