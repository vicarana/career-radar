#!/usr/bin/env python3
"""sources.py - every job-source adapter for career-radar.

Split out of radar.py on 2026-10-23 (it had grown past the 600 line
guideline). Each src_* function fetches one source and returns rows built
by _job(). Failures never raise out of here: they append to WARN so the
output says which source broke. ATTEMPTED/WARN are shared module state,
radar.py imports the same list objects.

Query-driven non-ATS sources (Workday, Get on Board, Amazon, Microsoft)
do their fetch/parse in extra_sources.py and are wrapped here.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

import extra_sources

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
WARN = []
ATTEMPTED = []


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


# Adzuna omits the employer on confidential and some agency posts (10 of
# ~1,300 rows on 2026-10-24, all Brazil/Spain). The name is not recoverable,
# so say so on the card instead of rendering a blank company.
UNDISCLOSED_COMPANY = "Company not disclosed"


def _job(title, company, location, url, remote, desc, salary_min=None, salary_max=None):
    return {
        "title": (title or "").strip(),
        "company": (company or "").strip(),
        "location": (location or "").strip(),
        "url": (url or "").strip(),
        "remote": bool(remote),
        "text": " ".join(filter(None, [title, company, location, desc])).lower(),
        "salary_min": salary_min,
        "salary_max": salary_max,
    }


def src_remotive(qs):
    out = []
    for q in qs:
        try:
            d = _get("https://remotive.com/api/remote-jobs?search=" + urllib.parse.quote(q))
            for j in d.get("jobs", []):
                out.append(_job(j.get("title"), j.get("company_name"),
                                j.get("candidate_required_location"), j.get("url"),
                                True, j.get("description", "")[:400]))
        except Exception as e:
            WARN.append(f"remotive:{type(e).__name__}")
    return out


def src_jobicy(qs):
    out = []
    for q in qs:
        try:
            d = _get("https://jobicy.com/api/v2/remote-jobs?count=50&tag=" + urllib.parse.quote(q))
            for j in d.get("jobs", []):
                out.append(_job(j.get("jobTitle"), j.get("companyName"), j.get("jobGeo"),
                                j.get("url"), True, (j.get("jobExcerpt") or "")[:400]))
        except Exception as e:
            WARN.append(f"jobicy:{type(e).__name__}")
    return out


def src_arbeitnow():
    out = []
    try:
        d = _get("https://www.arbeitnow.com/api/job-board-api")
        for j in d.get("data", []):
            tags = " ".join(j.get("tags", []) or [])
            out.append(_job(j.get("title"), j.get("company_name"), j.get("location"),
                            j.get("url"), j.get("remote", False),
                            (j.get("description", "") or "")[:400] + " " + tags))
    except Exception as e:
        WARN.append(f"arbeitnow:{type(e).__name__}")
    return out


def src_remoteok(qs):
    out = []
    try:
        d = _get("https://remoteok.com/api")
        for j in [r for r in d if isinstance(r, dict) and r.get("position")]:
            tags = " ".join(j.get("tags", []) or [])
            out.append(_job(j.get("position"), j.get("company"), j.get("location") or "Remote",
                            j.get("url"), True, (j.get("description", "") or "")[:300] + " " + tags,
                            salary_min=j.get("salary_min"), salary_max=j.get("salary_max")))
    except Exception as e:
        WARN.append(f"remoteok:{type(e).__name__}")
    return out


def humanize_company(slug, companies):
    """ATS board slugs are plain lowercase URL segments ('grafanalabs',
    'gitlab'), not display names. Prefer an explicit override from
    companies.json's display_names map, fall back to a plain title-case
    for anything not listed there (works fine for most single-word
    slugs, e.g. 'samsara' -> 'Samsara')."""
    overrides = companies.get("display_names", {})
    return overrides.get(slug) or slug.replace("-", " ").title()


def src_greenhouse(slugs, companies):
    """Public, unauthenticated ATS board API. Companies opt into this feed
    on purpose so their own careers page can render it."""
    ATTEMPTED.append("greenhouse")
    out = []
    for slug in slugs:
        try:
            d = _get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
            for j in d.get("jobs", []):
                loc = (j.get("location") or {}).get("name", "")
                row = _job(j.get("title"), humanize_company(slug, companies), loc, j.get("absolute_url"),
                           "remote" in loc.lower(), (j.get("content") or "")[:400])
                row["_career_root"] = f"https://job-boards.greenhouse.io/{slug}"
                out.append(row)
        except Exception as e:
            WARN.append(f"greenhouse:{slug}:{type(e).__name__}")
    return out


def src_lever(slugs, companies):
    """Public, unauthenticated ATS board API (same opt-in pattern as Greenhouse)."""
    ATTEMPTED.append("lever")
    out = []
    for slug in slugs:
        try:
            d = _get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
            for j in d:
                cats = j.get("categories", {}) or {}
                loc = cats.get("location", "")
                row = _job(j.get("text"), humanize_company(slug, companies), loc, j.get("hostedUrl"),
                           "remote" in loc.lower(), (j.get("descriptionPlain") or "")[:400])
                row["_career_root"] = f"https://jobs.lever.co/{slug}"
                out.append(row)
        except Exception as e:
            WARN.append(f"lever:{slug}:{type(e).__name__}")
    return out


def src_ashby(slugs, companies):
    """Public, unauthenticated ATS board API (same opt-in pattern as Greenhouse)."""
    ATTEMPTED.append("ashby")
    out = []
    for slug in slugs:
        try:
            d = _get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
            for j in d.get("jobs", []):
                loc = j.get("location", "")
                row = _job(j.get("title"), humanize_company(slug, companies), loc, j.get("jobUrl"),
                           bool(j.get("isRemote")), (j.get("descriptionPlain") or "")[:400])
                row["_career_root"] = f"https://jobs.ashbyhq.com/{slug}"
                out.append(row)
        except Exception as e:
            WARN.append(f"ashby:{slug}:{type(e).__name__}")
    return out


def src_adzuna(qs, country="us"):
    """Free-tier aggregator API. Skips cleanly if creds aren't set - no crash,
    just fewer sources, same graceful-degrade pattern as sync-profile.yml.
    Adzuna has no single global search, every query is scoped to one
    country in the URL path itself, so covering multiple geographies means
    calling this once per country code, not just adding more search terms
    to one call."""
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        return []
    ATTEMPTED.append("adzuna")
    out = []
    for q in qs:
        try:
            url = (f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
                   f"?app_id={app_id}&app_key={app_key}&results_per_page=50"
                   f"&what={urllib.parse.quote(q)}&content-type=application/json")
            # Shared helper: retries 429/503 (Adzuna answered HTTP 503 on and
            # off 2026-10-23/24, a different country each run), honors Retry-After.
            d = extra_sources._request_json(url, timeout=20)
            # Page 1 only (50 rows) on purpose: the free tier is quota
            # limited and 7 countries x 18 titles is already ~126 calls.
            # When Adzuna has more, say so in the output, never silently.
            if (d.get("count") or 0) > len(d.get("results", [])):
                extra_sources.TRUNCATED.append(f"adzuna:{country}")
            for j in d.get("results", []):
                loc = (j.get("location") or {}).get("display_name", "")
                # Adzuna's display_name often omits the country (e.g. a Mexico
                # City posting), which Track C/E matching needs. area[0] is the
                # country per Adzuna's docs (inferred, hence the defensive get).
                area = (j.get("location") or {}).get("area") or []
                if area and area[0].lower() not in loc.lower():
                    loc = f"{loc}, {area[0]}" if loc else area[0]
                employer = ((j.get("company") or {}).get("display_name") or "").strip()
                out.append(_job(j.get("title"), employer or UNDISCLOSED_COMPANY,
                                loc, j.get("redirect_url"), "remote" in loc.lower(),
                                (j.get("description") or "")[:800],
                                salary_min=j.get("salary_min"), salary_max=j.get("salary_max")))
        except urllib.error.HTTPError as e:
            # Capture the real status + a short body snippet, not just the
            # exception class name, "HTTPError" alone hides whether this is
            # bad creds (401), a malformed request (400), or a rate limit
            # (429), each needs a different fix and a bare class name can't
            # tell them apart.
            try:
                body = e.read().decode("utf-8", "replace")[:150]
            except Exception:
                body = ""
            WARN.append(f"adzuna:{country}:HTTP{e.code}:{body}")
            if e.code in extra_sources.RETRY_STATUSES:
                # Retries already ran out. The country is down or throttling us,
                # so each remaining query would only burn another round of
                # waits (up to 14 s). Skip them, the next run tries again.
                break
        except Exception as e:
            WARN.append(f"adzuna:{country}:{type(e).__name__}")
    return out


def src_workday(sites, qs):
    """Public Workday CXS job-search endpoint, one board per entry in
    companies.json's "workday" list. Fetch/parse lives in extra_sources."""
    ATTEMPTED.append("workday")
    out = []
    for site in sites:
        root = extra_sources.workday_root(site)
        for q in qs:
            try:
                for row in extra_sources.workday_postings(site, q):
                    job = _job(**row)
                    job["_career_root"] = root
                    out.append(job)
            except Exception as e:
                WARN.append(f"workday:{site['tenant']}:{type(e).__name__}")
    return out


def _from_queries(name, qs, rows_for):
    """Shared wrapper for query-driven sources living in extra_sources: one
    ATTEMPTED entry, one WARN entry per failed query, rows through _job()."""
    ATTEMPTED.append(name)
    out = []
    for q in qs:
        try:
            out.extend(_job(**row) for row in rows_for(q))
        except urllib.error.HTTPError as e:
            # The bare class name hides whether this is a rate limit (429),
            # a block (403) or a bad request (400). Keep the code + query.
            WARN.append(f"{name}:HTTP{e.code}:{q}")
        except Exception as e:
            WARN.append(f"{name}:{type(e).__name__}:{q}")
    return out


def src_getonboard(qs):
    """Get on Board, a Chile-based LatAm tech job board with a free public
    API. Feeds Track E (LatAm/Chile) directly."""
    return _from_queries("getonboard", qs, extra_sources.getonboard_postings)


def src_amazon(qs):
    """Amazon's own public job search JSON (amazon.jobs)."""
    return _from_queries("amazon", qs, extra_sources.amazon_postings)


def src_microsoft(qs):
    """Microsoft's public careers search JSON (apply.careers.microsoft.com)."""
    return _from_queries("microsoft", qs, extra_sources.microsoft_postings)
