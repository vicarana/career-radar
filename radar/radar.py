#!/usr/bin/env python3
"""
radar.py - Cloud job aggregator for career-radar (Tracks B + C).

Runs in GitHub Actions (no Walmart DNS block). Pure stdlib.
Emits JSON the PWA reads, plus a markdown digest.

Outputs:
  docs/data/latest.json           (PWA reads this)
  docs/data/history/<date>.json   (archive)
  docs/data/latest.md             (human/Claude-readable)

Sources: public job-board JSON APIs only. NO LinkedIn/employer scraping.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROFILE = os.path.join(ROOT, "profile.json")
COMPANIES = os.path.join(HERE, "companies.json")
DATA = os.path.join(ROOT, "docs", "data")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
WARN = []
ATTEMPTED = []


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _title_has_term(title, term):
    """Plain substring match for long terms; word-boundary match for short
    ones (<=4 chars) so e.g. 'iv' or 'cio' don't false-hit inside unrelated
    words like 'Creative' or 'Director'."""
    t = term.lower()
    if len(t) <= 4:
        return re.search(r"\b" + re.escape(t) + r"\b", title) is not None
    return t in title


def is_senior_or_leadership(job, p):
    """Hard filter, requires BOTH: (a) a Senior+ IC or leadership-tier title,
    AND (b) genuine domain signal in the title itself. (b) is not optional:
    an earlier version of this filter checked tier alone, and non-technical
    Sales/Product/Support Director and Manager titles at tech companies
    leaked through, because score() can accumulate points from buzzwords
    anywhere in a company's boilerplate job description text (e.g. a
    Sales Director posting at a cloud company mentioning 'Kubernetes' in
    passing), even though the role itself has nothing to do with
    engineering. Requiring the domain term to be in the TITLE itself,
    not just the description, closes that leak."""
    title = job["title"].lower()
    seniority = p.get("seniority", [])
    leadership = p.get("leadership_titles", [])
    tier_ok = (any(_title_has_term(title, s) for s in seniority)
               or any(_title_has_term(title, s) for s in leadership))
    if not tier_ok:
        return False
    # Bare CTO/CIO is unambiguous on its own, no further domain check needed.
    csuite = ["cto", "cio", "chief technology officer", "chief information officer"]
    if any(_title_has_term(title, t) for t in csuite):
        return True
    domain_terms = p.get("target_titles", []) + ["engineering"]
    return any(_title_has_term(title, t) for t in domain_terms)


def meets_comp_floor(job, p):
    """Only excludes when comp is actually disclosed and clearly below the
    floor. Most public ATS boards (Greenhouse/Lever/Ashby) never disclose
    salary at all, those pass through untouched, comp_disclosed=False, so
    the UI can be honest about what wasn't actually checked. Adzuna and
    RemoteOK, the only two sources that disclose salary, both report it as
    annual USD, so no monthly-vs-annual guessing needed."""
    floor = p.get("min_comp_monthly_usd", 0)
    lo = job.get("salary_min")
    if not floor or lo is None:
        return True
    return (lo / 12) >= floor


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
            for j in d.get("jobs", [])[:40]:
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
            for j in d.get("jobs", [])[:40]:
                out.append(_job(j.get("jobTitle"), j.get("companyName"), j.get("jobGeo"),
                                j.get("url"), True, (j.get("jobExcerpt") or "")[:400]))
        except Exception as e:
            WARN.append(f"jobicy:{type(e).__name__}")
    return out


def src_arbeitnow():
    out = []
    try:
        d = _get("https://www.arbeitnow.com/api/job-board-api")
        for j in d.get("data", [])[:120]:
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
        for j in [r for r in d if isinstance(r, dict) and r.get("position")][:120]:
            tags = " ".join(j.get("tags", []) or [])
            out.append(_job(j.get("position"), j.get("company"), j.get("location") or "Remote",
                            j.get("url"), True, (j.get("description", "") or "")[:300] + " " + tags,
                            salary_min=j.get("salary_min"), salary_max=j.get("salary_max")))
    except Exception as e:
        WARN.append(f"remoteok:{type(e).__name__}")
    return out


def _load_companies():
    try:
        with open(COMPANIES, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        WARN.append(f"companies.json:{type(e).__name__}")
        return {}


def src_greenhouse(slugs):
    """Public, unauthenticated ATS board API. Companies opt into this feed
    on purpose so their own careers page can render it."""
    ATTEMPTED.append("greenhouse")
    out = []
    for slug in slugs:
        try:
            d = _get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
            for j in d.get("jobs", [])[:60]:
                loc = (j.get("location") or {}).get("name", "")
                out.append(_job(j.get("title"), slug, loc, j.get("absolute_url"),
                                "remote" in loc.lower(), (j.get("content") or "")[:400]))
        except Exception as e:
            WARN.append(f"greenhouse:{slug}:{type(e).__name__}")
    return out


def src_lever(slugs):
    """Public, unauthenticated ATS board API (same opt-in pattern as Greenhouse)."""
    ATTEMPTED.append("lever")
    out = []
    for slug in slugs:
        try:
            d = _get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
            for j in d[:60]:
                cats = j.get("categories", {}) or {}
                loc = cats.get("location", "")
                out.append(_job(j.get("text"), slug, loc, j.get("hostedUrl"),
                                "remote" in loc.lower(), (j.get("descriptionPlain") or "")[:400]))
        except Exception as e:
            WARN.append(f"lever:{slug}:{type(e).__name__}")
    return out


def src_ashby(slugs):
    """Public, unauthenticated ATS board API (same opt-in pattern as Greenhouse)."""
    ATTEMPTED.append("ashby")
    out = []
    for slug in slugs:
        try:
            d = _get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
            for j in d.get("jobs", [])[:60]:
                loc = j.get("location", "")
                out.append(_job(j.get("title"), slug, loc, j.get("jobUrl"),
                                bool(j.get("isRemote")), (j.get("descriptionPlain") or "")[:400]))
        except Exception as e:
            WARN.append(f"ashby:{slug}:{type(e).__name__}")
    return out


def src_adzuna(qs):
    """Free-tier aggregator API. Skips cleanly if creds aren't set - no crash,
    just fewer sources, same graceful-degrade pattern as sync-profile.yml."""
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        return []
    ATTEMPTED.append("adzuna")
    out = []
    for q in qs:
        try:
            url = ("https://api.adzuna.com/v1/api/jobs/us/search/1"
                   f"?app_id={app_id}&app_key={app_key}&results_per_page=40"
                   f"&what={urllib.parse.quote(q)}&content-type=application/json")
            d = _get(url)
            for j in d.get("results", []):
                loc = (j.get("location") or {}).get("display_name", "")
                out.append(_job(j.get("title"), (j.get("company") or {}).get("display_name"),
                                loc, j.get("redirect_url"), "remote" in loc.lower(),
                                (j.get("description") or "")[:800],
                                salary_min=j.get("salary_min"), salary_max=j.get("salary_max")))
        except Exception as e:
            WARN.append(f"adzuna:{type(e).__name__}")
    return out


def score(job, p):
    t, title = job["text"], job["title"].lower()
    if any(s in title for s in p["avoid_skills"]):
        return -99
    sc = 0
    sc += sum(2 for s in p["target_titles"] if s in title)
    sc += sum(2 for s in p["strong_skills"] if s in t)
    sc += sum(1 for s in p["good_skills"] if s in t)
    return sc


def grade_of(score):
    """Map raw score to an A-F letter + 0-100 match pct (career-ops-style rubric)."""
    if score >= 14:
        g = "A"
    elif score >= 10:
        g = "B"
    elif score >= 7:
        g = "C"
    elif score >= 4:
        g = "D"
    else:
        g = "F"
    pct = max(35, min(99, round(score / 20 * 100)))
    return g, pct


def reasons_for(job, p):
    """Top human-readable 'why it fits' reasons from matched strong/good skills."""
    t, title = job["text"], job["title"].lower()
    out = []
    for s in p["target_titles"]:
        if s in title:
            out.append("Title match: " + s)
            break
    for s in p["strong_skills"]:
        if s in t and len(out) < 3:
            out.append(s.strip().upper() if len(s) <= 4 else s.strip().title())
    for s in p["good_skills"]:
        if s in t and len(out) < 3:
            out.append(s.strip().title())
    return out[:3]


_SPONSOR_NEGATION = re.compile(
    r"(no|not|without|cannot|can.t|unable to|does not|doesn.t|do not|don.t|won.t|will not)"
    r"[\w\s]{0,20}(sponsor\w*|visa|work permit)"
    r"|(sponsor\w*)[\w\s]{0,15}(not (provided|available|offered)|unavailable)",
    re.I,
)


def sponsor_confirmed(text, visa_terms):
    """True only if a visa/relocation term appears AND isn't immediately
    negated. 'sponsorship' is a substring of both 'we offer sponsorship'
    and 'no sponsorship provided', a bare substring match would tag the
    second as a yes, inverting the actual meaning. This is a hard-gate
    feature (Track D only exists because sponsorship makes a US role
    viable at all), so a false positive here is worse than a false
    negative, if any negated mention is found anywhere, we don't confirm."""
    if not any(v in text for v in visa_terms):
        return False
    return not _SPONSOR_NEGATION.search(text)


