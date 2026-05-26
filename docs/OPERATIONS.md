# Operations

Day-to-day JobSpy scrape and triage from the sisyphus repo root. For architecture and the two-stack split, see `docs/ARCHITECTURE.md`.

## Prerequisites

```bash
cd ~/Projects/sisyphus
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config/search_profile.template.yaml config/search_profile.local.yaml
# edit owner, home_metro, comp, tracks
export JOB_SEARCH_PROFILE=config/search_profile.local.yaml
python3 -c "from lib.search_profile import load_profile; load_profile('$JOB_SEARCH_PROFILE')"
```

Keep `config/search_profile.local.yaml` and CSV exports out of git.

## Daily workflow

```bash
source .venv/bin/activate
export JOB_SEARCH_PROFILE=config/search_profile.local.yaml
python3 scripts/run_search.py
python3 scripts/triage_jobspy_csv.py --latest --profile "$JOB_SEARCH_PROFILE"
```

Optional profile wrapper (sets triage env from YAML):

```bash
python3 scripts/triage_with_profile.py --latest --profile "$JOB_SEARCH_PROFILE"
```

Pick a catalog persona instead of a local copy:

```bash
export JOB_SEARCH_PROFILE=config/search_profiles/single-high-col-2026.yaml
python3 scripts/run_search.py
python3 scripts/triage_jobspy_csv.py --latest --profile "$JOB_SEARCH_PROFILE"
```

## Outputs

Default directory: `data/jobspy_results/` (override with `JOB_SEARCH_RESULTS_DIR` or profile `output.results_dir`).

| Artifact | Pattern | Role |
|----------|---------|------|
| Full daily scrape | `jobspy_results_YYYYMMDD.csv` | All survivors after filters and prescreen |
| Net-new URLs | `jobspy_results_YYYYMMDD_new.csv` | Rows whose URL was absent from prior full exports |
| Triage export | `triage_YYYYMMDD.csv` (with `--out`) | Verdicts, ILS estimate, wrapper hints |
| Funnel | `yield_log.csv`, `yield_funnel.csv` | Per-run stage counts |
| Errors | `search_errors.log` | Scraper warnings (rate limits, DNS, etc.) |

Common CSV columns after scrape: `track`, `title`, `company`, `location`, `date_posted`, `min_amount`, `max_amount`, `priority`, `stack_hits`, `yrs_req`, `domain`, `funding`, `job_url`, `description`, `query`.

## Entry commands

| Purpose | Command |
|---------|---------|
| Daily scrape | `python3 scripts/run_search.py` |
| Triage latest CSV | `python3 scripts/triage_jobspy_csv.py --latest --profile "$JOB_SEARCH_PROFILE"` |
| Triage specific file | `python3 scripts/triage_jobspy_csv.py path/to/jobspy_results_YYYYMMDD.csv --profile "$JOB_SEARCH_PROFILE"` |
| Triage without post-gates | `python3 scripts/triage_jobspy_csv.py --latest --no-post-gates --profile "$JOB_SEARCH_PROFILE"` |
| Include PM/PO in apply pool | `python3 scripts/triage_jobspy_csv.py --latest --include-pm-po --profile "$JOB_SEARCH_PROFILE"` |
| Validate all catalog YAML | `./scripts/verify_search_profiles.sh` |
| Fit calculator (interactive) | `./corpofit --interactive` |

## Environment variables

| Variable | Role |
|----------|------|
| `JOB_SEARCH_PROFILE` | Active search profile YAML |
| `JOB_SEARCH_RESULTS_DIR` | Override CSV output directory |
| `JOB_SKIP_COMPANIES_FILE` | Override `config/skip_companies.txt` |
| `JOB_APPLICATION_INDEX` | Optional local HTML index path for auto-skip merge |

## Script map

| Path | Role |
|------|------|
| `scripts/run_search.py` | Multi-board scrape, filter pipeline, prescreen, yield logs |
| `scripts/triage_jobspy_csv.py` | CSV triage; replays filters; ILS and post-gates |
| `scripts/triage_with_profile.py` | Loads profile, delegates to triage with floors/paths |
| `scripts/prescreen.py` | Prescreen columns on scrape output |
| `scripts/index_companies.py` | Application index parser for auto-skip |
| `lib/search_profile.py` | YAML profile loader and helpers |
| `lib/domain_inference.py` | Domain/tier heuristics for triage |
| `config/skip_companies.txt` | Company skip slugs |
| `config/ils_overrides.json` | Per-company ILS overrides for triage |
| `config/profile_catalog.yaml` | Search profile catalog and fit JSON links |
| `fit/scripts/corpofit.py` | Stdlib job-fit calculator (via `./corpofit`) |

## Scraper tracks

Letters in the `track` column map to query bundles in `scripts/run_search.py`:

| Track | Boards / source |
|-------|-----------------|
| A | SDET / QA / eval (Indeed + LinkedIn) |
| B | AI IC eval / tooling |
| C | Technical PM / TPM |
| G | Google Jobs |
| R | Remotive API |
| L | Lever boards |
| AS | Ashby |
| GH | Greenhouse |

Enable tracks per profile: `tracks.enable` in YAML (see `docs/SEARCH_PROFILE.md`).

## Branch protection (optional)

To require pull requests on `main`, run `scripts/apply_branch_protection.sh` with `GH_REPO=weijia-89/sisyphus` after the remote exists (`DRY_RUN=1` prints the payload; `DRY_RUN=0` applies).

## Web UI

Static landing page with copy-paste commands: `web/README.md` (`cd web && npm run dev`).
