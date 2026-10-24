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
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import radar  # noqa: E402
import sources  # noqa: E402


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


class HighConfidenceMatchesTests(unittest.TestCase):
    """Added 2026-09-23 per Vic's ask for a real, computed 'score 75+' filter,
    distinct from grade_of()'s coarser A/B/C letters (grade A starts at 70)."""

    def _row(self, match, score, company="X"):
        return {"match": match, "score": score, "company": company, "title": "t",
                "location": "remote", "url": f"https://x/{company}", "visa": False}

    def test_filters_by_threshold_inclusive(self):
        rows = [self._row(70, 14), self._row(75, 15), self._row(80, 16)]
        result = radar.high_confidence_matches(rows, 75)
        self.assertEqual([r["match"] for r in result], [80, 75])

    def test_sorted_by_score_descending(self):
        rows = [self._row(75, 15, "A"), self._row(90, 18, "B"), self._row(80, 16, "C")]
        result = radar.high_confidence_matches(rows, 75)
        self.assertEqual([r["company"] for r in result], ["B", "C", "A"])

    def test_empty_when_nothing_clears_threshold(self):
        rows = [self._row(60, 12), self._row(70, 14)]
        self.assertEqual(radar.high_confidence_matches(rows, 75), [])

    def test_empty_input_yields_empty_list(self):
        self.assertEqual(radar.high_confidence_matches([], 75), [])


class SeniorityAliasTests(unittest.TestCase):
    P = {"seniority": ["senior"], "leadership_titles": [], "target_titles": ["devops", "machine learning"]}

    def _ok(self, title):
        return radar.is_senior_or_leadership({"title": title}, self.P)

    def test_sr_abbreviation_counts_as_senior(self):
        self.assertTrue(self._ok("Sr. Salesforce DevOps Engineer"))
        self.assertTrue(self._ok("Sr Machine Learning Engineer"))

    def test_distinguished_counts_as_senior(self):
        self.assertTrue(self._ok("Distinguished Engineer, Core DevOps"))

    def test_spanish_and_portuguese_leadership_words_count(self):
        self.assertTrue(self._ok("Lider DevOps"))
        self.assertTrue(self._ok("Líder Técnico DevOps (WebLogic)"))
        self.assertTrue(self._ok("Jefe de Plataforma DevOps"))
        self.assertTrue(self._ok("Ingeniero DevOps Sénior"))

    def test_sr_is_a_whole_word_not_a_substring(self):
        self.assertFalse(self._ok("Usrbin DevOps Engineer"))

    def test_plain_title_without_seniority_still_excluded(self):
        self.assertFalse(self._ok("DevOps Engineer"))


class TitleLevelTests(unittest.TestCase):
    P = {"seniority": ["senior"], "leadership_titles": ["manager"],
         "target_titles": ["devops", "platform engineer", "sre"]}

    def _lvl(self, title):
        return radar.title_level({"title": title}, self.P)

    def test_explicit_senior_stays_senior(self):
        self.assertEqual(self._lvl("Senior DevOps Engineer"), "senior")
        self.assertEqual(self._lvl("SRE Manager"), "senior")

    def test_domain_title_without_level_word_is_unstated(self):
        self.assertEqual(self._lvl("Platform Engineer"), "unstated")
        self.assertEqual(self._lvl("DevOps Engineer (GCP)"), "unstated")

    def test_explicit_junior_markers_are_excluded(self):
        for t in ("DevOps Engineer Intern", "Junior Platform Engineer", "SRE Engineer II",
                  "Associate DevOps Engineer", "Platform Engineer I", "DevOps Engineer Jr"):
            self.assertIsNone(self._lvl(t), t)

    def test_off_domain_is_excluded_even_with_no_junior_word(self):
        self.assertIsNone(self._lvl("Account Executive"))
        self.assertIsNone(self._lvl("Software Engineering Generalist"))

    def test_i_marker_is_a_whole_word(self):
        self.assertEqual(self._lvl("DevOps Engineer, Insights"), "unstated")


