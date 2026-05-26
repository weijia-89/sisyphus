# Architecture

sisyphus is one public repository with two independent Python stacks. They never import each other. Operators link them through YAML and JSON data files only.

## Two stacks

| Stack | Path | Dependencies | Must not import |
|-------|------|--------------|-----------------|
| JobSpy scrape and triage | `scripts/`, `lib/` | `requirements.txt` (python-jobspy, pandas, requests, …) | anything under `fit/` |
| Job-fit calculator | `fit/` | stdlib only (Python 3.10+) | `lib/`, `scripts/`, pandas, jobspy |

The JobSpy stack wraps [python-jobspy](https://github.com/speedyapply/JobSpy) on PyPI. It adds multi-board orchestration, filter pipelines, prescreen columns on scrape output, YAML search profiles, and CSV triage. The fit stack is the former **corpofit** calculator under `fit/` with a repo-root `./corpofit` shim. The public [corpofit](https://github.com/weijia-89/corpofit) repo has an archive pointer README.

## Data-only link

`config/profile_catalog.yaml` pairs each search profile id with a fit calibration JSON stem and a short description. JobSpy code reads the active YAML via `JOB_SEARCH_PROFILE`. The calculator reads `fit/config/profiles/<stem>.json` or a local `fit/config/calibration.json`.

Optional field `fit_calibration_profile` on a search YAML mirrors the catalog entry. Duplicated comp floor numbers in YAML vs JSON are intentional (same persona, two surfaces).

No `import` between stacks. Changing scrape preferences does not require editing fit Python, and scoring a role does not load pandas or jobspy.

## Repository layout

```
sisyphus/
  README.md
  corpofit                    # shim → fit/scripts/corpofit.py
  scripts/                    # run_search, triage, prescreen, index helpers
  lib/                        # search_profile, domain_inference
  config/
    search_profiles/          # persona YAML files
    profile_catalog.yaml      # search ↔ fit manifest
    skip_companies.txt
    ils_overrides.json
  fit/
    scripts/corpofit.py
    config/profiles/*.json
    docs/
  data/jobspy_results/        # gitignored CSV output (.gitkeep in repo)
  docs/                       # architecture, operations, profile reference
  web/                        # static landing UI (optional)
```

## Scoring layers (do not conflate)

| Layer | Where | Scale | Use |
|-------|-------|-------|-----|
| Prescreen | `prescreen.priority` in scrape CSV | HIGH / MOD / LOW / ? | Sort rows; not an apply gate |
| Triage ILS | `scripts/triage_jobspy_csv.py` → `ils_estimate` | 0–100 estimate | apply/skip post-gate (~45 floor from profile) |
| Fit score | `./corpofit` | 0–100 + tier gates | Manual role-fit after triage pass |

Prescreen and triage run on every daily scrape. The fit calculator is interactive or CLI-driven on roles you choose to score.

## License split

- JobSpy stack (`scripts/`, `lib/`, root orchestration): MIT (see repo `LICENSE`)
- Fit calculator (`fit/`): PolyForm Noncommercial 1.0.0 + Iron Law Addendum

## Further reading

- Daily commands and script map: `docs/OPERATIONS.md`
- Profile fields: `docs/SEARCH_PROFILE.md`
- Profile catalog table: `docs/SEARCH_PROFILES.md`
- Upstream vs this repo: `DIFFERENCES-vs-python-jobspy.md`
