# JobSpy inventory (Wei monorepo)

Maintainer map of every JobSpy-related script, skill, SDK wrapper, and data path. **Canonical runtime today:** `~/Projects/toren`. **Portable target:** `~/Projects/sisyphus` (SDK lanes 2–4; see [Related repos](#related-repos-toren-vs-sisyphus-target)).

Upstream scraper API: [python-jobspy](https://github.com/speedyapply/JobSpy) (`scrape_jobs()`). Local orchestration is **not** a fork of that repo — it wraps PyPI `python-jobspy` plus custom filters, ATS boards, and triage.

---

## 1. Canonical daily flow

1. **Scrape** — `cd ~/Projects/toren/applications && python3 run_search_locally.py`  
   Multi-track search (Indeed/LinkedIn A–C, Google G, Remotive R, Lever L, Ashby AS, Greenhouse GH), filter pipeline, prescreen columns, daily CSV + `_new.csv` + yield logs.

2. **Triage CSV** — `cd ~/Projects/toren && python3 scripts/triage_jobspy_csv.py --latest`  
   Replays scraper filters via `import run_search_locally`; adds `triage_verdict`, ILS estimate, arrangement post-gates, wrapper hints, Phase-4 domain columns.

3. **Optional SDK ingest review** — `cd ~/Projects/cursor-sdk-playground && BATCH_DATE=YYYYMMDD ./scripts/toren_jobspy_ingest.sh`  
   Shell runs triage (backfill if assessment lag ≥2 days), dry-run `refresh_app_index.py`, then SDK agent with `ingest-search-results/SKILL.md` → `triage_review_*.md`, `assessment_*.md`.

4. **Application index** — `cd ~/Projects/toren/applications/scripts && python3 refresh_app_index.py` (default dry-run; `--apply` when safe)  
   Phase 4 calls `refresh_lib/jobspy_ingest.py` to surface **new** companies not already in Monitoring/strategy dirs (output-only in report).

**Net-new triage input:** Prefer `jobspy_results_YYYYMMDD_new.csv` when present (URLs not in prior full daily exports); else full `jobspy_results_YYYYMMDD.csv` (`ingest-search-results` Step 1).

---

## 2. Run order

| Step | Command / entry | Cwd | Produces |
|------|-----------------|-----|----------|
| 0 (optional) | `python3 applications/test_run_search_locally.py` or `scripts/run_all_tests.sh` | `~/Projects/toren` | Test pass/fail (before filter changes) |
| 1 | `python3 run_search_locally.py` | `~/Projects/toren/applications` | `jobspy_results/jobspy_results_YYYYMMDD.csv`, `_new.csv`, `yield_*.csv`, `search_errors.log` |
| 2 | `python3 scripts/triage_jobspy_csv.py --latest [--out …]` | `~/Projects/toren` | `triage_YYYYMMDD.csv` (or stdout summary) |
| 3 | `python3 scripts/export_triage_summary_for_ops.py` (ops) | `~/Projects/toren` | `triage_latest_ops.csv`, JSON rollup |
| 4 | `BATCH_DATE=… ./scripts/toren_jobspy_ingest.sh` | `cursor-sdk-playground` → agent `~/Projects/toren` | `triage_review_*.md`, `assessment_*.md`, SDK diligence log |
| 5 | `python3 applications/scripts/refresh_app_index.py [--apply]` | `~/Projects/toren/applications/scripts` | Diff report; optional HTML update (Phase 4 JobSpy section) |

**SDK lane 1 (inventory only):** `cd ~/Projects/cursor-sdk-playground && ./scripts/jobspy_lane1_locate.sh` → writes `~/Projects/sisyphus/docs/JOBSPY_INVENTORY.md`.

---

## 3. Entry commands

| Purpose | Command |
|---------|---------|
| Daily scrape (canonical) | `cd ~/Projects/toren/applications && python3 run_search_locally.py` |
| Triage latest full CSV | `cd ~/Projects/toren && python3 scripts/triage_jobspy_csv.py --latest` |
| Triage specific file | `python3 scripts/triage_jobspy_csv.py /path/to/jobspy_results_YYYYMMDD.csv --out applications/jobspy_results/triage_YYYYMMDD.csv` |
| Triage without post-gates | `python3 scripts/triage_jobspy_csv.py --latest --no-post-gates` |
| Include PM/PO titles in apply pool | `python3 scripts/triage_jobspy_csv.py --latest --include-pm-po` |
| Index refresh (dry-run) | `cd ~/Projects/toren/applications/scripts && python3 refresh_app_index.py` |
| Skip JobSpy phase in refresh | `python3 refresh_app_index.py --skip-jobspy` |
| SDK ingest + review | `cd ~/Projects/cursor-sdk-playground && BATCH_DATE=$(date +%Y%m%d) ./scripts/toren_jobspy_ingest.sh` |
| Extract index companies (CLI) | `cd ~/Projects/toren && python3 scripts/application_index_companies.py` |
| Regression suite | `cd ~/Projects/toren && scripts/run_all_tests.sh` |

---

## 4. Outputs (`~/Projects/toren/applications/jobspy_results/`)

| Artifact | Pattern / name | Role |
|----------|----------------|------|
| Full daily scrape | `jobspy_results_YYYYMMDD.csv` | All survivors after filter + prescreen; canonical scrape output |
| Net-new URLs | `jobspy_results_YYYYMMDD_new.csv` | Rows whose normalized `job_url` absent from prior `jobspy_results_*.csv` |
| Triage export | `triage_YYYYMMDD.csv`, `triage_latest.csv` | Script verdicts + ILS + wrapper columns |
| Operator review | `triage_review_YYYYMMDD.md` | SDK/operator packet |
| Wei assessment | `assessment_YYYYMMDD.md` | Funnel + scored survivors + actions |
| Funnel (legacy) | `yield_log.csv` | 6-column rollup per run |
| Funnel (extended) | `yield_funnel.csv` | Per-stage counts incl. PE/comp, desc, US col, JD geo |
| Errors | `search_errors.log` | Scraper warnings (rate limits, DNS, invalid country strings) |
| Roadmap | `ROADMAP.md` | Deferred pipeline improvements (linked from assessments) |
| Extra ATS slugs | `extra_ashby.txt`, `extra_gh.txt`, `extra_lever.txt` | Optional; merged at scrape time if present |
| SDK logs | `localonly/sdk-toren-jobspy-ingest-report.md` | Diligence checklist per ingest run |
| One-off | `inspect_*.py`, `inspect*.txt`, `auto_analysis_*.txt` | Ad-hoc analysis (not daily path) |

**CSV columns (post-scrape):** `track`, `title`, `company`, `location`, `date_posted`, `min_amount`, `max_amount`, `priority`, `stack_hits`, `yrs_req`, `domain`, `funding`, `job_url`, `description`, `query`.

---

## 5. File manifest

| Path | Role | Run by |
|------|------|--------|
| `toren/applications/run_search_locally.py` | **Primary scraper** — `scrape_jobs()` + Remotive/Lever/Ashby/GH + filter pipeline + prescreen + yield logs | Human / cron locally (`python3 run_search_locally.py`) |
| `toren/applications/prescreen.py` | Adds `stack_hits`, `yrs_req`, `domain`, `funding`, `priority` (not ILS) | Imported by `run_search_locally.py` |
| `toren/applications/index_companies.py` | Parses `application_index.html` → company tokens for auto-skip | Imported by `run_search_locally.py`; CLI via `scripts/application_index_companies.py` |
| `toren/scripts/triage_jobspy_csv.py` | CSV triage; imports `run_search_locally` filter functions + `refresh_lib.domain_inference` | Human, SDK shell (`toren_jobspy_ingest.sh`), `export_triage_summary_for_ops.py` |
| `toren/applications/scripts/refresh_lib/jobspy_ingest.py` | Phase 4: latest CSV → new-company heuristic report (no auto-add to index) | `refresh_app_index.py` |
| `toren/applications/scripts/refresh_lib/domain_inference.py` | Shared domain/tier/gate inference | `jobspy_ingest.py`, `triage_jobspy_csv.py` |
| `toren/applications/scripts/refresh_app_index.py` | Application index sync; invokes `ingest_jobspy()` unless `--skip-jobspy` | Human / SDK preflight (dry-run) |
| `toren/ingest-search-results/SKILL.md` | Agent workflow: find CSV, index URL dedupe, ILS heuristics, assessment format | Cursor/Claude when Wei says "jobspy" / SDK ingest agent |
| `toren/applications/skip_companies.txt` | Canonical company skip slugs | Loaded at scrape + triage |
| `toren/applications/referral_status.txt` | warm/strong ILS floor tiers | `triage_jobspy_csv.py` |
| `toren/applications/ils_overrides.json` | Per-company ILS overrides | `triage_jobspy_csv.py` |
| `toren/scripts/export_triage_summary_for_ops.py` | Ops rollup / n8n JSON from `--latest` triage | Ops automation |
| `toren/scripts/application_index_companies.py` | CLI wrapper for `index_companies` | Ad-hoc / debugging |
| `toren/scripts/run_all_tests.sh` | Runs triage/extractor regression suites | Before shipping filter changes |
| `toren/scripts/test_triage_20260515_regressions.py` | Fixture-backed triage regressions | `run_all_tests.sh` |
| `toren/scripts/test_wrapper_detect.py` | Staffing-wrapper detection tests | `run_all_tests.sh` |
| `toren/scripts/test_index_companies.py` | Index extractor contract tests | `run_all_tests.sh` |
| `toren/scripts/test_skip_key_variants.py` | Skip-key normalization tests | `run_all_tests.sh` |
| `toren/scripts/test_descblock_adversarial.py` | JD desc blocker adversarial cases | `run_all_tests.sh` |
| `toren/scripts/test_referral_floors.py` | Referral tier ILS floors | `run_all_tests.sh` |
| `toren/applications/test_run_search_locally.py` | pytest pins for filter functions | pytest / CI |
| `toren/applications/jobspy_results/*` | Data + assessments (see §4) | Scraper / triage / SDK |
| `cursor-sdk-playground/scripts/toren_jobspy_ingest.sh` | Orchestrates triage + SDK agent + verify | SDK operator |
| `cursor-sdk-playground/prompts/toren_jobspy_ingest.txt` | Worker prompt for ingest review | Rendered by `_toren_render_prompt.sh` |
| `cursor-sdk-playground/prompts/toren_jd_assess_manifest.json` | `jobspy_exclude` URLs/companies for ingest | Ingest agent READ |
| `cursor-sdk-playground/scripts/jobspy_lane1_locate.sh` | SDK: spawn agent to write sisyphus inventory | `./scripts/jobspy_lane1_locate.sh` |
| `cursor-sdk-playground/prompts/jobspy_lane1_locate.txt` | Lane 1 worker spec | SDK |
| `cursor-sdk-playground/prompts/jobspy-parallel-wave.md` | Four-lane wave index | Operator |
| `toren/career-helper.skill/workflows/triage_pipeline.md` | Sanitized triage workflow (ILS/JFS gate) | Skill reference |
| `toren/applications/atl_qa_scan.py` | **Adjacent** — manual Atlanta portal scanner (stdlib HTTP), not JobSpy | Optional manual scan |
| `sisyphus/README.md` | Bootstrap README; points to inventory + lane 3 port plan | Lane 3 target |
| `sisyphus/docs/JOBSPY_INVENTORY.md` | This file | Lane 1 output |

---

## 6. Environment

From `run_search_locally.py` docstring (run on host, not sandbox):

```bash
python3 -m pip install python-jobspy pandas requests --break-system-packages
```

**Imports:** `jobspy.scrape_jobs`, `pandas`, `requests`; local modules `prescreen`, `index_companies` (same directory as scraper).

**Runtime side effects on import:** reads `applications/skip_companies.txt`, `applications/application_index.html` (auto-skip merge), optional `jobspy_results/extra_{ashby,gh,lever}.txt`.

---

## 7. Dependencies

| Package | Used by |
|---------|---------|
| `python-jobspy` | `run_search_locally.py` — Indeed, LinkedIn, Google `scrape_jobs()` |
| `pandas` | Scraper concat/dedup/CSV; triage CSV read/write |
| `requests` | Remotive, Lever, Ashby, Greenhouse HTTP in scraper |
| stdlib only | `index_companies.py`, `prescreen.py`, most tests |
| `pytest` | `applications/test_run_search_locally.py` (optional) |

**Lane 3 sisyphus target** (not yet in repo): add `pyyaml`, `jsonschema` if search profile validation ships (`README.md`).

---

## 8. Related repos (toren vs sisyphus target)

| Repo | Role |
|------|------|
| **`~/Projects/toren`** | Production JobSpy stack, CSV data, skills, application index, assessments |
| **`~/Projects/sisyphus`** | Personal portable fork **target** — lane 3 copies `run_search_locally.py` → `scripts/run_search.py`, triage, profile config; env `JOB_SEARCH_RESULTS_DIR` |
| **`~/Projects/cursor-sdk-playground`** | SDK shell scripts + worker prompts; does not own scraper source |
| **PyPI `python-jobspy`** | Upstream; stay dependency, do not vendor (lane 3 `DIFFERENCES-vs-python-jobspy.md`) |

**Track legend (scraper):** A = SDET/QA/eval, B = AI IC eval/tooling, C = technical PM/TPM, G = Google Jobs, R = Remotive API, L = Lever, AS = Ashby, GH = Greenhouse boards.

---

## 9. Scoring layers (do not conflate)

| Layer | Where | Scale | Use |
|-------|-------|-------|-----|
| Prescreen | `prescreen.priority` in CSV | HIGH / MOD / LOW / ? | Sort CSV; not apply gate |
| Triage ILS | `triage_jobspy_csv.estimate_ils` → `ils_estimate` | 0–100 estimate | apply/skip post-gate (~45 floor) |
| JFS | Manual session | C1–C7, 0–100 | Effort/happiness after ILS pass |
| Refresh Phase 4 | `jobspy_ingest._estimate_jfs` | Heuristic float | New-company report in index refresh diff only |

Spec references: `toren/docs/reference_ils_scoring_model.md`, `ingest-search-results/SKILL.md`, `prescreen.py` module docstring.

---

*Generated by SDK jobspy-locate (lane 1). Verify: `test -f ~/Projects/sisyphus/docs/JOBSPY_INVENTORY.md`*
