"""Full-corpus Browse export: flatten only, unique pair_id, no invented scores."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from build_qa_browser_export import COLUMNS, flatten_qa_pairs

ROOT = Path(__file__).resolve().parents[1]


def _qa(**overrides):
    row = {
        "pair_id": "hsbc_2024-q1_001",
        "bank": "hsbc",
        "quarter": "2024-q1",
        "question_text": "What happened to CET1?",
        "answer_text": "The ratio was stable.",
        "question_sentiment": "negative",
        "question_ldsa_sentiment": "neutral",
        "directness": 0.4,
        "topic_substitution": 0,
    }
    row.update(overrides)
    return pd.DataFrame([row])


def test_flatten_has_expected_columns_and_calendar_period():
    out = flatten_qa_pairs(_qa())
    assert list(out.columns) == COLUMNS
    assert len(out) == 1
    assert out.loc[0, "calendar_period"] == "2024-H1q1"
    assert out.loc[0, "finbert_sentiment"] == "negative"
    assert out.loc[0, "ldsa_sentiment"] == "neutral"


def test_flatten_leaves_missing_scores_null():
    qa = _qa()
    qa = qa.drop(columns=["question_ldsa_sentiment"])
    out = flatten_qa_pairs(qa)
    assert pd.isna(out.loc[0, "ldsa_sentiment"])
    assert pd.isna(out.loc[0, "topic_id"])


def test_flatten_pair_id_unique_when_source_has_dups():
    qa = pd.concat([_qa(), _qa()], ignore_index=True)
    qa.loc[1, "question_text"] = "duplicate id, different text"
    out = flatten_qa_pairs(qa)
    assert len(out) == 1
    assert out["pair_id"].is_unique
    assert out.loc[0, "question_text"] == "What happened to CET1?"


def test_flatten_attaches_existing_topic_without_inventing():
    qa = _qa()
    corp = pd.DataFrame(
        [
            {
                "bank": "hsbc",
                "quarter": "2024-q1",
                "text": "What happened to CET1?",
                "topic": 7,
            }
        ]
    )
    out = flatten_qa_pairs(qa, corp)
    assert out.loc[0, "topic_id"] == 7
    unmatched = flatten_qa_pairs(_qa(question_text="unseen question"), corp)
    assert pd.isna(unmatched.loc[0, "topic_id"])


def test_flatten_empty_returns_schema():
    out = flatten_qa_pairs(pd.DataFrame())
    assert list(out.columns) == COLUMNS
    assert out.empty


def test_export_columns_and_unique_pair_id_on_live_sqlite():
    db = ROOT / "data" / "boe.sqlite"
    if not db.is_file():
        pytest.skip("no local data/boe.sqlite")
    import sqlite3

    conn = sqlite3.connect(str(db))
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "qa_pairs" not in tables:
        pytest.skip("qa_pairs not in sqlite")
    qa = pd.read_sql_query("SELECT * FROM qa_pairs", conn)
    corp = (
        pd.read_sql_query("SELECT * FROM analyst_turns", conn)
        if "analyst_turns" in tables
        else None
    )
    conn.close()
    out = flatten_qa_pairs(qa, corp)
    assert not out.empty
    assert list(out.columns) == COLUMNS
    assert out["pair_id"].is_unique
    assert out["pair_id"].ne("").all()


def test_main_writes_csv_and_sqlite_table(tmp_path, monkeypatch):
    import build_qa_browser_export as m

    qa = pd.concat(
        [
            _qa(),
            _qa(pair_id="barclays_2024-q1_001", bank="barclays", question_sentiment="positive"),
        ],
        ignore_index=True,
    )
    monkeypatch.setattr(m, "PROC", tmp_path)
    monkeypatch.setattr(m, "OUT_CSV", tmp_path / "all_qa_pairs.csv")
    monkeypatch.setattr(m, "configure", lambda **k: None)
    monkeypatch.setattr(m, "has_df", lambda n: n == "qa_pairs")
    monkeypatch.setattr(m, "load_df", lambda n: qa)
    saved = {}
    monkeypatch.setattr(m, "save_df", lambda n, df: saved.setdefault(n, df.copy()))
    m.main()
    csv_path = tmp_path / "all_qa_pairs.csv"
    assert csv_path.is_file()
    written = pd.read_csv(csv_path)
    assert list(written.columns) == COLUMNS
    assert written["pair_id"].is_unique
    assert not written.empty
    assert "qa_pairs_full" in saved
    assert len(saved["qa_pairs_full"]) == len(written)
