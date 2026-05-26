# Search profile catalog

Shipped YAML personas under `config/search_profiles/`. Field definitions and Python API: `docs/SEARCH_PROFILE.md`.

## Pick a profile

| Profile id | When to use |
|------------|-------------|
| `wei-atlanta-qa-2026` | **Default for this repo operator**; Atlanta hybrid allowlist, tracks A/B/C, operator-tuned tier-7 floor. |
| `single-us-metro-2026` | Single person, typical US metro COL; starting point for most searchers. |
| `single-low-col-2026` | Lower COL markets (midwest, smaller southern metros, rural). |
| `single-high-col-2026` | SF Bay, NYC, Seattle, LA, Boston-Cambridge, DC. |
| `couple-no-deps-medium-col-2026` | Two earners, no dependents; your income is one of two salaries. |
| `sole-earner-with-deps-medium-col-2026` | Sole earner with dependent(s); higher floors for healthcare, childcare, housing. |

Manifest: `config/profile_catalog.yaml` (`active_default: wei-atlanta-qa-2026`).

Each YAML may include optional `fit_calibration_profile: <stem>`: a **data-only** link to `fit/config/profiles/<stem>.json`. JobSpy code must not import `fit/`.

## Comp numbers (fit parity)

`comp.tier_floors` for tiers **5** and **7** are copied from fit JSON `comp_floor_usd` (same source as the calculator personas).

`comp.min_ceiling_usd` is the **scraper** `comp_ok` threshold (JobSpy `min_amount`/`max_amount` gate). It is set to **tier-5 floor minus $15,000**, matching the Wei Atlanta profile pattern (145k tier-5 → 130k scraper ceiling). This is intentionally below the tier-5 manual offer gate so the scraper surfaces borderline listings for triage.

| Profile | tier-5 floor | tier-7 floor | min_ceiling_usd |
|---------|-------------|-------------|-----------------|
| single-low-col-2026 | 105,000 | 125,000 | 90,000 |
| single-us-metro-2026 | 145,000 | 170,000 | 130,000 |
| single-high-col-2026 | 190,000 | 225,000 | 175,000 |
| couple-no-deps-medium-col-2026 | 125,000 | 145,000 | 110,000 |
| sole-earner-with-deps-medium-col-2026 | 190,000 | 220,000 | 175,000 |
| wei-atlanta-qa-2026 | 145,000 | 150,000* | 130,000 |

\* Wei tier-7 is operator-tuned below fit `single-us-metro-2026` (170,000).

Copy a profile to a gitignored local file and edit `owner`, `home_metro`, and comp if your situation differs.

## Run scrape + triage

```bash
cd ~/Projects/sisyphus
export JOB_SEARCH_PROFILE=config/search_profiles/single-high-col-2026.yaml

python3 scripts/run_search.py
python3 scripts/triage_jobspy_csv.py --latest --profile "$JOB_SEARCH_PROFILE"
```

Optional wrapper:

```bash
python3 scripts/triage_with_profile.py --latest --profile "$JOB_SEARCH_PROFILE"
```

Personal copy:

```bash
cp config/search_profiles/single-us-metro-2026.yaml config/search_profile.local.yaml
export JOB_SEARCH_PROFILE=config/search_profile.local.yaml
```

`config/search_profile.example.yaml` symlinks to `config/search_profiles/single-us-metro-2026.yaml`. The operator QA profile is `config/search_profiles/wei-atlanta-qa-2026.yaml`.

## Verify

```bash
./scripts/verify_search_profiles.sh
```
