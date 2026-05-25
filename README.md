# sisyphus

Private personal job-search workspace (Wei Jia). **GitHub:** `weijia-89/sisyphus` (private). Two independent Python stacks share one repo but **never cross-import**:

| Stack | Path | Dependencies |
|-------|------|--------------|
| **JobSpy scrape/triage** | `scripts/`, `lib/` | `requirements.txt` (python-jobspy, pandas, …) |
| **Job-fit calculator** | `fit/` | **stdlib only** |

Link stacks via **data only** — SDK lane 2 will add `config/profile_catalog.yaml` to pair a search profile with a fit calibration JSON (see `docs/CORPORFIT_MERGE.md`; catalog not in lane-1 merge).

Replaces legacy **`weijia-89/career-helper`** for scrape/triage. The former **corpofit** brand lives under `fit/`; application tracking stays in a separate local career-ops workspace — see `docs/MIGRATION_TASK.md`.

## JobSpy stack — setup

```bash
cd ~/Projects/sisyphus
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config/search_profile.template.yaml config/search_profile.local.yaml
# edit profile (owner, home_metro, comp, tracks) — local file is gitignored
export JOB_SEARCH_PROFILE=config/search_profile.local.yaml
```

Validate profile:

```bash
python3 -c "from lib.search_profile import load_profile; load_profile('$JOB_SEARCH_PROFILE')"
```

## JobSpy stack — daily commands

```bash
cd ~/Projects/sisyphus
source .venv/bin/activate
export JOB_SEARCH_PROFILE=config/search_profile.local.yaml
python3 scripts/run_search.py
python3 scripts/triage_jobspy_csv.py --latest --profile "$JOB_SEARCH_PROFILE"
```

Outputs land in `data/jobspy_results/` (gitignored):

- `jobspy_results_YYYYMMDD.csv` — full daily scrape after filters + prescreen
- `jobspy_results_YYYYMMDD_new.csv` — URLs not seen in prior full exports
- `yield_log.csv`, `yield_funnel.csv`, `search_errors.log`

Optional env overrides:

| Variable | Role |
|----------|------|
| `JOB_SEARCH_RESULTS_DIR` | Override CSV output directory |
| `JOB_SKIP_COMPANIES_FILE` | Override skip list path |
| `JOB_APPLICATION_INDEX` | Optional local HTML index path for auto-skip merge |

## Fit calculator stack

Stdlib-only; no venv required beyond Python 3.10+:

```bash
./corpofit --interactive
# or: python3 fit/scripts/corpofit.py --interactive
```

See `fit/README.md` and `fit/docs/getting-started.md`.

## Layout

```
corpofit                       # shim → fit/scripts/corpofit.py
scripts/run_search.py          # scraper + filter pipeline
scripts/triage_jobspy_csv.py   # CSV triage + ILS post-gates
scripts/prescreen.py           # prescreen columns
scripts/index_companies.py     # application index parser
scripts/triage_with_profile.py # profile wrapper → native triage
lib/search_profile.py          # YAML profile loader
lib/domain_inference.py        # triage domain/tier heuristics
config/search_profile.*        # profile schema, template, example
config/skip_companies.txt      # company skip slugs
config/ils_overrides.json      # per-company ILS overrides for triage
fit/                           # stdlib job-fit calculator (see fit/README.md)
data/jobspy_results/           # gitignored CSV output (.gitkeep only in repo)
```

## Docs

- `docs/JOBSPY_INVENTORY.md` — script map and daily flow
- `docs/SEARCH_PROFILE.md` — profile fields
- `docs/CORPORFIT_MERGE.md` — two-stack merge plan
- `docs/MIGRATION_TASK.md` — private publish + replace career-helper
- `docs/BRANCH_PROTECTION.md` — lock down `main`
- `DIFFERENCES-vs-python-jobspy.md` — upstream vs this repo

## License

Dual-licensed repo — see `LICENSE`:

- **JobSpy stack** (`scripts/`, `lib/`, …): MIT
- **Fit calculator** (`fit/`): PolyForm Noncommercial 1.0.0 + Iron Law Addendum
