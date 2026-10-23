#!/usr/bin/env python3
"""Offline tests for extra_sources.py: canned JSON, no network.

Run: python3 radar/test_extra_sources.py
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extra_sources  # noqa: E402

SITE = {"tenant": "acme", "wd": "wd5", "site": "Careers", "name": "Acme"}


def wd_page(total, titles):
    return {"total": total, "jobPostings": [
        {"title": t, "externalPath": f"/job/{i}", "locationsText": "Remote, US"}
        for i, t in enumerate(titles)]}


class WorkdayTests(unittest.TestCase):
    def test_pages_until_first_page_total_even_though_later_pages_report_zero(self):
        # Verified live: Workday returns `total` only on page 1, 0 afterwards.
        pages = [wd_page(25, ["a"] * 20), wd_page(0, ["b"] * 5)]
        with mock.patch.object(extra_sources, "_request_json", side_effect=pages) as req:
            rows = list(extra_sources.workday_postings(SITE, "sre"))
        self.assertEqual(len(rows), 25)
        self.assertEqual(req.call_count, 2)

    def test_row_shape_and_url(self):
        with mock.patch.object(extra_sources, "_request_json",
                               return_value=wd_page(1, ["Senior SRE"])):
            row = next(extra_sources.workday_postings(SITE, "sre"))
        self.assertEqual(row["company"], "Acme")
        self.assertEqual(row["url"], "https://acme.wd5.myworkdayjobs.com/Careers/job/0")
        self.assertTrue(row["remote"])

    def test_empty_board_stops_without_looping(self):
        with mock.patch.object(extra_sources, "_request_json",
                               return_value={"total": 0, "jobPostings": []}) as req:
            self.assertEqual(list(extra_sources.workday_postings(SITE, "sre")), [])
        self.assertEqual(req.call_count, 1)

    def test_broad_query_stops_at_page_limit_and_records_it(self):
        # Regression 2026-10-23: unbounded paging of broad queries hung a run.
        extra_sources.TRUNCATED.clear()
        with mock.patch.object(extra_sources, "_request_json",
                               return_value=wd_page(5000, ["a"] * 20)) as req:
            rows = list(extra_sources.workday_postings(SITE, "senior ai lead"))
        self.assertEqual(req.call_count, extra_sources.WORKDAY_MAX_PAGES)
        self.assertEqual(len(rows), 20 * extra_sources.WORKDAY_MAX_PAGES)
        self.assertEqual(extra_sources.TRUNCATED, ["workday:acme:senior ai lead"])


def gob_page(page, pages, n):
    return {"meta": {"page": page, "total_pages": pages}, "data": [{
        "attributes": {"title": f"Senior Cloud Engineer {page}-{i}", "remote": True,
                       "countries": ["Chile", "Remote"], "min_salary": 3400, "max_salary": 4400,
                       "description": "<p>Run <b>kubernetes</b></p>",
                       "company": {"data": {"attributes": {"name": "Acme SpA"}}}},
        "links": {"public_url": f"https://www.getonbrd.com/jobs/{page}-{i}"}}
        for i in range(n)]}


class GetOnBoardTests(unittest.TestCase):
    def test_walks_every_page(self):
        pages = [gob_page(1, 2, 3), gob_page(2, 2, 2)]
        with mock.patch.object(extra_sources, "_request_json", side_effect=pages):
            rows = list(extra_sources.getonboard_postings("devops"))
        self.assertEqual(len(rows), 5)

    def test_normalizes_fields_salary_annualized_and_html_stripped(self):
        with mock.patch.object(extra_sources, "_request_json", return_value=gob_page(1, 1, 1)):
            row = next(extra_sources.getonboard_postings("devops"))
        self.assertEqual(row["company"], "Acme SpA")
        self.assertEqual(row["location"], "Chile, Remote")
        self.assertEqual((row["salary_min"], row["salary_max"]), (3400 * 12, 4400 * 12))
        self.assertNotIn("<", row["desc"])
        self.assertIn("kubernetes", row["desc"])

    def test_stops_at_page_limit_and_records_it(self):
        extra_sources.TRUNCATED.clear()
        with mock.patch.object(extra_sources, "_request_json",
                               return_value=gob_page(1, 99, 1)) as req:
            list(extra_sources.getonboard_postings("devops"))
        self.assertEqual(req.call_count, extra_sources.GETONBOARD_MAX_PAGES)
        self.assertEqual(extra_sources.TRUNCATED, ["getonboard:devops"])

    def test_missing_salary_stays_none_not_zero(self):
        page = gob_page(1, 1, 1)
        page["data"][0]["attributes"].update(min_salary=None, max_salary=None)
        with mock.patch.object(extra_sources, "_request_json", return_value=page):
            row = next(extra_sources.getonboard_postings("devops"))
        self.assertIsNone(row["salary_min"])


def amz_page(hits, n, intern_at=None):
    return {"hits": hits, "jobs": [
        {"title": f"DevOps Engineer {i}", "location": "US, WA, Seattle",
         "normalized_location": "Seattle, Washington, USA", "job_path": f"/en/jobs/{i}/x",
         "description_short": "Run <b>aws</b>", "basic_qualifications": "python", "is_intern": i == intern_at}
        for i in range(n)]}


class AmazonTests(unittest.TestCase):
    def test_pages_by_offset_and_skips_interns(self):
        pages = [amz_page(150, 100, intern_at=0), amz_page(150, 50)]
        with mock.patch.object(extra_sources, "_request_json", side_effect=pages) as req:
            rows = list(extra_sources.amazon_postings("devops"))
        self.assertEqual(len(rows), 149)  # 150 minus the one intern
        self.assertIn("offset=100", req.call_args_list[1][0][0])

    def test_row_shape(self):
        with mock.patch.object(extra_sources, "_request_json", return_value=amz_page(1, 1)):
            row = next(extra_sources.amazon_postings("devops"))
        self.assertEqual(row["company"], "Amazon")
        self.assertEqual(row["url"], "https://www.amazon.jobs/en/jobs/0/x")
        self.assertEqual(row["location"], "Seattle, Washington, USA")
        self.assertIn("aws", row["desc"])
        self.assertNotIn("<", row["desc"])

    def test_page_limit_is_recorded(self):
        extra_sources.TRUNCATED.clear()
        with mock.patch.object(extra_sources, "_request_json", return_value=amz_page(9999, 100)) as req:
            list(extra_sources.amazon_postings("devops"))
        self.assertEqual(req.call_count, extra_sources.AMAZON_MAX_PAGES)
        self.assertEqual(extra_sources.TRUNCATED, ["amazon:devops"])


def ms_page(count, n):
    return {"data": {"count": count, "positions": [
        {"name": f"Senior SRE {i}", "locations": ["India, Hyderabad", "US, Redmond"],
         "positionUrl": f"/careers/job/{i}", "workLocationOption": "remote",
         "department": "Site Reliability Engineering"} for i in range(n)]}}


class MicrosoftTests(unittest.TestCase):
    def test_pages_by_start_until_count(self):
        pages = [ms_page(15, 10), ms_page(15, 5)]
        with mock.patch.object(extra_sources, "_request_json", side_effect=pages) as req:
            rows = list(extra_sources.microsoft_postings("sre"))
        self.assertEqual(len(rows), 15)
        self.assertIn("start=10", req.call_args_list[1][0][0])

    def test_row_shape(self):
        with mock.patch.object(extra_sources, "_request_json", return_value=ms_page(1, 1)):
            row = next(extra_sources.microsoft_postings("sre"))
        self.assertEqual(row["company"], "Microsoft")
        self.assertEqual(row["url"], "https://apply.careers.microsoft.com/careers/job/0")
        self.assertEqual(row["location"], "India, Hyderabad; US, Redmond")
        self.assertTrue(row["remote"])

    def test_page_limit_is_recorded(self):
        extra_sources.TRUNCATED.clear()
        with mock.patch.object(extra_sources, "_request_json", return_value=ms_page(9999, 10)) as req:
            list(extra_sources.microsoft_postings("sre"))
        self.assertEqual(req.call_count, extra_sources.MICROSOFT_MAX_PAGES)
        self.assertEqual(extra_sources.TRUNCATED, ["microsoft:sre"])


if __name__ == "__main__":
    unittest.main()