class CollapseMassPostedTests(unittest.TestCase):
    @staticmethod
    def _job(title, company, loc, score=5):
        return {"title": title, "company": company, "location": loc, "_score": score}

    def test_five_or_more_locations_collapse_to_best_scoring_one(self):
        jobs = [self._job("Prompt Engineer", "Spam GmbH", f"City {i}", score=i) for i in range(6)]
        kept, removed = radar.collapse_mass_posted(jobs)
        self.assertEqual(len(kept), 1)
        self.assertEqual(removed, 5)
        self.assertEqual(kept[0]["_score"], 5)
        self.assertEqual(kept[0]["_posted_in"], 6)

    def test_small_groups_keep_each_distinct_location(self):
        jobs = [self._job("Senior SRE", "Acme", loc) for loc in ("Paris", "Dublin", "Berlin")]
        kept, removed = radar.collapse_mass_posted(jobs)
        self.assertEqual((len(kept), removed), (3, 0))
        self.assertFalse(any("_posted_in" in j for j in kept))

    def test_exact_same_location_duplicates_are_dropped(self):
        jobs = [self._job("Senior SRE", "Acme", "Paris"), self._job("Senior SRE", "Acme", " paris ")]
        kept, removed = radar.collapse_mass_posted(jobs)
        self.assertEqual((len(kept), removed), (1, 1))

    def test_different_companies_never_merge(self):
        jobs = [self._job("Senior SRE", c, "Paris") for c in ("A", "B", "C", "D", "E", "F")]
        kept, _ = radar.collapse_mass_posted(jobs)
        self.assertEqual(len(kept), 6)


class AdzunaUndisclosedCompanyTests(unittest.TestCase):
    @staticmethod
    def _canned(*companies):
        return {"count": len(companies), "results": [
            {"title": "Devops Engineer", "company": c, "redirect_url": f"https://adzuna.test/{i}",
             "location": {"display_name": "Sao Paulo", "area": ["Brasil"]}, "description": ""}
            for i, c in enumerate(companies)]}

    def _run(self, payload):
        env = {"ADZUNA_APP_ID": "x", "ADZUNA_APP_KEY": "y"}
        with mock.patch.dict("os.environ", env), mock.patch.object(sources, "_get", return_value=payload):
            return sources.src_adzuna(["devops"], country="br")

    def test_missing_or_blank_employer_gets_visible_label(self):
        rows = self._run(self._canned(None, {}, {"display_name": "  "}, {"display_name": "Acme"}))
        self.assertEqual([r["company"] for r in rows],
                         [sources.UNDISCLOSED_COMPANY] * 3 + ["Acme"])

    def test_anonymous_ads_never_merge_even_at_five_locations(self):
        jobs = [{"title": "Devops Engineer", "company": sources.UNDISCLOSED_COMPANY,
                 "location": f"City {i}", "url": f"https://adzuna.test/{i}", "_score": 1}
                for i in range(6)]
        kept, removed = radar.collapse_mass_posted(jobs)
        self.assertEqual((len(kept), removed), (6, 0))


class FailedQueryWarningTests(unittest.TestCase):
    def test_http_error_keeps_code_and_query(self):
        import urllib.error
        import sources

        sources.WARN.clear()

        def boom(q):
            raise urllib.error.HTTPError("u", 429, "Too Many", {}, None)

        out = sources._from_queries("microsoft", ["sre"], boom)
        self.assertEqual(out, [])
        self.assertEqual(sources.WARN, ["microsoft:HTTP429:sre"])

    def test_other_errors_keep_class_and_query(self):
        import sources

        sources.WARN.clear()

        def boom(q):
            raise ValueError("x")

        sources._from_queries("amazon", ["devops"], boom)
        self.assertEqual(sources.WARN, ["amazon:ValueError:devops"])


