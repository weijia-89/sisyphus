# Differences vs python-jobspy (PyPI)

This repo is **not** a fork of [python-jobspy](https://github.com/speedyapply/JobSpy). It is a portable orchestration layer that calls upstream `scrape_jobs()` and adds filtering, triage, and profile-driven preferences.

## 1. What upstream JobSpy does

The PyPI package `python-jobspy` exposes a single scraper API:

- `jobspy.scrape_jobs()` — multi-board job search (Indeed, LinkedIn, Google Jobs, etc.)
- Returns a pandas DataFrame of raw listings (title, company, location, comp, URL, description when fetched)
- No opinionated filtering, prescreen scoring, dedup across daily runs, or triage verdicts

Upstream owns board adapters, rate limits, and HTML parsing inside the library.

## 2. What we added (sisyphus stack)

| Layer | Location | Purpose |
|-------|----------|---------|
| Multi-board tracks | `scripts/run_search.py` | Tracks A/B/C (Indeed+LI queries), G (Google), R (Remotive API), L (Lever), AS (Ashby), GH (Greenhouse) |
| Filter pipeline | `scripts/run_search.py` | Skip lists, title blockers/whitelist, PE signals, comp floor, desc blockers, US location, home-metro work-mode gate |
| Prescreen columns | `scripts/prescreen.py` | `stack_hits`, `yrs_req`, `domain`, `funding`, `priority` on each CSV row |
| Dedup + net-new export | `scripts/run_search.py` | Daily `jobspy_results_YYYYMMDD.csv` plus `_new.csv` for URLs absent from prior full exports |
| Yield logs | `scripts/run_search.py` | `yield_log.csv`, `yield_funnel.csv` funnel counts per run |
| Triage CLI | `scripts/triage_jobspy_csv.py` | Replays filter pipeline on CSV; `triage_verdict`, ILS estimate, arrangement post-gates, wrapper hints, Phase-4 domain columns |
| Domain inference | `lib/domain_inference.py` | Shared tier/gate heuristics for triage enrichment |
| Profile config | `config/search_profile.*`, `lib/search_profile.py` | YAML for remote preference, home metro, comp, ILS floors, enabled tracks, results dir, referral file |
| Application index auto-skip | `scripts/index_companies.py` | Optional merge from `application_index.html` (`JOB_APPLICATION_INDEX`) |

Environment variables for portability:

- `JOB_SEARCH_RESULTS_DIR` — CSV output directory (default: `data/jobspy_results` under repo root)
- `JOB_SEARCH_PROFILE` — active search profile YAML

## 3. What we did **not** fork

- **Do not vendor** python-jobspy source into this repo
- Stay on PyPI: `pip install python-jobspy` (see `requirements.txt`)
- Board-specific bugs and API changes are upstream concerns; bump the dependency version when needed

## 4. Historical port

The JobSpy orchestration in this repo was ported in 2026-05 from a monolithic local applications tree into `scripts/` and `lib/` with profile-driven paths. Same filter semantics; portable env vars and YAML instead of hardcoded metro paths. Daily commands:

```bash
cd ~/Projects/sisyphus
export JOB_SEARCH_PROFILE=config/search_profile.local.yaml
python3 scripts/run_search.py
python3 scripts/triage_jobspy_csv.py --latest --profile "$JOB_SEARCH_PROFILE"
```
