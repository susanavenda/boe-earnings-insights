#!/bin/bash
# Creates the labels and milestones that import_issues.sh depends on.
# Idempotent: safe to re-run. Run this BEFORE import_issues.sh.
#
# Usage (from repo root):
#   ./scripts/setup_labels_milestones.sh [owner/repo]

set -euo pipefail

REPO="${1:-}"
if [ -z "$REPO" ]; then
  REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || true)"
fi
if [ -z "$REPO" ]; then
  echo "Usage: ./scripts/setup_labels_milestones.sh owner/repo"
  exit 1
fi

echo "Repo: $REPO"
echo "Creating labels..."

create_label() {
  local name="$1" color="$2" desc="${3:-}"
  if [ -n "$desc" ]; then
    gh label create "$name" --repo "$REPO" --color "$color" --description "$desc" --force
  else
    gh label create "$name" --repo "$REPO" --color "$color" --force
  fi
}

create_label "phase:initiation" "5F5E5A" "Kick-off / charter"
create_label "phase:planning"   "3A5A78" "A1 planning"
create_label "phase:execution"  "0F6E56" "A2–A3 build"
create_label "phase:closure"    "534AB7" "A4 reflection"
create_label "milestone"        "854F0B" "Assignment submit gate"
create_label "data"             "378ADD" "Corpus / evidence"
create_label "modelling"        "D85A30" "Topics / sentiment / signals"
create_label "writing"          "639922" "Report text"
create_label "presentation"     "D4537E" "Deck / recording"
create_label "research"         "8A6FD0" "Domain / mapping"
create_label "gate"             "B60205" "M1–M10 acceptance test"
create_label "owner:evidence-pair"   "378ADD" "Evidence pair"
create_label "owner:signals-pair"    "D85A30" "Signals pair"
create_label "owner:synthesis"       "639922" "Synthesis"
create_label "owner:domain-analyst"  "8A6FD0" "Domain analyst"
create_label "owner:project-lead"    "854F0B" "Project lead"

echo "Ensuring milestones..."
ensure_milestone() {
  local title="$1" due="$2"
  if gh api "repos/$REPO/milestones?state=all" --jq ".[].title" | grep -Fxq "$title"; then
    echo "  exists: $title"
  else
    gh api "repos/$REPO/milestones" -f title="$title" -f due_on="$due" >/dev/null
    echo "  created: $title"
  fi
}

ensure_milestone "A1 — Scope & plan"   "2026-09-14T17:00:00Z"
ensure_milestone "A2 — Solution pitch" "2026-09-28T17:00:00Z"
ensure_milestone "A3 — Final report"   "2026-10-12T17:00:00Z"
ensure_milestone "A4 — Reflection"     "2026-10-19T17:00:00Z"

echo "Done. Now run: ./scripts/import_issues.sh $REPO"
echo "  Gates only (skip already-imported A1–A4 tasks): ./scripts/import_issues.sh $REPO --gates-only"
