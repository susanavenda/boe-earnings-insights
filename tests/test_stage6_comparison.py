"""Stage 6 — temporal / peer / structured-vs-unstructured. Peer gap is HSBC−Barclays."""
from __future__ import annotations

import pandas as pd
import pytest

from periods import matched_peer_gap


def test_stage6_three_views_present(nb_markdown, nb_code):
    assert "## Stage 6" in nb_markdown
    assert "6.0" in nb_code
    assert "6.1" in nb_code
    assert "6.1b" in nb_code
    assert "6.2" in nb_markdown or "Peer gap" in nb_markdown
    assert "6.3" in nb_code


def test_notebook_peer_gap_formula_is_hsbc_minus_barclays(nb_code):
    assert "agg['hsbc'] - agg['barclays']" in nb_code
    assert "both['hsbc'] - both['barclays']" in nb_code
    assert "def plot_peer_gap" in nb_code
    body = nb_code.split("def plot_peer_gap", 1)[1][:800]
    assert "credit_suisse" not in body


def test_peer_chart_defaults_to_2012_2025_both_complete(nb_code):
    assert "in_peer_window" in nb_code
    assert "both_complete" in nb_code


def test_topic_appear_disappear_is_not_a_sentiment_zscore(nb_markdown):
    assert "appear / disappear" in nb_markdown
    assert "not a sentiment z-score" in nb_markdown


def test_matched_peer_gap_is_hsbc_minus_barclays_drops_cs_and_unpaired():
    df = pd.DataFrame(
        [
            {"bank": "hsbc", "quarter": "2020-interim", "sentiment_net": 0.20},
            {"bank": "barclays", "quarter": "2020-q2", "sentiment_net": 0.10},
            {"bank": "credit_suisse", "quarter": "2020-q2", "sentiment_net": 9.0},
            {"bank": "hsbc", "quarter": "2019-annual", "sentiment_net": 0.40},
            {"bank": "hsbc", "quarter": "2011-interim", "sentiment_net": 0.50},
            {"bank": "barclays", "quarter": "2011-q2", "sentiment_net": 0.10},
            {"bank": "hsbc", "quarter": "2026-interim", "sentiment_net": 0.30},
            {"bank": "barclays", "quarter": "2026-q2", "sentiment_net": 0.10},
        ]
    )
    gap = matched_peer_gap(df)
    assert list(gap["calendar_period"]) == ["2020-H1"]
    assert gap["gap"].iloc[0] == pytest.approx(0.10)
    assert "credit_suisse" not in gap.columns
    assert gap["barclays"].iloc[0] == pytest.approx(0.10)

    wide = matched_peer_gap(df, peer_window_only=False)
    assert set(wide["calendar_period"]) == {"2011-H1", "2020-H1", "2026-H1"}
    assert "2019-FY" not in set(wide["calendar_period"])


def test_matched_peer_gap_never_fillnas_zero():
    df = pd.DataFrame(
        [
            {"bank": "hsbc", "quarter": "2018-fy", "sentiment_net": 0.5},
            {"bank": "barclays", "quarter": "2018-q4", "sentiment_net": float("nan")},
        ]
    )
    gap = matched_peer_gap(df)
    assert gap.empty
