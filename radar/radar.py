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
DATA = os.path.join(ROOT, "docs", "data")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
WARN = []


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


def score(job, p):
    t, title = job["text"], job["title"].lower()
    if any(s in title for s in p["avoid_skills"]):
        return -99
    sc = 0
    sc += sum(2 for s in p["target_titles"] if s in title)
    sc += sum(2 for s in p["strong_skills"] if s in t)
    sc += sum(1 for s in p["good_skills"] if s in t)
    return sc


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

    jobs = (src_remotive(["sre", "devops", "platform engineer", "automation", "reliability"])
            + src_jobicy(["devops", "engineering", "python"])
            + src_arbeitnow()
            + src_remoteok(["sre", "devops", "platform"]))

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
        return [{"title": j["title"], "company": j["company"], "location": j["location"],
                 "url": j["url"], "score": j["_score"], "visa": j.get("visa", False)}
                for j in lst[:40]]

    now = dt.datetime.now(dt.timezone.utc)
    date = now.strftime("%Y-%m-%d %H:%M UTC")
    sources_ok = 4 - len({w.split(":")[0] for w in WARN})
    payload = {
        "generated": date,
        "sources_ok": sources_ok,
        "tracks": {"B": clean(buckets["B"]), "C": clean(buckets["C"])},
        "linkedin": linkedin_searches(),
        "walmart_markets": p["track_a_walmart_markets"]["portals"],
        "warnings": sorted(set(WARN)),
    }

    os.makedirs(os.path.join(DATA, "history"), exist_ok=True)
    with open(os.path.join(DATA, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    day = now.strftime("%Y-%m-%d")
    with open(os.path.join(DATA, "history", f"{day}.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    lines = [f"# career-radar - {date}", f"Sources OK: {sources_ok}/4\n"]
    for tk, name in [("C", "Track C - Europe (visa-first)"), ("B", "Track B - Remote/income")]:
        lines.append(f"\n## {name} ({len(buckets[tk])})")
        for j in buckets[tk][:20]:
            v = " [VISA]" if j.get("visa") else ""
            lines.append(f"- {j['title']} @ {j['company'] or '?'} ({j['location'] or 'n/a'}) "
                         f"s{j['_score']}{v} {j['url']}")
    with open(os.path.join(DATA, "latest.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"[radar] {date}: B={len(buckets['B'])} C={len(buckets['C'])} sources={sources_ok}/4")


if __name__ == "__main__":
    main()
