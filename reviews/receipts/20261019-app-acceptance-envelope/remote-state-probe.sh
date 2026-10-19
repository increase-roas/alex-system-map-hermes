#!/bin/sh
# Read-only. Proves the reviewed commit was not published and no PR was opened for this work.
set -u
echo "local HEAD                = $(git rev-parse HEAD)"
echo "prior commit (merge)      = 4dcdf361de7bd77e7a738377166d14e8edd3da74"
echo "local origin/main ref     = $(git rev-parse origin/main)"
echo "LIVE remote main (ls-remote, fresh over the network):"
git ls-remote origin refs/heads/main
echo
echo "remote branches containing local HEAD (empty means unpublished):"
git branch -r --contains HEAD || true
echo "[end of remote-branch list]"
echo
echo "open/closed PRs whose head is main (this branch):"
gh pr list --repo increase-roas/alex-system-map --head main --state all --limit 20 --json number,state,headRefName,createdAt
echo "gh exit status for that query = $?"
