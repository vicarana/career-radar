# Vic's Personal Workshop — Claude Context
# v0a01cb | victoraranacl@gmail.com | Updated: 2026-07-11

---

## Who I Am Working With

**Vic (Victor Arana)** — Staff SRE / Platform Engineer at Walmart Chile.
Personal email: victoraranacl@gmail.com | Walmart: Victor.Arana1@walmart.com
GitHub: vicarana | Walmart GHE: v0a01cb

---

## Available MCP Servers (loaded automatically)

| Server | What it gives you | Classification |
|--------|------------------|----------------|
| `private` | Career data: resumes, cover letters, analysis, 101s, logs | PRIVATE — local only, never send to APIs |
| `corpus` | WMT FlexPOS corpus, Quipu KB, store playbooks | CONFIDENTIAL — sanitize before Element Gateway |

**Always call `list_private()` first** to see what's available before loading files.
**Never pass PRIVATE or CONFIDENTIAL content to external LLM APIs.**

---

## Project Inventory

### Career Projects
- `~/workshop/career-lifter/`  — AI-powered resume/cover letter generator
- `~/workshop/career-radar/`   — Career positioning radar tool
- `~/workshop/vicarana-profile/` — LinkedIn / profile content
- `~/workshop/vicarana.github.io/` — Personal portfolio site

### Personal Infrastructure
- `~/workshop/Panther/`     — Code Puppy agent customizations
- `~/workshop/Quipu/`       — Knowledge base engine
- `~/workshop/tools/`       — Personal dev tools

### Walmart Work (use Walmart git identity)
- `~/workshop/cl-*/`        — Chile platform repos (email: Victor.Arana1@walmart.com)
- `~/workshop/Mig*/`        — Migration projects
- `~/workshop/vcert-*/`     — Cert management
- `~/workshop/AraOps*/`     — Ops tooling
- `~/workshop/wm-*/`        — WMT mobility

---

## Git Identity Rules (auto-applied via .gitconfig includeIf)

| Directory pattern | Identity |
|------------------|----------|
| `~/workshop/cl-*` `~/workshop/Mig*` `~/workshop/vcert-*` `~/workshop/wm-*` `~/workshop/AraOps*` | Victor.Arana1@walmart.com |
| Everything else | victoraranacl@gmail.com |

**Never cross-contaminate:** no Walmart commits with personal email or vice versa.

---

## Coding Standards (all projects)

- Python: `uv` + venvs outside OneDrive (`~/.venvs/<project>`)
- No secrets in git. No .env files committed. Use Akeyless for Walmart.
- Keep files under 600 lines. DRY, YAGNI, SOLID.
- Commit often with descriptive messages. Never force-push.
- New projects: `git init` + `.gitignore` (node_modules, .venv, .env*)

---

## Security Rules (this MacBook)

- FileVault: ON
- Firewall: ON + stealth mode
- Screen lock: immediate on sleep
- SSH keys: `~/.ssh/vha-git` for GitHub, `id_ed25519-retail-cert` for Walmart infra
- Secrets: KeePassXC + Akeyless. Never in OneDrive root.
- `.venv`, `node_modules`, `.git`, `.env*`, `*.jks` excluded from OneDrive via `.onedriveignore`

---

## Data Classification — Check Before Every LLM Call

```
PRIVATE (career data — salary, comp targets, resumes, 1on1 notes)
  -> LOCAL ONLY. No external APIs. Use private-mcp to load.

CONFIDENTIAL (FlexPOS server data, store IPs, Kafka creds, certs)
  -> LOCAL ONLY or run sanitize-for-element.sh before Element Gateway.

INTERNAL (Walmart code, architecture, non-public docs)
  -> Walmart tools only (Code Puppy on Eagle WiFi / VPN).

PUBLIC
  -> Anywhere.
```

---

## Git Commit Rules (absolute — no exceptions, no directory)

- Commits are signed by Vic only. Author = Vicarana <victoraranacl@gmail.com>. Always.
- NEVER add Co-Authored-By, Generated-By, Signed-off-by, or any trailer that names an AI tool.
- NEVER mention Claude, Anthropic, Panther, Wibey, Copilot, or any AI in commit messages.
- NEVER add tags or annotated tags on behalf of Vic without explicit instruction.
- If a tool tries to inject a co-author trailer, the global hook at ~/.git-hooks/prepare-commit-msg
  will strip it. Do not try to work around this.
- Commit messages: concise imperative subject line. Body is optional. No AI attribution anywhere.

## Behavior Rules for Panther

- **Language: English is dominant.** All output, all files, all comments — English by default.
  Exception: career documents explicitly targeting Spanish-speaking markets (ES resume variants, ES cover letters).
  Never switch to Spanish mid-session because the user wrote in Spanish.
- Read before modify. Always.
- One recommendation per decision point.
- No sycophancy. No openers/closers.
- Uncertainty = say so. Never fabricate.
- Exact scope only — fix what was asked, nothing else.
