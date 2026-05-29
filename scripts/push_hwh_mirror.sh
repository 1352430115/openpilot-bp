#!/usr/bin/env bash
# Push current branch to github.com/hwh-kavin/openpilot (standalone fork).
set -euo pipefail
cd /data/openpilot

export GIT_SSH_COMMAND="ssh -F /data/ssh/config"
REMOTE="${REMOTE:-hwh}"
BRANCH="${BRANCH:-$(git branch --show-current)}"

git remote get-url "$REMOTE" >/dev/null 2>&1 || \
  git remote add "$REMOTE" "git@github.com:hwh-kavin/openpilot.git"

git remote set-url "$REMOTE" "git@github.com:hwh-kavin/openpilot.git"
git remote set-url --push "$REMOTE" "git@github.com:hwh-kavin/openpilot.git"

echo "Pushing ${BRANCH} -> ${REMOTE}/${BRANCH} ..."
git push "$REMOTE" "${BRANCH}:${BRANCH}"
echo "Done: https://github.com/hwh-kavin/openpilot/tree/${BRANCH}"
