#!/bin/bash
# Creates the labels and milestones that import_issues.sh depends on.
# Run this BEFORE import_issues.sh.
#
# Usage (from repo root):
#   ./scripts/setup_labels_milestones.sh your-org-or-username/boe-earnings-insights

REPO="$1"
if [ -z "$REPO" ]; then
  echo "Usage: ./scripts/setup_labels_milestones.sh owner/repo"
  exit 1
fi

echo "Creating labels..."
gh label create "phase:initiation" --repo "$REPO" --color "5F5E5A" --force
gh label create "phase:planning"   --repo "$REPO" --color "3A5A78" --force
gh label create "phase:execution"  --repo "$REPO" --color "0F6E56" --force
gh label create "phase:closure"    --repo "$REPO" --color "534AB7" --force
gh label create "milestone"        --repo "$REPO" --color "854F0B" --force
gh label create "data"             --repo "$REPO" --color "378ADD" --force
gh label create "modelling"        --repo "$REPO" --color "D85A30" --force
gh label create "writing"          --repo "$REPO" --color "639922" --force
gh label create "presentation"     --repo "$REPO" --color "D4537E" --force
gh label create "research"         --repo "$REPO" --color "8A6FD0" --force

echo "Creating milestones..."
gh api "repos/$REPO/milestones" -f title="A1 — Scope & plan"      -f due_on="2026-09-14T17:00:00Z"
gh api "repos/$REPO/milestones" -f title="A2 — Solution pitch"    -f due_on="2026-09-28T17:00:00Z"
gh api "repos/$REPO/milestones" -f title="A3 — Final report"      -f due_on="2026-10-12T17:00:00Z"
gh api "repos/$REPO/milestones" -f title="A4 — Reflection"        -f due_on="2026-10-19T17:00:00Z"

echo "Done. Now run: ./scripts/import_issues.sh $REPO"
