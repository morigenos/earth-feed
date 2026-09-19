#!/usr/bin/env bash
# Creates the feed repository and pushes these files, using the GitHub CLI.
# Install it first (https://cli.github.com), then run: bash setup.sh
set -euo pipefail

REPO="${1:-earth-feed}"

command -v gh >/dev/null || { echo "GitHub CLI not found. Install it from https://cli.github.com and run 'gh auth login'."; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "Not signed in. Run 'gh auth login' first."; exit 1; }

git init -q 2>/dev/null || true
git add .
git -c user.name="earth-feed" -c user.email="noreply@example.com" commit -qm "Earth Observatory data feed" || true
git branch -M main

gh repo create "$REPO" --public --source=. --push

USER=$(gh api user --jq .login)
echo
echo "Repository created: https://github.com/$USER/$REPO"
echo
echo "Optional keys:"
echo "  gh secret set FIRMS_KEY"
echo "  gh secret set OPENSKY_ID"
echo "  gh secret set OPENSKY_SECRET"
echo "  gh secret set GFW_TOKEN"
echo
echo "Run the job once now:"
echo "  gh workflow run 'Update Earth Observatory feed'"
echo
echo "Feed:"
echo "  https://raw.githubusercontent.com/$USER/$REPO/main/data/"
