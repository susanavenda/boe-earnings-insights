"""Desk agreement flag. Kept out of app.py so tests can import it without Streamlit."""
from __future__ import annotations

import pandas as pd


def faith_flag(faith) -> str | None:
    """yes/no when a flag was stored; None when empty. SQLite returns 0.0/1.0, not bools."""
    try:
        missing = bool(pd.isna(faith))
    except (TypeError, ValueError):
        missing = faith is None
    if missing:
        return None
    return "yes" if bool(faith) else "no"


def agree_row(row: pd.Series) -> str:
    labelled = faith_flag(row.get("faithful"))
    if labelled is not None:
        return labelled
    nar = str(row.get("narrative_direction") or "").strip().lower()
    hits = row.get("n_qa_hits")
    if pd.isna(hits) or int(hits or 0) == 0 or nar in ("", "nan", "none"):
        return "n/a"
    rep = str(row.get("reported_direction") or "").lower()
    return "yes" if rep == nar else "no"
