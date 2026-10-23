"""Fetch + parse for the two sources that aren't a plain ATS board feed:
Workday (many big employers) and Get on Board (Chile-based LatAm tech board).

Pure stdlib, no import of radar.py on purpose: radar.py wraps these rows with
its own _job()/WARN/ATTEMPTED bookkeeping, so this module stays a small,
network-only seam that unit tests can feed canned JSON.

Both public endpoints were verified live from GitHub Actions on 2026-10-23
(Nvidia and Salesforce Workday boards, getonbrd.com/api/v0). Every function
yields dicts whose keys match radar._job()'s parameters.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
WORKDAY_PAGE = 20  # Workday's CXS endpoint serves at most 20 rows per call.
GETONBOARD_PAGE = 100  # verified: per_page=100 returns 100 rows.
# Pages per SEARCH QUERY, not per board. Workday search is loose word
# matching, so a broad query (e.g. 'senior ai lead') can match most of a
# multi-thousand-posting board, and paging all of it for 18 queries x 2
# boards hung a real run for 6+ minutes (2026-10-23). Results are relevance
# ranked, so the first pages hold the real hits. Hitting the limit is never
# silent: it is recorded in TRUNCATED and surfaced in the output.
WORKDAY_MAX_PAGES = 3
GETONBOARD_MAX_PAGES = 5
TRUNCATED = []
_TAGS = re.compile(r"<[^>]+>")


def _request_json(url, body=None, timeout=25):
    headers = {"User-Agent": UA, "Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def workday_root(site):
    return f"https://{site['tenant']}.{site['wd']}.myworkdayjobs.com/{site['site']}"


def workday_postings(site, query):
    """Every posting a Workday board returns for one search term.

    Workday only reports `total` on the FIRST page (verified: later pages
    return 0), so the loop must remember the first one. Descriptions need a
    second call per job, so rows carry title + location only, scoring leans
    on the title for these.
    """
    api = (f"https://{site['tenant']}.{site['wd']}.myworkdayjobs.com"
           f"/wday/cxs/{site['tenant']}/{site['site']}/jobs")
    offset, total, pages_read = 0, None, 0
    while total is None or offset < total:
        if pages_read >= WORKDAY_MAX_PAGES:
            TRUNCATED.append(f"workday:{site['tenant']}:{query}")
            break
        d = _request_json(api, {"appliedFacets": {}, "limit": WORKDAY_PAGE,
                                "offset": offset, "searchText": query})
        pages_read += 1
        if total is None:
            total = d.get("total", 0)
        rows = d.get("jobPostings", [])
        if not rows:
            break
        for r in rows:
            loc = r.get("locationsText") or ""
            yield {"title": r.get("title"), "company": site.get("name") or site["tenant"],
                   "location": loc, "url": workday_root(site) + (r.get("externalPath") or ""),
                   "remote": "remote" in loc.lower(), "desc": ""}
        offset += WORKDAY_PAGE


def getonboard_postings(query):
    """Every Get on Board posting for one search term (paged).

    salary_min/max: the API reports USD per MONTH (inferred from a sample
    Senior role listed at 3400-4400, not independently verified), radar's
    comp floor expects annual USD, so values are multiplied by 12 here.
    """
    page, pages = 1, 1
    while page <= pages:
        if page > GETONBOARD_MAX_PAGES:
            TRUNCATED.append(f"getonboard:{query}")
            break
        d = _request_json("https://www.getonbrd.com/api/v0/search/jobs?query="
                          f"{urllib.parse.quote(query)}&per_page={GETONBOARD_PAGE}"
                          f"&page={page}&expand=%5B%22company%22%5D")
        pages = (d.get("meta") or {}).get("total_pages", 1)
        for j in d.get("data", []):
            a = j.get("attributes") or {}
            company = (((a.get("company") or {}).get("data") or {}).get("attributes") or {}).get("name")
            countries = a.get("countries") or []
            lo, hi = a.get("min_salary"), a.get("max_salary")
            yield {"title": a.get("title"), "company": company,
                   "location": ", ".join(countries), "url": (j.get("links") or {}).get("public_url"),
                   "remote": bool(a.get("remote")),
                   "desc": _TAGS.sub(" ", a.get("description") or ""),
                   "salary_min": lo * 12 if lo else None,
                   "salary_max": hi * 12 if hi else None}
        page += 1
