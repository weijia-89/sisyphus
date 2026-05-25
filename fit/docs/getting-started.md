# Getting started

corpofit is a stdlib-only Python tool. No external dependencies. Tested on Python 3.10+.

## Installation

```bash
git clone https://github.com/weijia-89/corpofit.git
cd corpofit
python3 -m unittest discover tests -v
```

If all tests pass, the install is good.

## First run

Interactive mode walks you through every input with prompts and inline rubric reminders:

```bash
python3 scripts/corpofit.py --interactive
```

Non-interactive scoring requires every input on the command line:

```bash
python3 scripts/corpofit.py \
  --tier 4 \
  --c1 10 --c2 12 --c3 11 --c4 10 --c6 7 --c7 2 \
  --comp 165000 \
  --company "Acme Corp"
```

If you forget a flag, the CLI tells you which one is missing.

## Exit codes

- 0: APPLY decision returned cleanly.
- 2: input validation failed (bad tier, bad dim score, malformed calibration).
- 3: Gate 2 (compensation floor) triggered DO_NOT_APPLY.
- 4: Gate 1 (tier 9 or 10) triggered DO_NOT_APPLY.
- 130: interactive session interrupted by Ctrl-C.

The non-zero exit codes are useful for shell scripting: chain corpofit into a pipeline and short-circuit on hard blocks.

## Calibration profiles

Five profiles ship in `config/profiles/`:

- `single-low-COL-2026.json`: single earner, low cost-of-living metro.
- `single-us-metro-2026.json`: single earner, median US metro. This is the default copied into `config/calibration.example.json`.
- `single-high-COL-2026.json`: single earner, high cost-of-living metro.
- `couple-no-deps-medium-COL-2026.json`: dual-earner couple, no dependents.
- `sole-earner-with-deps-medium-COL-2026.json`: sole earner, dependents.

To use a non-default profile:

```bash
cp config/profiles/single-high-COL-2026.json config/calibration.json
```

Or pass `--config` directly:

```bash
python3 scripts/corpofit.py --config config/profiles/single-high-COL-2026.json ...
```

The `config/calibration.json` path is gitignored. Personal-fit calibrations stay local.

## The local log

Every run (unless `--no-log`) appends a JSON record to `localonly/score_log.jsonl`. The record includes the company name, your tier, the score, the band, and the calibration hash so you can audit which tuning was active for each entry.

The `localonly/` directory is gitignored. Records never leave the machine.

To review your log:

```bash
cat localonly/score_log.jsonl | python3 -m json.tool
```

## Elicitation flow

```bash
python3 scripts/elicit.py values
python3 scripts/elicit.py cover-letter
python3 scripts/elicit.py resume
```

Each subcommand walks through a structured questionnaire and saves a session file under `localonly/sessions/`. Future cover-letter or resume drafts can pull from the saved values to maintain a consistent voice.

See `docs/role-fit-dimensions.md` for the seven scoring dimensions. The 1-10 industry-classification tier is user-supplied input. corpofit doesn't ship a public rubric; bring your own ethics framework and apply it consistently.
