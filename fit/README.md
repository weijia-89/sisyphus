# Job-fit calculator (formerly corpofit brand)

Stdlib-only Python job-fit calculator. Scores opportunities on seven dimensions, personal preferences, and tier-specific compensation floors. No external packages, no network calls, no telemetry.

## Quick start

From the sisyphus repo root:

```bash
./corpofit --interactive
```

Or invoke the script directly:

```bash
python3 fit/scripts/corpofit.py --interactive
```

Non-interactive scoring:

```bash
./corpofit \
  --tier 4 \
  --psych-safety 10 --wlb 12 --manager 11 --security 10 \
  --growth 7 --comp-sustain 2 \
  --comp 165000 --company "Acme Corp"
```

## Layout

```
fit/scripts/corpofit.py       # main calculator CLI
fit/scripts/elicit.py         # structured elicitation flows
fit/scripts/repo_archive.py   # archive encode/decode utilities
fit/config/profiles/          # shipped calibration personas
fit/config/calibration.example.json
fit/tests/                    # stdlib unittest suite
fit/docs/                     # getting-started, dimensions, worked example
```

Calibration profiles live in `fit/config/profiles/`. Copy one to `fit/config/calibration.json` (gitignored) or pass `--config`.

Local score logs and elicitation sessions go under `fit/localonly/` (gitignored).

## Documentation

- [Getting started](docs/getting-started.md)
- [Role-fit dimensions](docs/role-fit-dimensions.md)
- [Worked example](docs/worked-example.md)

## Stack isolation

This calculator is **stdlib-only** and must not import anything from the JobSpy stack (`lib/`, `scripts/run_search.py`, pandas, jobspy). Link stacks via data files only — see `docs/ARCHITECTURE.md` at the repo root.

## License

PolyForm Noncommercial 1.0.0 + Iron Law Addendum — see repo-root `LICENSE` (fit calculator section).
