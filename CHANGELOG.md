# Changelog

This file tracks notable changes. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `web/`: minimal Vite static landing page for JobSpy and fit calculator entry commands.
- `docs/ARCHITECTURE.md`: canonical two-stack architecture and data-only link.
- `docs/OPERATIONS.md`: daily workflow, script map, outputs, and environment variables.

### Changed

- README hero image vendored under `docs/assets/sisyphus-hero.jpg` (operator photo; no CDN hotlink).
- Removed SDK review HTML comments from public markdown.
- Documentation deduped: overlapping intros split between `docs/SEARCH_PROFILE.md` and `docs/SEARCH_PROFILES.md` with cross-links.
- `DIFFERENCES-vs-python-jobspy.md`: trimmed legacy path migration table to a short historical port note.
- Root `README.md` points at canonical docs and Web UI subsection.

### Removed

- Internal operator docs: branch protection essay, migration checklist, JobSpy SDK inventory, corpofit merge plan (content merged into public docs above).

- Repository visibility set to **public** (`weijia-89/sisyphus`).
- Root `README.md` rewritten for public readers (setup, daily flow, layout, license split).

## [0.2.0] - 2026-05-25

### Added

- Search profile family and `config/profile_catalog.yaml` linking profiles to fit calibrations ([#4](https://github.com/weijia-89/sisyphus/pull/4)).
- corpofit job-fit calculator under `fit/` with repo-root `./corpofit` shim ([#2](https://github.com/weijia-89/sisyphus/pull/2), [#3](https://github.com/weijia-89/sisyphus/pull/3)).
- Branch protection apply script (`scripts/apply_branch_protection.sh`).
- SDK hardening on profile paths plus README merge resolution; review-driven fixes on merge branches.

### Changed

- Unified formerly separate corpofit calculator tree into `fit/`; the public corpofit repo now carries an archive pointer README.
- JobSpy orchestration remains in `scripts/` and `lib/` with MIT license; fit stack stays stdlib-only under PolyForm Noncommercial.

## [0.1.0] - 2026-05-18

### Added

- Initial private monorepo layout: JobSpy scrape/triage stack, `requirements.txt`, search profile template, prescreen and triage scripts.
- Search profile reference docs and `DIFFERENCES-vs-python-jobspy.md`.
