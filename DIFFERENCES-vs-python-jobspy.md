# Differences vs python-jobspy (PyPI)

This repo is **not** a fork of [python-jobspy](https://github.com/speedyapply/JobSpy). It is a portable orchestration layer that calls upstream `scrape_jobs()` and adds filtering, triage, and profile-driven preferences.

## 1. What upstream JobSpy does

The PyPI package `python-jobspy` exposes a single scraper API:

- `jobspy.scrape_jobs()` — multi-board job search (Indeed, LinkedIn, Google Jobs, etc.)
- Returns a pandas DataFrame of raw listings (title, company, location, comp, URL, description when fetched)
- No opinionated filtering, prescreen scoring, dedup across daily runs, or triage verdicts

Upstream owns board adapters, rate limits, and HTML parsing inside the library.

## 2. What we added (sisyphus / toren stack)

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

## 4. Migration from `toren/applications/` paths

| toren (canonical today) | sisyphus (portable) |
|-------------------------|---------------------|
| `~/Projects/toren/applications/run_search_locally.py` | `scripts/run_search.py` |
| `~/Projects/toren/applications/prescreen.py` | `scripts/prescreen.py` |
| `~/Projects/toren/applications/index_companies.py` | `scripts/index_companies.py` |
| `~/Projects/toren/scripts/triage_jobspy_csv.py` | `scripts/triage_jobspy_csv.py` |
| `~/Projects/toren/applications/scripts/refresh_lib/domain_inference.py` | `lib/domain_inference.py` |
| `~/Projects/toren/applications/jobspy_results/` | `$JOB_SEARCH_RESULTS_DIR` or profile `output.results_dir` (default `./data/jobspy_results`) |
| `~/Projects/toren/applications/skip_companies.txt` | `config/skip_companies.txt` (or `JOB_SKIP_COMPANIES_FILE`) |
| `~/Projects/toren/applications/referral_status.txt` | profile `referrals.status_file` |
| `~/Projects/toren/applications/ils_overrides.json` | `config/ils_overrides.json` |
| `~/Projects/toren/applications/application_index.html` | optional `config/application_index.html` via `JOB_APPLICATION_INDEX` |
| Hardcoded Atlanta geo in scraper/triage | `home_metro.place_names` + `remote_preference` in search profile |

**Daily commands (sisyphus):**

```bash
cd ~/Projects/sisyphus
export JOB_SEARCH_PROFILE=config/search_profile.local.yaml
python3 scripts/run_search.py
python3 scripts/triage_jobspy_csv.py --latest --profile "$JOB_SEARCH_PROFILE"
```

**Equivalent toren commands:**

```bash
cd ~/Projects/toren/applications && python3 run_search_locally.py
cd ~/Projects/toren && python3 scripts/triage_jobspy_csv.py --latest
```

Filter logic is preserved verbatim from toren except for path resolution and profile-driven geo/comp/track settings.
