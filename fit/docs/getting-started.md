# Getting started

corpofit is a stdlib-only Python tool under `fit/` in the sisyphus repo. Run it from the repo root via `./corpofit`, not as a standalone corpofit clone. No external dependencies. Tested on Python 3.10+.

## Installation

From a clone of the sisyphus repo:

```bash
git clone git@github.com:weijia-89/sisyphus.git
cd sisyphus
python3 -m unittest discover -s fit/tests -v
```

If all tests pass, the install is good.

## First run

From the **repo root**, interactive mode walks you through every input with prompts and inline rubric reminders:

```bash
./corpofit --interactive
```

Or invoke the script directly:

```bash
python3 fit/scripts/corpofit.py --interactive
```

Non-interactive scoring requires every input on the command line:

```bash
./corpofit \
  --tier 4 \
  --c1 10 --c2 12 --c3 11 --c4 10 --c6 7 --c7 2 \
  --comp 165000 \
  --company "Acme Corp"
```

If you forget a flag, the CLI tells you which one is missing.

## Exit codes

- 0: APPLY decision returned cleanly (and score logged when logging is enabled).
- 2: input validation failed (bad tier, bad dim score, malformed calibration), missing `--company` when logging, or log append failed.
- 3: Gate 2 (compensation floor) triggered DO_NOT_APPLY.
- 4: Gate 1 (tier 9 or 10) triggered DO_NOT_APPLY.
- 130: interactive session interrupted by Ctrl-C.

The non-zero exit codes are useful for shell scripting: chain corpofit into a pipeline and short-circuit on hard blocks.

## Calibration profiles

Five profiles ship in `fit/config/profiles/`:

- `single-low-col-2026.json`: single earner, low cost-of-living metro.
- `single-us-metro-2026.json`: single earner, median US metro. This is the default copied into `fit/config/calibration.example.json`.
- `single-high-col-2026.json`: single earner, high cost-of-living metro.
- `couple-no-deps-medium-col-2026.json`: dual-earner couple, no dependents.
- `sole-earner-with-deps-medium-col-2026.json`: sole earner, dependents.

To use a non-default profile:

```bash
cp fit/config/profiles/single-high-col-2026.json fit/config/calibration.json
```

Or pass `--config` directly:

```bash
./corpofit --config fit/config/profiles/single-high-col-2026.json ...
```

The `fit/config/calibration.json` path is gitignored. Personal-fit calibrations stay local.

## The local log

Every run (unless `--no-log`) appends a JSON record to `fit/localonly/score_log.jsonl` (paths are relative to the repo root when you use `./corpofit`). The record includes the company name, your tier, the score, the band, and the `_revision` field (calibration revision hash; the CLI prints it as "revision") so you can audit which tuning was active for each entry.

The `fit/localonly/` directory is gitignored. Records never leave the machine.

To review your log:

```bash
cat fit/localonly/score_log.jsonl | python3 -m json.tool
```

## Elicitation flow

```bash
python3 fit/scripts/elicit.py values
python3 fit/scripts/elicit.py cover-letter
python3 fit/scripts/elicit.py resume
```

Each subcommand walks through a structured questionnaire and saves a session file under `fit/localonly/sessions/`. Future cover-letter or resume drafts can pull from the saved values to maintain a consistent voice.

See `fit/docs/role-fit-dimensions.md` for the seven scoring dimensions. The 1-10 industry-classification tier is user-supplied input. corpofit doesn't ship a public rubric; bring your own ethics framework and apply it consistently.
