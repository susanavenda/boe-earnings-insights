"""Browse-tab sort: interesting pairs first, not alphabetical order."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

FACTORY = Path(__file__).resolve().parents[1]


def _load_sort():
    demo = str(FACTORY / "demo")
    if demo not in sys.path:
        sys.path.insert(0, demo)
    from pipeline.browse import _sort_browse_rows

    return _sort_browse_rows


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "pair_id": ["a", "b", "c", "d"],
            "finbert_sentiment": ["positive", "negative", "neutral", None],
            "directness": [0.9, 0.2, None, 0.1],
            "topic_substitution": [0, 1, 0, 1],
        }
    )


def test_sort_most_negative_finbert_first():
    _sort_browse_rows = _load_sort()
    out = _sort_browse_rows(_frame(), "Most negative (FinBERT)")
    assert list(out["pair_id"]) == ["b", "c", "a", "d"]
    assert list(out["finbert_sentiment"].iloc[:3]) == ["negative", "neutral", "positive"]
    assert pd.isna(out["finbert_sentiment"].iloc[3])


def test_sort_least_direct_first():
    _sort_browse_rows = _load_sort()
    out = _sort_browse_rows(_frame(), "Least direct")
    assert list(out["pair_id"]) == ["d", "b", "a", "c"]
    assert list(out["directness"].iloc[:3]) == [0.1, 0.2, 0.9]
    assert pd.isna(out["directness"].iloc[3])


def test_sort_topic_substituted_first():
    _sort_browse_rows = _load_sort()
    out = _sort_browse_rows(_frame(), "Topic-substituted first")
    assert list(out["topic_substitution"]) == [1, 1, 0, 0]
    assert set(out.loc[out["topic_substitution"] == 1, "pair_id"]) == {"b", "d"}


def test_csv_tables_maps_full_corpus_export():
    demo = str(FACTORY / "demo")
    if demo not in sys.path:
        sys.path.insert(0, demo)
    from pipeline.db import CSV_TABLES

    assert CSV_TABLES["all_qa_pairs.csv"] == "qa_pairs_full"
