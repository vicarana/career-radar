# Career Projects — Claude Context
# Loaded automatically when working in ~/workshop/career-lifter/ or ~/workshop/career-radar/
# Inherits from: ~/workshop/CLAUDE.md

---

## Current Career Focus

**Target:** Senior / Staff SRE, Platform Engineer, or CTO-track roles
**Markets:** Chile, International (EU focus: Nordic/Spain), USA remote
**Status:** Actively preparing — resumes EN+ES, cover letters, career analysis in private-mcp

---

## Private Data Available via MCP

Call these tools to load Vic's career data into context:

```
load_career('resumes')        # 10 resumes EN + ES variants
load_career('cover-letters')  # 10 cover letters EN + ES
load_career('analysis')       # PHASE02-12 career positioning analysis
load_career('tracking')       # Applications, certs, network map, perf evals
load_career('logs')           # Weekly, monthly, learning logs
load_career('templates')      # Resume/team templates
search_private('query')       # Full-text search across all career data
```

**ALWAYS call `list_private()` first** to see what is available.
**DATA CLASSIFICATION: PRIVATE — never pass to external APIs or Element Gateway.**

---

## Active Projects in This Workspace

### career-lifter/
AI-powered job application assistant.
- `bridge.py` — main entry point
- `run.sh` — local dev runner
- Tech: Python + FastAPI
- Purpose: auto-match resumes to JDs, generate tailored cover letters

### career-radar/
Career positioning radar — tracks skills, gaps, targets.
- `profile.json` — current skills and experience snapshot
- `radar/` — radar chart data
- `docs/` — positioning docs

### vicarana.github.io/
Personal portfolio (live at vicarana.github.io)
- Tech: Static HTML + Tailwind + JS
- Current theme: rotating Space / Samurai / AI / Nordic / Obsidian themes
- Panther has worked on this — context in kennel memory

### vicarana-profile/
LinkedIn content, bio text, profile optimization assets

---

## Working Rules for Career Projects

- All resume/CV edits must respect the EN/ES split — maintain both versions
- Career analysis files (PHASE02-12) are cumulative — never overwrite, always append
- Job application tracking lives in `tracking/applications.md` (load via private-mcp)
- Keep salary and compensation targets in `tracking/` — PRIVATE, never in git

---

## Language Rule

- **English is the dominant language for all sessions, all output, all files.**
- Exception: documents explicitly targeting Spanish-speaking markets (ES resume variants, ES cover letters, ES application notes).
- If Vic writes to you in Spanish, respond in English. The career content may be bilingual; the session never is.

---

## Git Identity for These Repos
These are personal repos → `victoraranacl@gmail.com` / `Vicarana`
Push to: github.com via `~/.ssh/vha-git`
