# Branch protection (`main`)

GitHub rules for the personal JobSpy repo **sisyphus**. Apply only after the remote exists and the operator confirms `GH_REPO`.

**Default target:** `weijia-89/sisyphus` (set explicitly; never assume from cwd alone).

## Policy

| Rule | Setting | Notes |
| ---- | ------- | ----- |
| Default branch | `main` | Set in repo Settings → General if the repo was created with another default. |
| Require PR before merge | yes | Direct pushes to `main` blocked once protection is on. |
| Require approvals | 1 | See [Solo maintainer tradeoff](#solo-maintainer-tradeoff). |
| Dismiss stale reviews | yes | New commits invalidate prior approvals. |
| Require conversation resolution | yes | Unresolved review threads block merge. |
| Require linear history | optional (off) | Enable if you squash-merge only and want a straight line; skip if you use merge commits. |
| Force pushes | block on `main` | Aligns with safetybar: no `--force` to shared default branch. |
| Branch deletions | block on `main` | Prevents accidental removal of the default branch. |
| Enforce for admins | off (default) | Repo admins can bypass; turn on if you want rules to bind you too. |
| Required status checks | none (placeholder) | Add when CI exists — see [Status checks (future)](#status-checks-future). |

## Solo maintainer tradeoff

With **required approving review count = 1**, GitHub expects someone other than the PR author to approve. On a solo personal repo that usually means:

- **Option A (strict):** keep `required_approving_review_count: 1` and use a second account, bot, or org rule exception — merges stay review-gated.
- **Option B (pragmatic solo):** set count to `0` but keep **require PR** + stale dismissal + conversation resolution — you still open a PR for audit trail, but you can merge without a second human.
- **Option C:** use GitHub’s “Allow specified actors to bypass required pull requests” (if available on your plan) for your user only — document who is on that list.

The bundled script defaults to **count = 1** (recommended policy table). Lower it in the JSON payload before apply if you choose Option B.

## Prerequisites

1. Remote repo exists: `gh repo view "$GH_REPO"`.
2. `gh` authenticated to **github.com** (not only an enterprise host): `gh auth status`.
3. Default branch is `main` (or edit the script branch name).
4. Operator confirms **`GH_REPO=owner/name`** matches the intended repo (safetybar — wrong repo PUT is hard to undo cleanly).

## Apply via script (preferred)

From repo root:

```bash
cd ~/Projects/sisyphus
export GH_REPO=weijia-89/sisyphus

# Dry run (default) — prints JSON only
./scripts/apply_branch_protection.sh

# Apply (only after repo exists + operator intent)
DRY_RUN=0 ./scripts/apply_branch_protection.sh
```

The script is idempotent: repeated `DRY_RUN=0` runs send the same PUT payload. It refuses apply if `gh repo view` fails.

## Manual UI steps

1. Open `https://github.com/<owner>/<repo>/settings/branches`.
2. **Add branch protection rule** → branch name pattern: `main`.
3. Enable:
   - **Require a pull request before merging**
   - **Require approvals** (1, or 0 for solo — see tradeoff)
   - **Dismiss stale pull request approvals when new commits are pushed**
   - **Require conversation resolution before merging**
4. Under **Rules applied to everyone including administrators** (optional): enable if you want no bypass.
5. Disable **Allow force pushes** and **Allow deletions**.
6. Leave **Require status checks** empty until CI is wired.
7. Save changes.

## `gh api` commands

Inspect current protection (404 = not configured yet):

```bash
export GH_REPO=weijia-89/sisyphus
OWNER="${GH_REPO%%/*}"
REPO="${GH_REPO##*/}"

gh api "repos/${OWNER}/${REPO}/branches/main/protection" 2>&1 || true
```

Dry-run payload (same as script):

```bash
DRY_RUN=1 GH_REPO=weijia-89/sisyphus ./scripts/apply_branch_protection.sh
```

Apply (requires repo + admin):

```bash
DRY_RUN=0 GH_REPO=weijia-89/sisyphus ./scripts/apply_branch_protection.sh
```

Equivalent one-shot PUT:

```bash
export GH_REPO=weijia-89/sisyphus
OWNER="${GH_REPO%%/*}"
REPO="${GH_REPO##*/}"

gh api -X PUT "repos/${OWNER}/${REPO}/branches/main/protection" --input - <<'EOF'
{
  "required_status_checks": null,
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 1
  },
  "restrictions": null,
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": true
}
EOF
```

## Status checks (future)

When CI exists (e.g. lint + `pytest`), add a section here and extend the script payload:

```json
"required_status_checks": {
  "strict": true,
  "contexts": ["ci / test"]
}
```

Until then, `required_status_checks` stays `null` so merges are not blocked on missing workflows.

## Git workflow after protection

- Work on feature branches; open PRs into `main`.
- **Do not** `git push --force` to `main` (blocked by protection; also disallowed by project policy).
- To undo a bad merge on `main`, use **revert commits**, not force-push.

## Related

- `README.md` — repo overview and SDK lane 4 entrypoint
- `scripts/apply_branch_protection.sh` — automation with `DRY_RUN=1` default
