"""Deck map must join HSBC interim to Barclays q2 and lock the four PRA codes."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

FACTORY = Path(__file__).resolve().parents[1]


def _load_map():
    demo = str(FACTORY / "demo")
    if demo not in sys.path:
        sys.path.insert(0, demo)
    from pipeline.pitch_map import (
        KPI_TO_PRA,
        coverage_line,
        inbox_bucket,
        inbox_period_label,
        period_key,
        rows_for_episode,
    )

    return KPI_TO_PRA, coverage_line, inbox_bucket, inbox_period_label, period_key, rows_for_episode


def test_kpi_pra_codes_match_deck():
    kpi, _, _, _, _, _ = _load_map()
    assert kpi["total_income"]["pra"] == "P03"
    assert kpi["operating_costs"]["pra"] == "P03"
    assert kpi["credit_impairment"]["pra"] == "P04"
    assert kpi["cet1_ratio"]["pra"] == "P01"


def test_period_key_joins_interim_to_h1():
    _, _, _, _, period_key, _ = _load_map()
    assert period_key("2025-interim") == period_key("2025-q2") == "2025-h1"
    assert period_key("2024-annual") == period_key("2024-fy") == "2024-fy"


def test_rows_for_episode_keeps_matching_quarter():
    _, _, _, _, _, rows_for_episode = _load_map()
    df = pd.DataFrame(
        {
            "bank": ["hsbc", "hsbc", "barclays"],
            "quarter": ["2025-interim", "2024-annual", "2025-q2"],
            "mean_directness": [0.2, 0.3, 0.4],
        }
    )
    ep = {"bank": "hsbc", "quarter": "2025-interim", "calendar_period": "2025-H1"}
    out = rows_for_episode(df, ep)
    assert len(out) == 1
    assert float(out.iloc[0]["mean_directness"]) == 0.2


def test_coverage_line_never_fillna_story():
    _, coverage_line, _, _, _, _ = _load_map()
    text = coverage_line(pd.DataFrame())
    assert "missing" in text.lower() or "fillna" in text.lower()


def test_inbox_does_not_treat_2026_as_the_2025_peer():
    _, _, inbox_bucket, inbox_period_label, _, _ = _load_map()
    hsbc = {"bank": "hsbc", "id": "hsbc_2025_h1", "calendar_period": "2025-H1", "quarter": "2025-interim"}
    barx = {"bank": "barclays", "id": "barclays_2026_h1", "calendar_period": "2026-H1", "quarter": "2026-q2"}
    cs = {"bank": "credit_suisse", "id": "cs_2022_q4", "calendar_period": "2022-FY", "quarter": "2022-q4"}
    assert inbox_bucket(hsbc) == "paired"
    assert inbox_bucket(barx) == "in_progress"
    assert inbox_bucket(cs) == "a3"
    assert inbox_period_label(cs) == "2022-Q4"


def test_reviewed_flag_distinguishes_computed_quarters():
    demo = str(FACTORY / "demo")
    if demo not in sys.path:
        sys.path.insert(0, demo)
    from pipeline.pitch_map import is_reviewed_episode, trail_for

    hsbc = {"id": "hsbc_2025_h1", "bank": "hsbc", "reviewed": True}
    extra = {"id": "hsbc_2018_annual", "bank": "hsbc", "reviewed": False}
    assert is_reviewed_episode(hsbc) is True
    assert is_reviewed_episode(extra) is False
    assert "Unreviewed" in trail_for(extra)
    assert "WATCH" in trail_for(hsbc)
