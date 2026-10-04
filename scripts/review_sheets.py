"""Write human-review CSVs without wiping what a reviewer already filled in.

The notebook regenerates the review sheets on every run (mixed_split_review.csv,
untagged_reasons.csv). A plain to_csv would erase the reviewer's columns, so:

- rows still in the new sheet keep any non-empty reviewer value from the old file;
- rows the reviewer filled in that are no longer generated are kept at the
  bottom with stale=True, so no manual answer is ever dropped silently.

Rows are matched on (pair_id, source): pair_id alone repeats when two PDFs share
a bank-quarter, and row positions change between runs.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

KEY = ("pair_id", "source")


def _filled(s: pd.Series) -> pd.Series:
    t = s.fillna("").astype(str).str.strip()
    return t.ne("") & t.str.lower().ne("nan")


def save_review_sheet(new: pd.DataFrame, path, manual_cols, key=KEY) -> dict:
    """Write `new` to `path`, carrying over reviewer columns. Returns counts."""
    path = Path(path)
    key = [k for k in key if k in new.columns]
    manual_cols = list(manual_cols)
    out = new.reset_index(drop=True).copy()
    for c in manual_cols:
        if c not in out.columns:
            out[c] = ""
    out["stale"] = False
    kept = stale = 0
    if path.exists() and key:
        old = pd.read_csv(path, dtype=str, keep_default_na=False)
        cols = [c for c in manual_cols if c in old.columns]
        if cols and all(k in old.columns for k in key):
            any_filled = pd.concat([_filled(old[c]) for c in cols], axis=1).any(axis=1)
            done = old[any_filled].drop_duplicates(subset=key, keep="last")
            new_keys = out[key].astype(str)
            merged = new_keys.merge(done[key + cols], on=key, how="left", suffixes=("", "_old"))
            for c in cols:
                carried = merged[c].fillna("")
                mask = _filled(carried).to_numpy()
                out.loc[mask, c] = carried[mask].to_numpy()
                kept += int(mask.sum())
            seen = set(map(tuple, new_keys.to_numpy()))
            gone = done[[tuple(r) not in seen for r in done[key].astype(str).to_numpy()]]
            if len(gone):
                gone = gone.assign(stale=True)
                out = pd.concat([out, gone[[c for c in out.columns if c in gone.columns]]], ignore_index=True)
                stale = len(gone)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)
    return {"rows": len(out), "reviewer_values_kept": kept, "stale_rows_kept": stale}
