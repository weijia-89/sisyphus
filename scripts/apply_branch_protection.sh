#!/usr/bin/env bash
# Apply GitHub branch protection on main. Default DRY_RUN=1.
# Requires GH_REPO=owner/name. Never stores tokens in this file.
set -euo pipefail

GH_REPO="${GH_REPO:?set GH_REPO=owner/repo (e.g. weijia-89/sisyphus)}"
DRY_RUN="${DRY_RUN:-1}"
BRANCH="${BRANCH:-main}"
OWNER="${GH_REPO%%/*}"
REPO="${GH_REPO##*/}"

if [[ "$OWNER" == "$REPO" || -z "$OWNER" || -z "$REPO" ]]; then
  echo "error: GH_REPO must be owner/repo, got: $GH_REPO" >&2
  exit 1
fi

PAYLOAD=$(cat <<EOF
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
)

echo "target: $GH_REPO branch=$BRANCH DRY_RUN=$DRY_RUN" >&2

if [[ "$DRY_RUN" == "1" ]]; then
  echo "DRY_RUN=1 — would PUT repos/$OWNER/$REPO/branches/$BRANCH/protection"
  echo "$PAYLOAD" | python3 -m json.tool
  exit 0
fi

if ! gh repo view "$GH_REPO" --json nameWithOwner >/dev/null 2>&1; then
  echo "error: repo $GH_REPO not found or not visible; aborting (no PUT)." >&2
  exit 1
fi

echo "Applying protection to $GH_REPO ($BRANCH) …" >&2
gh api -X PUT "repos/${OWNER}/${REPO}/branches/${BRANCH}/protection" --input - <<<"$PAYLOAD"
echo "done — verify with: gh api repos/${OWNER}/${REPO}/branches/${BRANCH}/protection" >&2
