"""Stage 8 — protocol is alert/watch/null, not a firm rating. CS extra years are not extra cases."""
from __future__ import annotations

import pandas as pd

from build_supervisory_episode import EPISODES, build_cs_quarter_trend, build_protocol
from periods import calendar_period


def test_protocol_cases_are_exactly_three():
    ids = [e["id"] for e in EPISODES]
    assert ids == ["hsbc_2025_h1", "barclays_2026_h1", "cs_2022_q4"]
    assert calendar_period("2025-interim") == "2025-H1"
    assert calendar_period("2026-q2") == "2026-H1"
    assert calendar_period("2022-q4") == "2022-FY"


def test_protocol_rules_are_alert_watch_null():
    proto = build_protocol()
    assert set(proto["severity"]) == {"alert", "watch", "null"}
    assert set(proto["rule_id"]) == {"A1", "A2", "A3", "N1", "M6"}
    m6 = proto.loc[proto["rule_id"] == "M6"].iloc[0]
    assert m6["severity"] == "watch"
    assert m6["condition"] == "At least 3 impairment questions in the quarter and coverage below 50%"


def test_cs_trend_is_not_an_extra_protocol_case():
    extra_ids = [e["id"] for e in EPISODES if "cs_" in e["id"]]
    assert extra_ids == ["cs_2022_q4"]
    corp = pd.DataFrame(
        [
            {
                "bank": "credit_suisse",
                "quarter": "2021-q4",
                "finbert_net": 0.01,
                "finbert_sentiment": "neutral",
                "topic": 0,
                "text": "x",
            },
            {
                "bank": "credit_suisse",
                "quarter": "2022-q4",
                "finbert_net": 0.08,
                "finbert_sentiment": "positive",
                "topic": 1,
                "text": "y",
            },
        ]
    )
    trend = build_cs_quarter_trend(corp)
    assert set(trend["quarter"]) == {"2021-q4", "2022-q4"}
    assert len(EPISODES) == 3


def test_notebook_marks_cs_trend_as_extra(nb_code, nb_markdown):
    assert "8.4" in nb_code
    assert "not protocol" in nb_code or "extra" in nb_code.lower()
    assert "firm rating" in nb_markdown.lower() or "not a firm rating" in nb_markdown