class ManualPortalsTests(unittest.TestCase):
    def test_drops_companies_that_now_have_an_automated_feed(self):
        companies = {"greenhouse": ["anthropic"], "ashby": ["openai"],
                     "display_names": {"openai": "OpenAI"},
                     "workday": [{"tenant": "nvidia", "name": "NVIDIA"}],
                     "automated_portal_names": ["Amazon"]}
        portals = [{"company": n, "url": "u"} for n in
                   ("Anthropic", "OpenAI", "NVIDIA", "Amazon", "BHP (mining, Chile filter)")]
        left = radar.manual_portals(portals, companies)
        self.assertEqual([x["company"] for x in left], ["BHP (mining, Chile filter)"])


class NoSilentCapTests(unittest.TestCase):
    """Regression for 2026-10-23: the dashboard showed 88 openings because
    boards were clipped to 60 postings and every track to 40. Every
    qualifying posting a source returns must reach the output."""

    N = 150

    def test_every_qualifying_posting_reaches_the_output(self):
        import json
        import tempfile
        from unittest import mock

        board = [radar._job(f"Senior Site Reliability Engineer {i}", "Acme", "Remote",
                            f"https://example.test/{i}", True, "kubernetes terraform python")
                 for i in range(self.N)]
        empty = mock.Mock(return_value=[])
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(radar, "DATA", tmp), \
                mock.patch.object(radar, "src_greenhouse", return_value=board), \
                mock.patch.object(radar, "src_remotive", empty), \
                mock.patch.object(radar, "src_jobicy", empty), \
                mock.patch.object(radar, "src_arbeitnow", empty), \
                mock.patch.object(radar, "src_remoteok", empty), \
                mock.patch.object(radar, "src_lever", empty), \
                mock.patch.object(radar, "src_ashby", empty), \
                mock.patch.object(radar, "src_workday", empty), \
                mock.patch.object(radar, "src_getonboard", empty), \
                mock.patch.object(radar, "src_amazon", empty), \
                mock.patch.object(radar, "src_microsoft", empty), \
                mock.patch.object(radar, "src_adzuna", empty):
            radar.main()
            with open(f"{tmp}/latest.json", encoding="utf-8") as f:
                out = json.load(f)
        self.assertEqual(len(out["tracks"]["B"]), self.N)
        self.assertEqual(out["funnel"]["fetched"], self.N)
        self.assertEqual(out["funnel"]["comp_ok"], self.N)
        self.assertEqual(out["stats"]["unique"], self.N)
        self.assertEqual(out["funnel"]["title_senior"], self.N)
        self.assertEqual(out["funnel"]["title_unstated"], 0)

    def test_unstated_level_roles_are_included_and_flagged(self):
        import json
        import tempfile
        from unittest import mock

        board = [radar._job("Platform Engineer", "Acme", "Remote", "https://example.test/u",
                            True, "kubernetes terraform python")]
        empty = mock.Mock(return_value=[])
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(radar, "DATA", tmp), \
                mock.patch.object(radar, "src_greenhouse", return_value=board), \
                mock.patch.object(radar, "src_remotive", empty), \
                mock.patch.object(radar, "src_jobicy", empty), \
                mock.patch.object(radar, "src_arbeitnow", empty), \
                mock.patch.object(radar, "src_remoteok", empty), \
                mock.patch.object(radar, "src_lever", empty), \
                mock.patch.object(radar, "src_ashby", empty), \
                mock.patch.object(radar, "src_workday", empty), \
                mock.patch.object(radar, "src_getonboard", empty), \
                mock.patch.object(radar, "src_amazon", empty), \
                mock.patch.object(radar, "src_microsoft", empty), \
                mock.patch.object(radar, "src_adzuna", empty):
            radar.main()
            with open(f"{tmp}/latest.json", encoding="utf-8") as f:
                out = json.load(f)
        row = out["tracks"]["B"][0]
        self.assertEqual(row["level"], "unstated")
        self.assertIn("Level not stated", row["reasons"])
        self.assertEqual(out["funnel"]["title_unstated"], 1)


if __name__ == "__main__":
    unittest.main()
