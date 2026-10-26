# Elk Grove Soccer — Roseville Cup Qualifier Match Hub

An independent, mobile-friendly match guide, branded with Elk Grove Soccer-inspired navy/orange/white. Not affiliated with or endorsed by Elk Grove Soccer, MLS NEXT, Cal North, Kitman or MLS Assist. Club logo is intentionally not used.

## Publish to GitHub Pages
1. Create a public repository, e.g. `elk-grove-roseville`.
2. Upload the **contents** of this ZIP to the repository root (`index.html` must be at the top level, alongside `data/` and `.github/`).
3. Under Settings → Pages choose **Deploy from a branch**, `main` → `/(root)` and save.
4. The site will be at `https://YOUR_USER.github.io/elk-grove-roseville/`.
5. If enabling the included GitHub Actions sync workflow: under Settings → Actions → General, allow **Read and write permissions** for the workflow's GITHUB_TOKEN (repository policy may vary). The workflow is scheduled every two hours, and can also be run manually. It won't fabricate matches if the source feed has none.

## Two schedule modes
- Draft: 18 static Elk Grove group fixtures extracted from the user's preliminary organizer field grid (3 games each for U13/U14/U15/U16/U17/U19). It works even with JavaScript disabled, and shows conditional knockout windows separately. The Groups section displays each age division's four-team draft pool and Elk Grove's three kickoff/field assignments.
- Published: requests `https://mls-assist.theintelligenceplatform.com/data/schedule/mls-next-cup-qualifier-roseville-regional.json` on selection/refresh. If cross-origin fetch fails it uses the locally synchronized snapshot (`data/published-schedule.json`) and clearly says the snapshot is cached, with its original sync date. If a local browser blocks both requests, it falls back to an embedded older dated snapshot. Scores are shown only when the event is marked completed.

No credentials are used or embedded. Third-party data access is not a formally documented integration; follow provider terms, and confirm the source before deploying automated retrieval.

## Map and parking
The interactive field sketch reproduces the field **numbering and approximate arrangement** from Cal North's organizer map. For entrance routes, concessions, accessibility and exact walking paths, use the linked *Official numbered field map*. Per organizer: North lot Fields 1,2,4,5,6,7; South lot Fields 3,8,9,10. Venue address: 2600 Westbrook Blvd, Roseville CA 95747.

## Contents
- `index.html`: complete site, including offline draft and field sketch
- `draft.html`, `published.html`, `groups.html`: compatibility redirects
- `data/published-schedule.json`: older public snapshot, provided as fallback, dated October 14, 2026 (not confirmed current)
- `tools/sync_published.py`: feed retrieval script for GitHub Actions
- `.github/workflows/sync-published.yml`: 2-hourly optional snapshot sync

Group section: All ages displays A-D across all six age divisions; selecting one age shows its four groups.

### Field map
The Field Map section loads the official Cal North PVSC complex map from an external image URL; an internet connection is required to display it. The numbered field guide and parking information remain available offline.
