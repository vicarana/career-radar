"""Fetch + parse for the sources that aren't a plain ATS board feed:
Workday (many big employers), Get on Board (Chile-based LatAm tech board),
Amazon and Microsoft (their own careers search JSON).

Pure stdlib, no import of radar.py on purpose: radar.py wraps these rows with
its own _job()/WARN/ATTEMPTED bookkeeping, so this module stays a small,
network-only seam that unit tests can feed canned JSON.

All public endpoints were verified live from GitHub Actions on 2026-10-23
(Nvidia and Salesforce Workday boards, getonbrd.com/api/v0, amazon.jobs and
apply.careers.microsoft.com). Every function
yields dicts whose keys match radar._job()'s parameters.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
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
AMAZON_PAGE = 100  # verified: result_limit=100 returns 100 rows.
AMAZON_MAX_PAGES = 3
MICROSOFT_PAGE = 10  # verified: the endpoint serves 10 rows per call.
MICROSOFT_MAX_PAGES = 5
TRUNCATED = []
RETRY_STATUSES = (429, 503)
RETRY_MAX = 3
GETONBOARD_PAUSE = 0.5  # seconds between calls, it rate limits (HTTP 429)
MICROSOFT_PAUSE = 1.0
_TAGS = re.compile(r"<[^>]+>")


def _retry_wait(err, attempt):
    """Seconds to wait before retrying a refused request: honor Retry-After
    when it is a number, else back off 2s, 4s, 8s. Capped at 30s."""
    try:
        header = float((err.headers or {}).get("Retry-After"))
    except (TypeError, ValueError):
        header = 0.0
    return min(header or 2 ** (attempt + 1), 30.0)


def _request_json(url, body=None, timeout=25, pause=0.0):
    """GET (or POST when `body` is given) and parse JSON.

    Retries 429/503 up to RETRY_MAX times, then raises. `pause` sleeps after a
    successful call, for hosts that rate limit (2026-10-23: Microsoft and Get
    on Board answered HTTP 429 when queried at full speed, silently losing
    most queries). Any other error raises immediately and loudly.
    """
    headers = {"User-Agent": UA, "Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    for attempt in range(RETRY_MAX + 1):
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                parsed = json.loads(r.read().decode("utf-8", "replace"))
            break
        except urllib.error.HTTPError as err:
            if err.code not in RETRY_STATUSES or attempt == RETRY_MAX:
                raise
            time.sleep(_retry_wait(err, attempt))
    if pause:
        time.sleep(pause)
    return parsed


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
                          f"&page={page}&expand=%5B%22company%22%5D", pause=GETONBOARD_PAUSE)
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


def amazon_postings(query):
    """Amazon's own job search JSON, paged by offset (100 per page).

    `hits` is the total for the query. Interns are skipped using Amazon's own
    `is_intern` flag. Description = short description + basic qualifications,
    which is where the skill keywords live.
    """
    offset, hits, pages_read = 0, None, 0
    while hits is None or offset < hits:
        if pages_read >= AMAZON_MAX_PAGES:
            TRUNCATED.append(f"amazon:{query}")
            break
        d = _request_json("https://www.amazon.jobs/en/search.json?result_limit="
                          f"{AMAZON_PAGE}&offset={offset}&base_query={urllib.parse.quote(query)}")
        pages_read += 1
        if hits is None:
            hits = d.get("hits", 0)
        rows = d.get("jobs", [])
        if not rows:
            break
        for j in rows:
            if j.get("is_intern"):
                continue
            loc = j.get("normalized_location") or j.get("location") or ""
            desc = " ".join(filter(None, [j.get("description_short"), j.get("basic_qualifications")]))
            yield {"title": j.get("title"), "company": "Amazon", "location": loc,
                   "url": "https://www.amazon.jobs" + (j.get("job_path") or ""),
                   "remote": "virtual" in loc.lower() or "remote" in loc.lower(),
                   "desc": _TAGS.sub(" ", desc)}
        offset += AMAZON_PAGE


def microsoft_postings(query):
    """Microsoft's public careers search JSON, paged by `start` (10 per page).

    The old gcsservices.careers.microsoft.com endpoint now fails TLS
    verification, this is the working replacement (verified 2026-10-23).
    `data.count` is the total. No description is returned, so scoring leans
    on title + department + locations. The job URL base is inferred from
    positionUrl, not independently opened.
    """
    start, total, pages_read = 0, None, 0
    while total is None or start < total:
        if pages_read >= MICROSOFT_MAX_PAGES:
            TRUNCATED.append(f"microsoft:{query}")
            break
        d = _request_json("https://apply.careers.microsoft.com/api/pcsx/search"
                          f"?domain=microsoft.com&query={urllib.parse.quote(query)}&start={start}",
                          pause=MICROSOFT_PAUSE)
        pages_read += 1
        data = d.get("data") or {}
        if total is None:
            total = data.get("count", 0)
        rows = data.get("positions", [])
        if not rows:
            break
        for j in rows:
            locs = j.get("locations") or []
            yield {"title": j.get("name"), "company": "Microsoft", "location": "; ".join(locs),
                   "url": "https://apply.careers.microsoft.com" + (j.get("positionUrl") or ""),
                   "remote": j.get("workLocationOption") == "remote",
                   "desc": j.get("department") or ""}
        start += MICROSOFT_PAGE
