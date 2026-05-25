# Search profile

One YAML file describes remote/work-mode rules, home metro, comp floors, ILS triage floors, enabled scraper tracks, and referral tiers. **Triage** and **scraper** (lane 3) read it via `lib/search_profile.py` — no Python edits for preference changes.

## Quick start

```bash
cd ~/Projects/sisyphus
python3 -m venv .venv && source .venv/bin/activate
pip install pyyaml jsonschema

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
| `config/search_profile.example.yaml` | Symlink to `search_profiles/single-us-metro-2026.yaml` (generic metro starter) |
| `config/search_profiles/` | Catalog personas — see `profile_catalog.yaml` and `docs/SEARCH_PROFILES.md` |
| `config/profile_catalog.yaml` | Manifest + `active_default` (`wei-atlanta-qa-2026`) |
| `config/search_profiles/wei-atlanta-qa-2026.yaml` | Wei operator QA (full ATL allowlist, tracks A/B/C) |
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
| `hybrid_home_metro` | Remote US **or** hybrid/onsite when JD/location matches `home_metro.place_names` |
| `any_us_remote` | Broad US-remote column pass; **does not** enforce home-metro hybrid allowlist |

For a fixed home city (e.g. Atlanta), use `hybrid_home_metro`. That matches **IL-12 L-0** in `toren/applications/_network_iron_laws.md`: remote US, hub-list remote including your city, or hybrid in your metro only. `any_us_remote` can surface hybrid-in-Irvine roles that IL-12 would block before ILS/JFS work.

### `home_metro`

- `zip_anchor` — commute anchor ZIP (documentation; enforcement uses `place_names`)
- `place_names` — substring allowlist aligned with `run_search_locally.passes_wei_geo_and_work_mode`

### `comp`

- `min_ceiling_usd` — scraper `comp_ok` threshold (default Wei: 130000)
- `tier_floors` — optional T5/T7 offer gates for manual review after triage

### `ils`

- `cold_floor` — triage post-gate skip (default 45)
- `referral_warm_delta` / `referral_strong_delta` — relative to cold (default −10 / −20)

### `referrals.status_file`

Plain text: `company_substring,status` per line (`cold` | `warm` | `strong`). See `~/Projects/toren/applications/referral_status.txt` for format.

### `tracks.enable`

Letters `A` `B` `C` `G` `R` `GH` `L` `AS` — see `docs/JOBSPY_INVENTORY.md` § track legend.

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

Import works with **only** sisyphus on `PYTHONPATH` (no toren).

## Triage integration

### Lane 2 (now): wrapper

```bash
export JOB_SEARCH_PROFILE=config/search_profile.local.yaml
python3 scripts/triage_with_profile.py --latest
python3 scripts/triage_with_profile.py --dry-run --profile config/search_profiles/wei-atlanta-qa-2026.yaml
```

Delegates to `~/Projects/toren/scripts/triage_jobspy_csv.py` with `--ils-floor` from profile until lane 3 lands.

### Lane 3 (planned): native `--profile`

Lane 3 copies `triage_jobspy_csv.py` into `scripts/triage_jobspy_csv.py` and adds:

```bash
python3 scripts/triage_jobspy_csv.py --latest --profile "$JOB_SEARCH_PROFILE"
```

The ported script should:

1. Call `load_profile(args.profile or os.environ["JOB_SEARCH_PROFILE"])`
2. Pass `ils.cold_floor` and referral deltas into post-gates
3. Load `referrals.status_file` instead of hardcoded toren path
4. Use `output.results_dir` for `--latest` when not overridden
5. Apply `remote_preference` + `home_metro.place_names` in arrangement/geo gates (replacing hardcoded ATL regex when profile-driven)

Until lane 3 ships, geo/remote gates in delegated toren triage remain ATL-hardcoded; profile `remote_preference` documents intent and validates early.

## Scraper integration (lane 3)

`scripts/run_search.py` (port of `run_search_locally.py`) should read the same profile for:

- `comp.min_ceiling_usd`
- `tracks.enable`
- `home_metro` + `remote_preference` in filter pipeline
- `output.results_dir`

## Do not store in profile

- API keys, passwords, OAuth tokens
- Employer secrets or private assessment notes

Use gitignored local paths only for `search_profile.local.yaml` and optional `referral_status.local.txt`.

## Verify

```bash
./scripts/verify_search_profiles.sh
test -f config/search_profile.schema.json
test -f docs/SEARCH_PROFILE.md
```
