#!/usr/bin/env bash
# Push IR PDFs + Excel packs so Colab can git-clone a working factory.
set -euo pipefail
cd "$(dirname "$0")/.."
git add data/raw/transcripts data/structured docs/hand_validation_sample.csv
git status --short data/raw data/structured
echo
echo "If the list above is empty, the files are not on disk."
echo "Then: git commit -m 'Add IR PDFs and Excel packs for Colab' && git push"
