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
- `radar/radar.py` - cloud aggregator (pure stdlib; public job APIs; NO scraping).
- `profile.json` - your targets (synced from MClaude, or edit here).
- `docs/` - the PWA (GitHub Pages serves this). `index.html`, `sw.js`, icons, `data/`.
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
