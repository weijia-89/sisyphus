# sisyphus

![Sculpture of Sisyphus pushing a boulder in an outdoor graveyard setting](docs/assets/sisyphus-hero.jpg)

README hero: operator-provided photograph, vendored under `docs/assets/` (see `docs/assets/IMAGE_ATTRIBUTION.md`). Myth background: [Sisyphus (Greek mythology)](https://www.britannica.com/topic/Sisyphus-Greek-mythology).

Job-search tooling built around [python-jobspy](https://github.com/speedyapply/JobSpy). This repo adds multi-board scrape orchestration plus YAML search profiles with prescreen columns. A triage CLI ranks the CSV rows. A stdlib-only job-fit calculator lives under `fit/`. The tree is a pipeline and scoring layer on top of the PyPI package, not a fork of upstream JobSpy. Board and scraper drift is ongoing; it's unclear how long current filters stay valid without a refresh or a python-jobspy bump.

**Repository:** [github.com/weijia-89/sisyphus](https://github.com/weijia-89/sisyphus) (public)

Two Python stacks live in one tree and **never import each other**:

| Stack | Path | Dependencies |
|-------|------|--------------|
| JobSpy scrape and triage | `scripts/`, `lib/` | `requirements.txt` (python-jobspy, pandas, …) |
| Job-fit calculator | `fit/` | stdlib only (Python 3.10+) |

The stacks connect through **data only**: `config/profile_catalog.yaml` maps a search profile to a fit calibration JSON. See `docs/CORPORFIT_MERGE.md` for how the former corpofit calculator landed under `fit/`.

## Quick start (JobSpy stack)

```bash
git clone https://github.com/weijia-89/sisyphus.git
cd sisyphus
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config/search_profile.template.yaml config/search_profile.local.yaml
# edit profile (owner, home_metro, comp, tracks); keep the local file out of git
export JOB_SEARCH_PROFILE=config/search_profile.local.yaml
```

Validate the profile:

```bash
python3 -c "from lib.search_profile import load_profile; load_profile('$JOB_SEARCH_PROFILE')"
```

## Daily workflow

```bash
source .venv/bin/activate
export JOB_SEARCH_PROFILE=config/search_profile.local.yaml
python3 scripts/run_search.py
python3 scripts/triage_jobspy_csv.py --latest --profile "$JOB_SEARCH_PROFILE"
```

CSV output goes to `data/jobspy_results/` (gitignored):

- `jobspy_results_YYYYMMDD.csv`: full daily scrape after filters and prescreen
- `jobspy_results_YYYYMMDD_new.csv`: URLs not seen in prior full exports
- `yield_log.csv`, `yield_funnel.csv`, `search_errors.log`

Optional environment overrides:

| Variable | Role |
|----------|------|
| `JOB_SEARCH_RESULTS_DIR` | Override CSV output directory |
| `JOB_SKIP_COMPANIES_FILE` | Override skip list path |
| `JOB_APPLICATION_INDEX` | Optional local HTML index path for auto-skip merge |

## Fit calculator

No extra packages beyond Python 3.10+:

```bash
./corpofit --interactive
# or: python3 fit/scripts/corpofit.py --interactive
```

Details: `fit/README.md`, `fit/docs/getting-started.md`.

## Layout

```
corpofit                       # repo-root executable shim → fit/scripts/corpofit.py
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
fit/                           # stdlib job-fit calculator
data/jobspy_results/           # gitignored CSV output (.gitkeep in repo)
```

## Documentation

- `docs/JOBSPY_INVENTORY.md`: script map and daily flow
- `docs/SEARCH_PROFILE.md`: profile fields
- `docs/CORPORFIT_MERGE.md`: two-stack architecture
- `docs/BRANCH_PROTECTION.md`: `main` branch policy
- `DIFFERENCES-vs-python-jobspy.md`: upstream vs this repo

## License

Dual-licensed; see `LICENSE`:

- **JobSpy stack** (`scripts/`, `lib/`, …): MIT
- **Fit calculator** (`fit/`): PolyForm Noncommercial 1.0.0 + Iron Law Addendum
