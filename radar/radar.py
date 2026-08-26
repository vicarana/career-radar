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


def _job(title, company, location, url, remote, desc):
    return {
        "title": (title or "").strip(),
        "company": (company or "").strip(),
        "location": (location or "").strip(),
        "url": (url or "").strip(),
        "remote": bool(remote),
        "text": " ".join(filter(None, [title, company, location, desc])).lower(),
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
                            j.get("url"), True, (j.get("description", "") or "")[:300] + " " + tags))
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
                                (j.get("description") or "")[:400]))
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


def tracks_of(job, p):
    t, tks = job["text"], set()
    if job["remote"] or "remote" in t or "anywhere" in t:
        tks.add("B")
    eu = p["track_c_europe"]
    if any(c in t for c in eu["countries"]):
        tks.add("C")
        if any(v in t for v in eu["visa_terms"]):
            job["visa"] = True
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
            + src_adzuna(["site reliability engineer", "devops engineer", "platform engineer"]))

    seen, uniq = set(), []
    for j in jobs:
        k = j["url"] or (j["title"] + j["company"])
        if k not in seen:
            seen.add(k)
            uniq.append(j)

    buckets = {"B": [], "C": []}
    for j in uniq:
        s = score(j, p)
        if s < p.get("min_score", 3):
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
                         "visa": j.get("visa", False), "reasons": reasons_for(j, p)})
        return rows

    now = dt.datetime.now(dt.timezone.utc)
    date = now.strftime("%Y-%m-%d %H:%M UTC")
    total_attempted = len(set(ATTEMPTED))
    sources_ok = total_attempted - len({w.split(":")[0] for w in WARN})
    B, C = clean(buckets["B"]), clean(buckets["C"])
    allrows = B + C
    stats = {
        "total": len(allrows),
        "track_b": len(B),
        "track_c": len(C),
        "grade_a": sum(1 for r in allrows if r["grade"] == "A"),
        "grade_b": sum(1 for r in allrows if r["grade"] == "B"),
        "visa": sum(1 for r in C if r["visa"]),
    }
    payload = {
        "generated": date,
        "sources_ok": sources_ok,
        "sources_total": total_attempted,
        "stats": stats,
        "tracks": {"B": B, "C": C},
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
    for tk, name in [("C", "Track C - Europe (visa-first)"), ("B", "Track B - Remote/income")]:
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
