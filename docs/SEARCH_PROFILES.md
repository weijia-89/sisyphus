# Search profile catalog

Multiple YAML profiles under `config/search_profiles/` describe remote/work-mode rules, home metro, comp floors, ILS triage floors, enabled scraper tracks, and referral tiers. **Triage** and **scraper** read the active file via `lib/search_profile.py` — no Python edits for preference changes.

See also `docs/SEARCH_PROFILE.md` for field reference and Python API.

## Pick a profile

| Profile id | When to use |
|------------|-------------|
| `wei-atlanta-qa-2026` | **Default for this repo operator** — Atlanta hybrid allowlist, tracks A/B/C, Wei-tuned tier-7 floor. |
| `single-us-metro-2026` | Single person, typical US metro COL; starting point for most searchers. |
| `single-low-col-2026` | Lower COL markets (midwest, smaller southern metros, rural). |
| `single-high-col-2026` | SF Bay, NYC, Seattle, LA, Boston-Cambridge, DC. |
| `couple-no-deps-medium-col-2026` | Two earners, no dependents; your income is one of two salaries. |
| `sole-earner-with-deps-medium-col-2026` | Sole earner with dependent(s); higher floors for healthcare, childcare, housing. |

Manifest: `config/profile_catalog.yaml` (`active_default: wei-atlanta-qa-2026`).

Each YAML may include optional `fit_calibration_profile: <stem>` — a **data-only** link to `fit/config/profiles/<stem>.json` after the corpofit merge PR lands. JobSpy code must not import `fit/`.

## Comp numbers (corpofit parity)

`comp.tier_floors` for tiers **5** and **7** are copied from corpofit JSON `comp_floor_usd` (same source as the fit calculator personas).

`comp.min_ceiling_usd` is the **scraper** `comp_ok` threshold (JobSpy `min_amount`/`max_amount` gate). It is set to **tier-5 floor minus $15,000**, matching the Wei Atlanta profile pattern (145k tier-5 → 130k scraper ceiling). This is intentionally below the tier-5 manual offer gate so the scraper surfaces borderline listings for triage.

| Profile | tier-5 floor | tier-7 floor | min_ceiling_usd |
|---------|-------------|-------------|-----------------|
| single-low-col-2026 | 105,000 | 125,000 | 90,000 |
| single-us-metro-2026 | 145,000 | 170,000 | 130,000 |
| single-high-col-2026 | 190,000 | 225,000 | 175,000 |
| couple-no-deps-medium-col-2026 | 125,000 | 145,000 | 110,000 |
| sole-earner-with-deps-medium-col-2026 | 190,000 | 220,000 | 175,000 |
| wei-atlanta-qa-2026 | 145,000 | 150,000* | 130,000 |

\* Wei tier-7 is operator-tuned below corpofit `single-us-metro-2026` (170,000).

Copy a profile to a gitignored local file and edit `owner`, `home_metro`, and comp if your situation differs.

## Run scrape + triage

```bash
cd ~/Projects/sisyphus
export JOB_SEARCH_PROFILE=config/search_profiles/single-high-col-2026.yaml

python3 scripts/run_search.py
python3 scripts/triage_jobspy_csv.py --latest --profile "$JOB_SEARCH_PROFILE"
```

Optional wrapper (profile → triage env/flags):

```bash
python3 scripts/triage_with_profile.py --latest --profile "$JOB_SEARCH_PROFILE"
```

For a personal copy:

```bash
cp config/search_profiles/single-us-metro-2026.yaml config/search_profile.local.yaml
# edit owner, home_metro.place_names, comp
export JOB_SEARCH_PROFILE=config/search_profile.local.yaml
```

`config/search_profile.example.yaml` is a symlink to `config/search_profiles/single-us-metro-2026.yaml`. The former monolithic example now lives at `config/search_profiles/wei-atlanta-qa-2026.yaml`.

## Verify

```bash
python3 -c "
from pathlib import Path
import sys
sys.path.insert(0, '.')
from lib.search_profile import load_profile
for p in Path('config/search_profiles').glob('*.yaml'):
    load_profile(str(p))
    print('ok', p.name)
"
test -f config/profile_catalog.yaml
test -f docs/SEARCH_PROFILES.md
```
