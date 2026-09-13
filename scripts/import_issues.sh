#!/bin/bash
# Bulk-create issues from docs/project/issues.csv using the GitHub CLI.
#
# Parses quoted multiline CSV (required for M1–M10 gate bodies).
# Splits semicolon-separated labels into separate GitHub labels.
# Skips titles that already exist (open or closed).
#
# Setup (one-time):
#   1. gh auth login
#   2. ./scripts/setup_labels_milestones.sh [owner/repo]
#
# Usage (from repo root):
#   ./scripts/import_issues.sh [owner/repo] [--gates-only] [--dry-run]
#
#   --gates-only   import M1–M10 and the A3 live gate only
#   --dry-run      print what would be created, do not call gh issue create

set -euo pipefail

REPO=""
GATES_ONLY=0
DRY_RUN=0

for arg in "$@"; do
  case "$arg" in
    --gates-only) GATES_ONLY=1 ;;
    --dry-run)    DRY_RUN=1 ;;
    --*)
      echo "Unknown flag: $arg"
      echo "Usage: ./scripts/import_issues.sh [owner/repo] [--gates-only] [--dry-run]"
      exit 1
      ;;
    *)
      if [ -z "$REPO" ]; then
        REPO="$arg"
      else
        echo "Unexpected argument: $arg"
        exit 1
      fi
      ;;
  esac
done

if [ -z "$REPO" ]; then
  REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || true)"
fi
if [ -z "$REPO" ]; then
  echo "Usage: ./scripts/import_issues.sh owner/repo [--gates-only] [--dry-run]"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CSV="${SCRIPT_DIR}/../docs/project/issues.csv"
if [ ! -f "$CSV" ]; then
  echo "Missing issues CSV: $CSV"
  exit 1
fi

export REPO CSV GATES_ONLY DRY_RUN

python3 - <<'PY'
import csv, json, os, re, subprocess, sys
from pathlib import Path

repo = os.environ["REPO"]
csv_path = Path(os.environ["CSV"])
gates_only = os.environ.get("GATES_ONLY", "0") == "1"
dry_run = os.environ.get("DRY_RUN", "0") == "1"


def gh(*args, check=True):
    return subprocess.run(
        ["gh", *args],
        check=check,
        capture_output=True,
        text=True,
    )


def existing_titles():
    titles = set()
    cmd = [
        "gh", "issue", "list",
        "--repo", repo,
        "--state", "all",
        "--limit", "500",
        "--json", "title",
    ]
    raw = subprocess.check_output(cmd, text=True)
    for item in json.loads(raw):
        titles.add(item["title"].strip())
    return titles


def is_gate(title: str) -> bool:
    t = title.strip()
    return bool(re.match(r"^M\d+\s", t) or t.startswith("A3 live"))


def split_labels(raw: str):
    return [p.strip() for p in (raw or "").split(";") if p.strip()]


def compose_body(row: dict) -> str:
    body = (row.get("body") or "").strip()
    start = (row.get("start_date") or "").strip()
    due = (row.get("due_date") or "").strip()
    if start or due:
        stamp = " · ".join(
            x for x in (
                f"Start: {start}" if start else "",
                f"Due: {due}" if due else "",
            ) if x
        )
        if stamp and stamp not in body:
            body = f"{body}\n\n---\n{stamp}" if body else stamp
    return body


print(f"Repo: {repo}")
print(f"CSV:  {csv_path}")
print("Loading existing issue titles...")
have = existing_titles()
print(f"  {len(have)} existing")

created = skipped = 0
with csv_path.open(newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        title = (row.get("title") or "").strip()
        if not title:
            continue
        if gates_only and not is_gate(title):
            continue
        if title in have:
            print(f"SKIP exists: {title}")
            skipped += 1
            continue

        labels = split_labels(row.get("labels") or "")
        milestone = (row.get("milestone") or "").strip()
        body = compose_body(row)

        print(f"{'DRY ' if dry_run else ''}CREATE: {title}")
        if labels:
            print(f"         labels: {', '.join(labels)}")
        if milestone:
            print(f"         milestone: {milestone}")
        if dry_run:
            created += 1
            continue

        args = [
            "issue", "create",
            "--repo", repo,
            "--title", title,
            "--body", body or title,
        ]
        for lab in labels:
            args.extend(["--label", lab])
        if milestone:
            args.extend(["--milestone", milestone])
        proc = gh(*args, check=False)
        if proc.returncode != 0:
            sys.stderr.write(proc.stderr)
            sys.exit(proc.returncode or 1)
        url = (proc.stdout or "").strip()
        if url:
            print(f"         {url}")
        have.add(title)
        created += 1

print(f"Done. created={created} skipped={skipped}")
if not dry_run:
    print("Add new issues to the Project view if they are not auto-added.")
PY
