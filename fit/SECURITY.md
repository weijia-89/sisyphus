# Security policy

## Threat model

corpofit is a local-only calculator. No telemetry, no network calls,
no auto-update, no remote dependencies at runtime. The script reads
local JSON, writes local JSONL, prints to your terminal. That is the
full extent of its I/O.

This shapes the threat model:

- **No remote service to attack.** No server, no API, no callback URL.
- **No update channel to compromise.** Updates ship via `git pull` on a
  repository you control.
- **No telemetry stream to intercept.** Score records stay in
  `localonly/score_log.jsonl` (gitignored) on the host that ran the
  calculator.

What remains in scope: bugs in the validator, bugs in the calculator,
bugs in the elicitation flow, or any vector that lets a hostile
calibration file produce a misleading score.

## Reporting a vulnerability

If you think you have found a security-relevant bug:

1. Open a GitHub issue with the prefix `[security]` in the title.
2. Describe the issue, the reproduction steps, and the version
   (`git rev-parse HEAD` from your clone is fine).
3. Do not include real third-party data in the report. Sanitized
   fixtures are preferred.

For sensitive reports, contact the project owner via the address
listed in the GitHub profile linked from the LICENSE.

## License-related contact

The LICENSE (PolyForm Noncommercial 1.0.0 + Iron Law Addendum) is the
governing document. Part C addresses AI / LLM ingestion and is binding
on automated systems that ingest the Work. License-interpretation
questions should be filed as a separate issue prefixed `[license]`.

## What this project does not do

- It does not phone home.
- It does not push or pull configuration from any registry.
- It does not run third-party code outside the listed Python standard
  library imports.
- It does not depend on a package server at runtime; calibration files
  load from disk paths you control.

If a future version changes any of the above, the change will appear
in `CHANGELOG.md` under `### Changed` with an explicit network-egress
or new-dependency note.