def tracks_of(job, p):
    """Tags are additive, not exclusive: a remote US role can be both B and D.
    Track D (US + sponsor) is a hard AND, unlike Track C's soft visa tag,
    because a US role with no sponsorship offer genuinely isn't viable, not
    just a lower-priority one. Checks the full text (not just location)
    since 'Remote, US-only' postings often put the US detail in the
    description rather than the structured location field."""
    t, tks = job["text"], set()
    if job["remote"] or "remote" in t or "anywhere" in t:
        tks.add("B")
    eu = p["track_c_europe"]
    if any(c in t for c in eu["countries"]):
        tks.add("C")
        if any(v in t for v in eu["visa_terms"]):
            job["visa"] = True
    us = p.get("track_d_us_sponsor", {})
    if us and any(ind in t for ind in us.get("us_indicators", [])) \
            and sponsor_confirmed(t, eu["visa_terms"]):
        tks.add("D")
        job["us_sponsor"] = True
    return tks


def linkedin_searches():
    b = "https://www.linkedin.com/jobs/search/?keywords="
    combos = [
        ("SRE - Remote (B)", "Site Reliability Engineer", "&f_WT=2"),
        ("DevOps - Remote (B)", "DevOps Engineer", "&f_WT=2"),
        ("Platform - Netherlands (C)", "Platform Engineer", "&location=Netherlands"),
        ("SRE - Finland (C)", "Site Reliability Engineer", "&location=Finland"),
        ("DevOps - Germany (C)", "DevOps Engineer", "&location=Germany"),
        ("SRE - Norway (C)", "Site Reliability Engineer", "&location=Norway"),
        ("Automation - EU (C)", "Automation Engineer", "&location=European%20Union"),
    ]
    return [{"label": l, "url": b + urllib.parse.quote(k) + s} for l, k, s in combos]


