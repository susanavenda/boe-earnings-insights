"""Faithfulness flags, cost/impairment direction, and the Stage 6.4 save."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "demo"))

from build_a1_evidence import behavioural_signals, cohort_of, prudential_map, state_summary
from build_qa_browser_export import flatten_qa_pairs
from pipeline.agreement import agree_row
from generate_pra_note import render_note
from keywords import faith_label, narrative_direction, reported_direction


def test_faith_label_accepts_sqlite_floats():
    assert faith_label(1.0) == "yes"
    assert faith_label(0.0) == "no"
    assert faith_label(np.float64(1.0)) == "yes"
    assert faith_label(np.bool_(False)) == "no"
    assert faith_label(float("nan")) is None
    assert faith_label(None) is None


def test_pra_note_and_desk_agree_on_stored_flags():
    briefs = pd.DataFrame(
        [
            {
                "episode_id": "hsbc_2025_h1",
                "metric": "cet1_ratio",
                "reported_direction": "up",
                "narrative_direction": "up",
                "faithful": 1.0,
            },
            {
                "episode_id": "hsbc_2025_h1",
                "metric": "operating_costs",
                "reported_direction": "down",
                "narrative_direction": "down",
                "faithful": 0.0,
            },
        ]
    )
    protocol = pd.DataFrame([{"rule_id": "A3", "severity": "watch", "condition": "soft"}])
    ep = {
        "id": "hsbc_2025_h1",
        "bank": "hsbc",
        "quarter": "2025-interim",
        "calendar_period": "2025-H1",
        "struct_quarter": "2025-q2",
        "label": "HSBC",
        "verdict": "WATCH",
        "headline": "x",
        "n_turns": 1,
        "finbert_net": 0.0,
        "topic1_turns": 0,
        "topic1_neg_share": 0.0,
        "peer_gap_hsbc_minus_barclays": None,
        "peer_hsbc_net": None,
        "peer_barclays_net": None,
        "rules_fired": [],
    }
    note = render_note(ep, briefs, protocol)
    assert "| cet1_ratio | up | up | yes |" in note
    assert "| operating_costs | down | down | no |" in note
    assert agree_row(briefs.iloc[0]) == "yes"
    assert agree_row(briefs.iloc[1]) == "no"
    missing = briefs.iloc[1].copy()
    missing["faithful"] = np.nan
    missing["n_qa_hits"] = 0
    assert agree_row(missing) == "n/a"


def test_costs_and_impairment_use_absolute_change():
    # A more negative charge is a larger cost, so the direction is up.
    assert reported_direction(-100, -120, metric="operating_costs") == "down"
    assert reported_direction(-120, -100, metric="operating_costs") == "up"
    assert reported_direction(-30, -10, metric="credit_impairment") == "up"
    # Income keeps the sign.
    assert reported_direction(80, 100, metric="total_income") == "down"
    assert reported_direction(14.2, 13.8, metric="cet1_ratio") == "up"


def test_downstream_frames_keep_the_new_behaviour_columns():
    qa = behavioural_signals(
        pd.DataFrame(
            [
                {
                    "pair_id": "a",
                    "bank": "hsbc",
                    "quarter": "2025-interim",
                    "question_text": "What about the CET1 ratio this quarter?",
                    "answer_text": "Revenue and fee income were very strong this quarter.",
                    "seed_topic_q": "capital",
                    "seed_topic_a": "profitability",
                    "prudential8_q": "capital_adequacy",
                    "prudential8_a": "profitability_earnings",
                }
            ]
        )
    )
    assert "substitution_measurable" in qa.columns
    assert "directness_v2" in qa.columns
    ss = state_summary(qa, None)
    assert "mean_directness_v2" in ss.columns
    assert cohort_of("hsbc") == "UK" and cohort_of("credit_suisse") == "CS"
    assert ss["cohort"].iloc[0] == "UK"
    assert "n_substitution_measurable" in ss.columns
    mapped = prudential_map(qa)
    assert len(mapped) == 1
    flat = flatten_qa_pairs(qa)
    assert list(flat.columns)


def test_stage_64_does_not_overwrite_narrative_without_metric():
    nb = json.loads((ROOT / "notebooks" / "boe_earnings_insights.ipynb").read_text())
    src = "\n".join("".join(c.get("source") or []) for c in nb["cells"])
    assert "_save('narrative_df', eval_narrative)" not in src
    assert "reported_direction" in src


def test_negative_tone_agrees_with_a_rising_charge():
    # Bigger impairment/cost charge is "up"; negative Q&A tone should agree with it.
    for metric in ("credit_impairment", "operating_costs"):
        assert narrative_direction(-0.3, metric) == "up"
        assert narrative_direction(0.3, metric) == "down"
        assert narrative_direction(0.0, metric) == "flat"
        assert narrative_direction(-0.3, metric) == reported_direction(-500, -400, metric=metric)
    # Income and CET1 keep the plain mapping.
    assert narrative_direction(0.3, "total_income") == "up"
    assert narrative_direction(-0.3, "cet1_ratio") == "down"
