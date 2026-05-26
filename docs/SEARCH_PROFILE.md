# Search profile

Field reference for one YAML search profile. For the catalog of shipped personas and comp tables, see `docs/SEARCH_PROFILES.md`.

## Quick start

```bash
cd ~/Projects/sisyphus
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp config/search_profile.template.yaml config/search_profile.local.yaml
# edit owner, home_metro, comp, paths

export JOB_SEARCH_PROFILE=config/search_profile.local.yaml
python3 -c "from lib.search_profile import load_profile; load_profile('$JOB_SEARCH_PROFILE')"
```

`config/search_profile.local.yaml` is **gitignored**. Never commit it (may contain personal paths).

## Files

| File | Purpose |
|------|---------|
| `config/search_profile.schema.json` | JSON Schema draft 2020-12 validation |
| `config/search_profile.template.yaml` | Anonymized starter with comments |
| `config/search_profile.example.yaml` | Symlink to `search_profiles/single-us-metro-2026.yaml` |
| `config/search_profiles/` | Catalog personas; see `profile_catalog.yaml` and `docs/SEARCH_PROFILES.md` |
| `config/profile_catalog.yaml` | Manifest + `active_default` (`wei-atlanta-qa-2026`) |
| `config/search_profiles/wei-atlanta-qa-2026.yaml` | Operator QA profile (full ATL allowlist, tracks A/B/C) |
| `config/search_profile.local.yaml` | Your copy (create locally) |
| `lib/search_profile.py` | `load_profile()` + helpers |

## Environment

| Variable | Role |
|----------|------|
| `JOB_SEARCH_PROFILE` | Path to active profile YAML (preferred) |
| `TRIAGE_REFERRAL_STATUS` | Set by `scripts/triage_with_profile.py` for wrappers |
| `TRIAGE_ILS_FLOOR` | Cold ILS floor from profile (wrapper convenience) |

## Field reference

### `remote_preference`

| Value | Behavior |
|-------|----------|
| `fully_remote` | US employee remote only; hybrid/onsite dropped |
| `hybrid_home_metro` | US remote **or** hybrid/onsite when JD/location matches `home_metro.place_names` |
| `any_us_remote` | Broad US-remote column pass; does not enforce home-metro hybrid allowlist |

For a fixed home city, use `hybrid_home_metro`. `any_us_remote` can surface hybrid roles outside your metro that stricter work-mode rules would block before ILS work.

### `home_metro`

- `zip_anchor` - commute anchor ZIP (documentation; enforcement uses `place_names`)
- `place_names` - substring allowlist for hybrid/onsite matching

### `comp`

- `min_ceiling_usd` - scraper `comp_ok` threshold (default example: 130000)
- `tier_floors` - optional T5/T7 offer gates for manual review after triage

### `ils`

- `cold_floor` - triage post-gate skip (default 45)
- `referral_warm_delta` / `referral_strong_delta` - relative to cold (default −10 / −20)

### `referrals.status_file`

Plain text: `company_substring,status` per line (`cold` | `warm` | `strong`). Copy the format from `config/search_profile.template.yaml` comments or maintain a gitignored local file.

### `tracks.enable`

Letters `A` `B` `C` `G` `R` `GH` `L` `AS`; see `docs/OPERATIONS.md` (scraper tracks).

### `output.results_dir`

Directory for `jobspy_results_YYYYMMDD.csv` and triage exports (default `./data/jobspy_results`).

## Python API

```python
from lib.search_profile import (
    load_profile,
    remote_policy,
    allowed_hybrid_places,
    ils_floor,
    referral_path,
)

profile = load_profile("config/search_profile.local.yaml")
remote_policy(profile)          # work-mode summary dict
allowed_hybrid_places(profile)  # list of place names
ils_floor(profile, "warm")      # tiered floor
referral_path(profile)          # absolute path
```

## Scrape and triage integration

`scripts/run_search.py` reads the profile for `comp.min_ceiling_usd`, `tracks.enable`, `home_metro`, `remote_preference`, and `output.results_dir`.

`scripts/triage_jobspy_csv.py` accepts `--profile` or `JOB_SEARCH_PROFILE` for ILS floors, referral file path, and results directory.

```bash
export JOB_SEARCH_PROFILE=config/search_profile.local.yaml
python3 scripts/run_search.py
python3 scripts/triage_jobspy_csv.py --latest --profile "$JOB_SEARCH_PROFILE"
```

Wrapper:

```bash
python3 scripts/triage_with_profile.py --latest --profile "$JOB_SEARCH_PROFILE"
```

## Do not store in profile

- API keys, passwords, OAuth tokens
- Employer secrets or private assessment notes

Use gitignored local paths only for `search_profile.local.yaml` and optional `referral_status.local.txt`.

## Verify

```bash
./scripts/verify_search_profiles.sh
```
