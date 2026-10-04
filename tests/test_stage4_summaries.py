"""Stage 4 — Rafael extractive briefs, four KPI lock, no gold recode."""
from __future__ import annotations

import math

from build_metric_briefs import METRIC_KW, METRIC_LABELS, extractive_brief


FOUR = ("total_income", "operating_costs", "credit_impairment", "cet1_ratio")


def test_stage4_cells_present(nb_code, nb_markdown):
    assert "## Stage 4" in nb_markdown
    assert "4.1" in nb_code and "4.2" in nb_code and "4.3" in nb_code


def test_metric_catalogue_is_four_lines():
    assert tuple(METRIC_LABELS) == FOUR or set(METRIC_LABELS) == set(FOUR)
    assert set(METRIC_KW) == set(FOUR)


def test_extractive_brief_stays_in_source():
    text = (
        "Operating costs increased due to inflation. "
        "The cost programme remains on track this year. "
        "Wealth revenues were mixed."
    )
    brief, overlap = extractive_brief(text, "operating_costs")
    assert "cost" in brief.lower()
    assert overlap >= 0.2
    missing, ov = extractive_brief("No numbers here at all.", "cet1_ratio")
    assert "not clearly discussed" in missing
    assert math.isnan(ov)


def test_notebook_four_metrics_lock(nb_code):
    assert "METRICS_OF_INTEREST" in nb_code
    for m in FOUR:
        assert m in nb_code
