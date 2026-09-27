"""Full-corpus Browse helpers. Protocol lookup is visual — unreviewed ≠ Case File."""
from __future__ import annotations

import pandas as pd

SORT_NEGATIVE = "Most negative (FinBERT)"
SORT_DIRECT = "Least direct"
SORT_SUBST = "Topic-substituted first"
SORT_MODES = (SORT_NEGATIVE, SORT_DIRECT, SORT_SUBST)


def _sort_browse_rows(df: pd.DataFrame, mode: str) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    if mode == SORT_NEGATIVE:
        order = {"negative": 0, "neutral": 1, "positive": 2}
        return (
            df.assign(_k=df["finbert_sentiment"].map(order).fillna(3))
            .sort_values("_k")
            .drop(columns="_k")
            .reset_index(drop=True)
        )
    if mode == SORT_DIRECT:
        return df.sort_values("directness", ascending=True, na_position="last").reset_index(
            drop=True
        )
    if mode == SORT_SUBST:
        return df.sort_values("topic_substitution", ascending=False, na_position="last").reset_index(
            drop=True
        )
    return df