def main():
    with open(PROFILE, encoding="utf-8") as f:
        p = json.load(f)
    companies = _load_companies()

    ATTEMPTED.extend(["remotive", "jobicy", "arbeitnow", "remoteok"])
    jobs = (src_remotive(["sre", "devops", "platform engineer", "automation", "reliability"])
            + src_jobicy(["devops", "engineering", "python"])
            + src_arbeitnow()
            + src_remoteok(["sre", "devops", "platform"])
            + src_greenhouse(companies.get("greenhouse", []))
            + src_lever(companies.get("lever", []))
            + src_ashby(companies.get("ashby", []))
            # The last 4 queries specifically target sponsorship-friendly
            # postings for Track D. Raw ATS feeds (Greenhouse/Lever/Ashby)
            # almost never spell out sponsorship in the posting text, that's
            # usually discussed in an interview, not the JSON payload. Adzuna
            # aggregates recruiter-written postings that more often call out
            # sponsorship explicitly as a selling point, and its `what=`
            # param free-text searches title+description, so searching for
            # the term itself surfaces postings that already contain it.
            + src_adzuna(["site reliability engineer", "devops engineer", "platform engineer",
                         "site reliability engineer visa sponsorship",
                         "platform engineer H1B sponsorship",
                         "devops manager relocation sponsorship",
                         "engineering manager visa sponsorship"]))

    seen, uniq = set(), []
    for j in jobs:
        k = j["url"] or (j["title"] + j["company"])
        if k not in seen:
            seen.add(k)
            uniq.append(j)

    buckets = {"B": [], "C": [], "D": []}
    for j in uniq:
        s = score(j, p)
        if s < p.get("min_score", 3):
            continue
        if not is_senior_or_leadership(j, p):
            continue
        if not meets_comp_floor(j, p):
            continue
        j["_score"] = s
        for tk in tracks_of(j, p):
            buckets[tk].append(j)
    for tk in buckets:
        buckets[tk].sort(key=lambda x: x["_score"], reverse=True)

    def clean(lst):
        rows = []
        for j in lst[:40]:
            g, pct = grade_of(j["_score"])
            rows.append({"title": j["title"], "company": j["company"], "location": j["location"],
                         "url": j["url"], "score": j["_score"], "grade": g, "match": pct,
                         "visa": j.get("visa", False), "us_sponsor": j.get("us_sponsor", False),
                         "reasons": reasons_for(j, p),
                         "salary_min": j.get("salary_min"), "salary_max": j.get("salary_max"),
                         "comp_disclosed": j.get("salary_min") is not None})
        return rows

    now = dt.datetime.now(dt.timezone.utc)
    date = now.strftime("%Y-%m-%d %H:%M UTC")
    total_attempted = len(set(ATTEMPTED))
    sources_ok = total_attempted - len({w.split(":")[0] for w in WARN})
    B, C, D = clean(buckets["B"]), clean(buckets["C"]), clean(buckets["D"])
    allrows = B + C + D
    stats = {
        "total": len(allrows),
        "track_b": len(B),
        "track_c": len(C),
        "track_d": len(D),
        "grade_a": sum(1 for r in allrows if r["grade"] == "A"),
        "grade_b": sum(1 for r in allrows if r["grade"] == "B"),
        "visa": sum(1 for r in C if r["visa"]),
    }
    payload = {
        "generated": date,
        "sources_ok": sources_ok,
        "sources_total": total_attempted,
        "stats": stats,
        "tracks": {"B": B, "C": C, "D": D},
        "linkedin": linkedin_searches(),
        "walmart_markets": p["track_a_walmart_markets"]["portals"],
        "warnings": sorted(set(WARN)),
        "profile_lite": {
            "target_titles": p["target_titles"],
            "strong_skills": p["strong_skills"],
            "good_skills": p["good_skills"],
            "avoid_skills": p["avoid_skills"],
        },
    }

    os.makedirs(os.path.join(DATA, "history"), exist_ok=True)
    with open(os.path.join(DATA, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    day = now.strftime("%Y-%m-%d")
    with open(os.path.join(DATA, "history", f"{day}.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    lines = [f"# career-radar - {date}", f"Sources OK: {sources_ok}/{total_attempted}\n"]
    for tk, name in [("D", "Track D - US (visa + relocation sponsor required)"),
                     ("C", "Track C - Europe (visa-first)"), ("B", "Track B - Remote/income")]:
        lines.append(f"\n## {name} ({len(buckets[tk])})")
        for j in buckets[tk][:20]:
            v = " [VISA]" if j.get("visa") else ""
            lines.append(f"- {j['title']} @ {j['company'] or '?'} ({j['location'] or 'n/a'}) "
                         f"s{j['_score']}{v} {j['url']}")
    with open(os.path.join(DATA, "latest.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"[radar] {date}: B={len(buckets['B'])} C={len(buckets['C'])} sources={sources_ok}/{total_attempted}")


if __name__ == "__main__":
    main()
