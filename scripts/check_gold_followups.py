#!/usr/bin/env python3
"""Which human-labelled pairs changed after the follow-up parser fix?

The parser now splits an analyst follow-up into its own pair (``_002b``) instead
of folding it into the previous answer. Labelled pair_ids keep their number, but
a labelled pair whose answer used to contain a follow-up now has a shorter
answer_text than the one the coders read.

Run after Stage 1.5 has rebuilt qa_pairs:
    python scripts/check_gold_followups.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from store import configure, has_df, load_df  # noqa: E402

LABELS = ROOT / "docs" / "assignment2" / "human_labels"
FOLLOWUP = re.compile(r"^(?P<stem>.+_\d{3})[b-z]$")


def gold_ids() -> dict[str, set[str]]:
    packs = {}
    for name in ("sentiment_90_labels_template.csv", "sample_60_machine_key.csv"):
        path = LABELS / name
        if path.exists():
            packs[name] = set(pd.read_csv(path)["pair_id"].astype(str))
    return packs


def affected(qa: pd.DataFrame, ids: set[str]) -> list[str]:
    stems = {
        m.group("stem")
        for pid in qa["pair_id"].astype(str)
        if (m := FOLLOWUP.match(pid))
    }
    return sorted(ids & stems)


def main() -> None:
    configure(memory=False)
    if not has_df("qa_pairs"):
        raise SystemExit("qa_pairs not in data/boe.sqlite — run notebook Stage 1.5 first")
    qa = load_df("qa_pairs")
    n_follow = int(qa["pair_id"].astype(str).str.match(FOLLOWUP).sum())
    print(f"qa_pairs {len(qa)}, follow-up pairs {n_follow}")
    for name, ids in gold_ids().items():
        missing = sorted(ids - set(qa["pair_id"].astype(str)))
        hit = affected(qa, ids)
        print(f"\n{name}: {len(ids)} labelled pairs")
        print(f"  answer now shorter (a follow-up was split out): {len(hit)}")
        for pid in hit:
            print(f"    {pid}")
        if missing:
            print(f"  pair_ids no longer in qa_pairs: {len(missing)} {missing[:10]}")


if __name__ == "__main__":
    main()
