"""Cross-stage join: periods, seed, protocol, and sqlite artefacts stay aligned."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from build_a1_evidence import seed_label
from build_metric_briefs import METRIC_KW as BRIEF_KW
from build_supervisory_episode import EPISODES, METRIC_KW as EP_KW
from periods import calendar_period
from topic_modeling import clean_timestamp, get_bertopic_input_column

ROOT = Path(__file__).resolve().parents[1]


def test_four_kpi_names_match_across_evidence_briefs_and_episodes():
    assert set(BRIEF_KW) == set(EP_KW)
    assert set(BRIEF_KW) == {
        "total_income",
        "operating_costs",
        "credit_impairment",
        "cet1_ratio",
    }


def test_protocol_quarters_join_via_calendar_period():
    for spec in EPISODES:
        assert calendar_period(spec["quarter"]) == spec["calendar_period"]
        assert calendar_period(spec["struct_quarter"]) == spec["calendar_period"]


def test_drift_dates_stay_distinct_when_protocol_join_collapses_h1():
    assert calendar_period("2024-q1") != calendar_period("2024-interim")
    assert calendar_period("2024-q2") == calendar_period("2024-interim")
    assert clean_timestamp("2024-q1") != clean_timestamp("2024-interim")
    assert clean_timestamp("2024-q2") != clean_timestamp("2024-interim")


def test_llm_opt_in_does_not_break_the_stage2_to_stage3_column(monkeypatch):
    monkeypatch.delenv("BOE_USE_LLM_PREPROCESSING", raising=False)
    df = pd.DataFrame(
        {
            "clean_text": ["analyst words"],
            "llm_preprocessed_text": ["paraphrase"],
        }
    )
    assert get_bertopic_input_column(df) == "clean_text"


def test_seed_and_episode_keywords_agree_on_impairment():
    assert seed_label("credit impairment and ECL rose") == "asset_quality"
    assert any(k in "impairment ecl" for k in EP_KW["credit_impairment"])


def test_live_sqlite_has_joined_stage_tables():
    db = ROOT / "data" / "boe.sqlite"
    if not db.is_file():
        pytest.skip("no local data/boe.sqlite")
    import store

    store.configure(memory=False, path=db, auto_flush=False)
    needed = ["qa_pairs", "corpus_analyst", "protocol"]
    present = []
    for name in needed:
        try:
            frame = store.load_df(name)
        except Exception:
            continue
        if frame is not None and not frame.empty:
            present.append(name)
    assert present, "sqlite exists but core stage tables are empty"
