# career-radar (App 1) - Tracks B + C

Your personal job radar for **remote/income (B)** and **Europe relocation (C)** roles.
Runs in **GitHub Actions (cloud)** - not your Walmart Mac, not Walmart DNS - and shows
up as an **installable iPhone app** (PWA).

## Why this exists
- Walmart DNS blocks job APIs and job-hunting on the work laptop is a bad idea.
- This moves the whole hunt to the cloud. You just read results on your phone.

## Architecture
```
MClaude (private brain) --sync-profile.yml--> career-radar --daily-radar.yml--> docs/data/latest.json --> iPhone PWA
```

## Pieces
- `design/README.md` - full UI redesign process log: 21 design mockups
  considered, the decision, and a real Chromium engine bug found + fixed
  during the rebuild. Start here if you want the "why" behind the UI.
- `radar/radar.py` - cloud aggregator (pure stdlib; public job APIs + public ATS board
  APIs; NO LinkedIn/employer scraping, ever).
- `radar/companies.json` - watchlist of company slugs for the Greenhouse/Lever/Ashby
  adapters. Tune freely, no code changes needed.
- `profile.json` - your targets (synced from MClaude, or edit here).
- `docs/` - the PWA (GitHub Pages serves this). `index.html`, `match.js`, `sw.js`,
  icons, `data/`.
- `.github/workflows/daily-radar.yml` - daily cloud run (11:00 UTC) + manual trigger.
- `.github/workflows/sync-profile.yml` - pulls profile.json from MClaude (needs PAT).

## One-time setup
1. Create **public** repo `vicarana/career-radar` at https://github.com/new (no README).
2. Push (remote already set):
   ```bash
   cd ~/workshop/career-radar && git push -u origin main
   ```
3. **Enable Pages:** Settings -> Pages -> Deploy from branch -> `main` / `/docs` -> Save.
   Site: `https://vicarana.github.io/career-radar/`
4. **Enable Actions write:** Settings -> Actions -> General -> Workflow permissions ->
   "Read and write permissions" -> Save.
5. (Optional pipeline) Add secret `MCLAUDE_PAT` (fine-grained PAT, read Contents on
   vicarana/MClaude) so `sync-profile.yml` can pull your master profile.
6. Run it now: Actions tab -> **daily-radar** -> Run workflow. Wait ~1 min.

## Install on iPhone
1. Open `https://vicarana.github.io/career-radar/` in **Safari**.
2. Share -> **Add to Home Screen**. Now it's an app icon; opens full-screen, works offline.

## Code from your phone
- GitHub -> this repo -> `.` (or press `.`) opens **github.dev** (VS Code in Safari).
- Or spin a **Codespace** (Code -> Codespaces) and run Claude Code inside it (subscription auth).

## Tuning
Edit `profile.json` (titles, countries, `min_score`), commit, push. Next run uses it.
Edit `radar/companies.json` to add/remove companies for the ATS-board adapters.

## Job sources (all ToS-safe, no scraping, no LinkedIn/employer session access)
| Source | Auth needed | Notes |
|---|---|---|
| Remotive, Jobicy, Arbeitnow, RemoteOK | None | Public remote-job aggregator APIs |
| Greenhouse, Lever, Ashby | None | Public ATS board JSON, opt-in by the employer |
| Adzuna | Free API key (optional) | Broader general aggregator |
| LinkedIn, careerhound.io, anywhere else | None (manual) | Use the **Match JD** tab, see below |

### Enabling Adzuna (optional, widens coverage)
1. Sign up free at https://developer.adzuna.com/ , grab your `app_id` and `app_key`.
2. `gh secret set ADZUNA_APP_ID --repo vicarana/career-radar`
3. `gh secret set ADZUNA_APP_KEY --repo vicarana/career-radar`
4. If unset, `src_adzuna()` just skips, no crash, one fewer source counted in
   `sources_ok/sources_total` on the dashboard.

### Tuning company watchlist / diagnosing a dead slug
After any run, check `docs/data/latest.json` -> `warnings`. An entry like
`greenhouse:somecompany:HTTPError` means that slug is wrong or the company moved
ATS platforms. Fix or remove it in `radar/companies.json`, no code changes needed.

## Match JD tab: the LinkedIn-safe way to get gap analysis on any posting
We deliberately do not scrape LinkedIn or careerhound.io (session-based scraping
risks your account, see NOTICE.md's anti-scraping stance and the general spirit of
this project). Instead:

1. Find a posting yourself (LinkedIn, careerhound.io, anywhere), read it like normal.
2. Grab the job description text, either:
   - **Manually**: select all, copy, paste into the app's **Match JD** tab, or
   - **Bookmarklet** (faster): a one-click bookmark that grabs title/company/
     description from the page you're already viewing in your own logged-in
     session. Nothing automated, nothing repeated, functionally the same as
     you manually copying text yourself.
3. Paste into **Match JD**, tap Analyze. You get a grade, a match percent, which
   keywords you already cover, and a gap list (what the posting wants that isn't
   in your `profile.json` skill lists yet).
4. Tap **Tailor CV (with gaps)** to copy a Claude prompt that includes the gap
   list, so your tailored CV addresses it truthfully where it genuinely applies.
5. You click Apply yourself, on the employer's own site. No auto-submit, ever.

### Installing the bookmarklet
One-click, on-device, reads only the page you're already viewing in your own
logged-in session, functionally the same as manually selecting and copying text.

```javascript
javascript:(function(){var el=document.querySelector('.jobs-description__content,.jobs-box__html-content,article,main')||document.body;var title=(document.querySelector('h1')||{}).innerText||'';var company=(document.querySelector('.jobs-unified-top-card__company-name,.job-details-jobs-unified-top-card__company-name')||{}).innerText||'';var payload=(title+'\n'+company+'\n\n'+el.innerText).trim();navigator.clipboard.writeText(payload).then(function(){alert('JD copied - paste into career-radar.')}).catch(function(){prompt('Copy this text:',payload)});})();
```

**Mac (Chrome/Safari):** bookmark any page, edit it, paste the snippet above into
the URL field, name it "Grab JD". Click it on a job posting page.

**iPhone Safari:** bookmark any page to Favorites, edit it, paste the snippet into
the address field. On a job posting, tap the address bar, tap the bookmark.

LinkedIn changes its CSS class names occasionally, so the selectors above may need
a tweak every few months. Worst case it falls back to the whole page body text,
which the Match JD tab's cleaner will tidy up anyway.
