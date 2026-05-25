# Migration task — sisyphus replaces `career-helper` (private)

**Status:** not started (operator-tracked)  
**Target GitHub:** `weijia-89/sisyphus` — **private**, branch protection on `main`  
**Retire / supersede:** `weijia-89/career-helper` (private legacy JobSpy bundle) · **`weijia-89/corpofit`** (public fit calculator → merged under `fit/` — see `docs/CORPORFIT_MERGE.md`)

## Policy

| Rule | Detail |
|------|--------|
| **No `toren` in sisyphus git** | Application index, assessments, corpovoice, and preapply live in a **separate local-only** career-ops tree. Do not document `~/Projects/toren` paths in README, inventory, or public repo files. |
| **No secrets in sisyphus** | `search_profile.local.yaml`, CSV exports, referral files with PII, and `.venv` stay gitignored. |
| **Private + locked** | Repo visibility **private**. `docs/BRANCH_PROTECTION.md` + `scripts/apply_branch_protection.sh` before treating `main` as production. |
| **JobSpy canonical here** | Daily scrape + triage commands run from `~/Projects/sisyphus` only after cutover. |

## Checklist

### A. GitHub hygiene (before advertising the repo)

- [ ] Confirm `gh repo view weijia-89/sisyphus` — if **public**, run `gh repo edit weijia-89/sisyphus --visibility private --accept-visibility-change-consequences`
- [ ] If remote missing: `gh repo create weijia-89/sisyphus --private --source=. --remote=origin` from clean tree (no local CSV data committed)
- [ ] Push default branch; set default branch to `main` (or document `master` → rename if needed)
- [ ] `DRY_RUN=1 GH_REPO=weijia-89/sisyphus ./scripts/apply_branch_protection.sh` then `DRY_RUN=0` after review
- [ ] Archive or add README banner on `weijia-89/career-helper`: “JobSpy stack moved to private sisyphus — do not use for scrape/triage”

### B. Repo content (sisyphus-only docs)

- [x] Scraper + triage scripts under `scripts/` (lane 3)
- [x] Profile schema + `lib/search_profile.py` (lane 2)
- [ ] Remove remaining **toren** / **career-help** path references from tracked markdown (see grep: `rg -n 'toren|career-help' --glob '!localonly/**'`)
- [ ] `docs/JOBSPY_INVENTORY.md` describes **this repo only** (done in same migration PR)
- [ ] Optional: port `test_run_search_locally.py` → `tests/` with pytest (no toren imports)

### C. Operator cutover (local machine)

- [ ] Point daily cron / aliases at `cd ~/Projects/sisyphus && python3 scripts/run_search.py`
- [ ] Copy **data only** (not committed): prior `jobspy_results/*.csv` → `data/jobspy_results/` if history needed
- [ ] Copy `skip_companies.txt`, `ils_overrides.json`, referral template from legacy tree into `config/` (local edits, not committed if sensitive)
- [ ] Update `JOB_APPLICATION_INDEX` env to a **local path** outside sisyphus if index HTML stays in career-ops tree
- [ ] SDK ingest / preapply / index refresh remain in **career-ops** workspace (`cursor-sdk-playground` + local applications tree) — **not** part of sisyphus publish

### D. Downstream doc fixes (outside sisyphus)

- [ ] `toren/ingest-search-results/SKILL.md` Step 3: replace `~/Projects/career-help` with sisyphus triage path (career-ops repo, separate commit)
- [ ] `cursor-sdk-playground` jobspy lane 1–3 prompts: mark copy-from-toren as **historical**; new work reads sisyphus only

## Success criteria

1. `rg 'toren|career-help' ~/Projects/sisyphus --glob '!localonly/**' --glob '!.venv/**'` returns no matches in operator-facing docs (code comments may cite “ported 2026-05” without paths).
2. `weijia-89/sisyphus` is **private**, protection applied, default branch receives PRs only.
3. Wei runs one full scrape + triage cycle from sisyphus without referencing `career-helper` or `toren` in commands.

## SDK kickoff (Wave 6H — unified repo)

See `~/Projects/cursor-sdk-playground/prompts/sdk-wave6h-kickoffs.txt`:

```bash
cd ~/Projects/cursor-sdk-playground
export SDK_STAKES_TIER=vibe-careful
# Parallel (≤2 agents on sisyphus):
./scripts/sisyphus_merge_corpofit.sh
./scripts/sisyphus_search_profiles_corpofit.sh
# After PRs merge:
./scripts/sisyphus_github_unify.sh
```

After unify: complete checklist A manually; **sisyphus stays private**.
