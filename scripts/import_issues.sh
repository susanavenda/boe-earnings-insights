#!/bin/bash
# Bulk-create issues from issues.csv using the GitHub CLI.
#
# Setup (one-time):
#   1. Install the GitHub CLI: https://cli.github.com
#   2. Run: gh auth login   (follow the prompts)
#   3. Make sure the milestones (A1–A4) and labels already exist in the repo
#      — create them first via the web UI, or the import will fail on those rows.
#
# Usage (from repo root):
#   ./scripts/import_issues.sh your-org-or-username/boe-earnings-insights

REPO="$1"
if [ -z "$REPO" ]; then
  echo "Usage: ./scripts/import_issues.sh owner/repo"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CSV="${SCRIPT_DIR}/../docs/project/issues.csv"
if [ ! -f "$CSV" ]; then
  echo "Missing issues CSV: $CSV"
  exit 1
fi

# Skip header row, read each line
tail -n +2 "$CSV" | while IFS=',' read -r title body labels milestone; do
  echo "Creating: $title"
  gh issue create \
    --repo "$REPO" \
    --title "$title" \
    --body "$body" \
    --label "$labels" \
    --milestone "$milestone"
done

echo "Done. Check the Issues tab, then add them all to your Project view."
