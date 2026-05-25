# corpofit → sisyphus merge (private unified repo)

**Goal:** One private repo **`weijia-89/sisyphus`** = JobSpy scrape/triage **plus** the stdlib job-fit calculator (formerly **corpofit**). The public name **corpofit** retires; GitHub Pages / old clone URLs get a redirect README on the archived repo.

## Two stacks, zero Python cross-imports

| Stack | Path | Deps | Must not import |
|-------|------|------|-----------------|
| **JobSpy** | `scripts/`, `lib/search_profile.py`, `config/search_profiles/` | `requirements.txt` (python-jobspy, pandas, …) | anything under `fit/` |
| **Fit calculator** | `fit/scripts/corpofit.py`, `fit/tests/`, `fit/config/profiles/` | **stdlib only** | `lib/`, `scripts/run_search.py`, pandas, jobspy |

Link stacks via **data only**:

<!-- sdk-review F3: profile_catalog.yaml is SDK lane 2, not present in lane-1 merge -->
- `config/profile_catalog.yaml` (SDK lane 2 — not in lane-1 merge) — pairs a search profile id with a fit calibration JSON id + human description
- Operator passes `JOB_SEARCH_PROFILE=config/search_profiles/<id>.yaml` for scrape/triage
<!-- sdk-review F5: repo-root ./corpofit shim, not ./fit/corpofit -->
- Operator passes `fit/config/profiles/<id>.json` (or `--config`) for `./corpofit` scoring from repo root

No `import` between stacks. Duplicated comp floor numbers in YAML vs JSON are intentional (generated from same source in SDK lane 2).

## Target layout (after merge)

```
sisyphus/
  README.md                    # unified; private repo
  LICENSE                      # PolyForm-NC + Iron Law (corpofit) + JobSpy MIT addendum — reconcile in merge PR
  requirements.txt             # JobSpy only
  corpofit                     # shim → fit/scripts/corpofit.py (backward compat for docs/CLI)
  scripts/                     # JobSpy (unchanged paths)
  lib/
  config/
    search_profiles/           # multiple YAML (lane 2)
    profile_catalog.yaml       # manifest linking search ↔ fit profiles (lane 2)
    search_profile.schema.json
    skip_companies.txt
  fit/
    README.md
    scripts/corpofit.py
    scripts/elicit.py
    scripts/repo_archive.py
    config/profiles/*.json     # ported from corpofit
    tests/
    docs/                      # getting-started, role-fit-dimensions (subset)
  docs/
    JOBSPY_INVENTORY.md
    SEARCH_PROFILES.md         # catalog of YAML profiles (lane 2)
    CORPORFIT_MERGE.md         # this file
    MIGRATION_TASK.md
  data/jobspy_results/
```

## Search profiles (from corpofit household types)

Port **five** corpofit calibration personas into **search_profile** YAML:

| Fit profile (JSON) | Search YAML (proposed) | comp emphasis |
|--------------------|------------------------|---------------|
| `single-low-col-2026` | `search_profiles/single-low-col-2026.yaml` | lower `min_ceiling_usd`, tier_floors |
| `single-us-metro-2026` | `search_profiles/single-us-metro-2026.yaml` | default metro (Atlanta example in place_names) |
| `single-high-col-2026` | `search_profiles/single-high-col-2026.yaml` | high COL floors |
| `couple-no-deps-medium-col-2026` | `search_profiles/couple-no-deps-medium-col-2026.yaml` | medium COL |
| `sole-earner-with-deps-medium-col-2026` | `search_profiles/sole-earner-with-deps-medium-col-2026.yaml` | medium COL, higher floors |

Each YAML includes optional field `fit_calibration_profile: <json basename>` for catalog parity.

Wei’s active Atlanta QA profile becomes `search_profiles/wei-atlanta-qa-2026.yaml` (rename from example) and catalog entry `active_default: true` in `profile_catalog.yaml`.

## GitHub

| Repo | After merge |
|------|-------------|
| `weijia-89/sisyphus` | **Private**, canonical, branch protection |
| `weijia-89/corpofit` | Archive or top README: “Moved into private sisyphus — fit calculator lives under `fit/`” |
| `weijia-89/career-helper` | Archive banner (JobSpy only) — see `MIGRATION_TASK.md` |

Pages: corpofit Pages SPA may stay on archived repo temporarily; optional later lane ports `fit/docs/` assets only if needed.

## SDK parallel lanes

See `~/Projects/cursor-sdk-playground/prompts/sdk-wave6h-kickoffs.txt`:

1. `sisyphus_merge_corpofit.sh` — port `fit/` tree + shim + LICENSE/README
2. `sisyphus_search_profiles_corpofit.sh` — YAML family + catalog (parallel branch)
3. `sisyphus_github_unify.sh` — private sisyphus + corpofit archive README

Merge PRs 1+2 before or with 3; resolve README/LICENSE conflicts once.
