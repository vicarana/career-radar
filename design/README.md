# career-radar UI redesign: full process log

Chronicle of the 2026-08-26 UI redesign, from initial audit through 21
design explorations to the shipped Liquid Glass + AI-native minimal
build. Kept here so the reasoning and evidence survive past any single
chat session.

## 1. Why this started

The live PWA (`docs/index.html`) had **zero `@media` queries**, confirmed
by grepping the file before touching anything. It was a fixed
mobile-width layout that just stretched edge-to-edge on tablet/desktop.
The manifest also lacked `purpose: maskable` icon variants, so Android's
adaptive-icon system could crop the home-screen icon oddly.

## 2. Design exploration (21 options, all in `mockups/`)

Rather than guess at one direction, built clickable, resizable HTML
mockups for every option so decisions were made by looking at real
screens, not descriptions. Open `mockups/index.html` for the full
clickable gallery.

**Round 1 (A-G), grounded in the app's actual needs:**
| # | Name | Idea |
|---|---|---|
| A | Aurora Glass | Refined evolution of the original dark theme, responsive |
| B | Command Center | Dense ops-dashboard feel, bottom tab bar, list rows |
| C | Warm Minimal | Light editorial digest, serif type, light/dark toggle |
| D | Liquid Glass | Apple's current (iOS/visionOS 2025-26) translucent material design |
| E | Bento Grid | Modern SaaS asymmetric tile grid (Apple/Notion/Arc style) |
| F | Neo-Brutalist | Thick borders, hard offset shadows, flat saturated color |
| G | Swipe to Triage | Functional Tinder-style card stack, drag or tap to decide |

**Round 2 (H-U), full sweep of current web design trends** (requested
explicitly: "top 20 trending designs"):
Classic Glassmorphism, Neumorphism, AI-native minimal chat UI, Kinetic
big-type minimalism, Maximalism, Retro-futurism/Y2K, Claymorphism,
Gradient Mesh/Aurora, Scroll-driven micro-interactions (functional demo),
Variable/expressive typography, Monochrome + single accent, 3D isometric
icons, Skeuomorphic realism, Command-palette-first navigation (functional
demo).

Each mockup used the same sample data (Replit/GitLab/Datadog postings,
already-public real jobs pulled during earlier live runs) so styles were
comparable apples-to-apples.

## 3. Decision

Vic picked a mix: **J (AI-native minimal, floating input bar)** fused
with **D (Liquid Glass, responsive)**. Rationale discussed in-session:
native-feeling on iOS, minimal chrome for a daily-glance tool, floating
input reused as a live job search/filter bar instead of a separate
paste-only field.

## 4. Real implementation

Rewrote `docs/index.html`'s visual layer only. All JS logic, function
names, and data contracts kept identical to avoid regressions:
`dashboard()`, `jobCard()`, `matchView()`, `savedView()`, `render()`,
`load()`, save/tailor-CV prompts, service worker registration, all
untouched.

Changes:
- Translucent `.glass` panels (`backdrop-filter: blur()`), blurred
  color blobs behind the UI, floating pill nav
- Bottom floating tab bar (mobile) that becomes a sticky left glass rail
  (desktop, `>=960px`)
- New floating search bar filters jobs live by title/company/skill,
  visible everywhere except the Match JD tab (which has its own paste
  form)
- Consolidated the old LinkedIn/Walmart tabs into a "Quick Links"
  section under Dashboard, 7 tabs doesn't fit a usable mobile bottom
  nav, 5 does
- `manifest.webmanifest`: added `purpose: maskable` icon variants,
  `orientation`, `categories`

## 5. The bug found during testing

While verifying responsiveness with Playwright (not just eyeballing
screenshots), found a real Chromium engine bug:

```css
/* This silently resolves to top:0 instead of anchoring to the bottom */
.tabbar{position:fixed; bottom: calc(env(safe-area-inset-bottom) + 12px);}
```

Isolated across roughly 20 minimal reproductions (see chat history for
the full binary search) to confirm: `calc()` wrapping `env()` directly as
a `position:fixed` element's `bottom` value breaks the top/bottom solving
algorithm, independent of explicit height, `backdrop-filter`, or
`margin`. This is exactly the pattern most PWA tab bars use for iPhone
notch/home-indicator safe areas, a genuinely common trap.

**Fix:** nest `env()` inside `max()` first, then wrap in `calc()` if
extra offset is needed:
```css
/* Clean */
bottom: max(12px, env(safe-area-inset-bottom));
/* Also clean, for an offset above another floating element */
bottom: calc(max(12px, env(safe-area-inset-bottom)) + 70px);
```
Applied to `.tabbar`, `.searchbar`, and `.toast`, the three fixed-position
elements using this pattern.

Screenshots, in order:
1. `screenshots/01-bug-discovered-tabbar-at-top.png`, raw headless
   Chrome capture, tab bar rendering at the top instead of the bottom
2. `screenshots/02-first-fix-attempt-still-broken.png`, adding an
   explicit height alone did not fix it (this ruled out the first
   hypothesis)
3. `screenshots/03-bug-fixed-final-mobile.png`, correct anchoring after
   the `max()` fix, verified via `getBoundingClientRect()`, not just
   visual inspection
4. `screenshots/04-match-jd-tab-verified.png`, confirms the Match JD
   paste form still works, search bar correctly hidden on that tab
5. `screenshots/05-desktop-layout-verified.png`, glass rail nav,
   4-column stat grid, sticky search bar at `>=960px`
6. `screenshots/06-search-feature-verified.png`, live search filtering
   confirmed against real `data/latest.json`, zero console errors

## 6. Verification method

Not a single "looks fine" screenshot. Used Playwright to:
- Load the page against a local server serving the **real**
  `docs/data/latest.json` (no mock data)
- Read `getBoundingClientRect()` on the tab bar and search bar to prove
  numeric positioning, not just visual impression
- Click through tabs (Dashboard, Match JD) and confirm re-render
- Type into the search box and count actual filtered results
- Click the save/heart button and listen for `pageerror` events
  (zero errors)
- Screenshot at both `390x844` (mobile) and `1400x900` (desktop)

## 7. Shipped

Live at https://vicarana.github.io/career-radar/, commit history on
`main` in this repo covers the full diff.

## Full link index
- Live PWA: https://vicarana.github.io/career-radar/
- This repo: https://github.com/vicarana/career-radar
- Mockup gallery (local, open in browser): `design/mockups/index.html`
