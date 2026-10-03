"""Execute the actual Colab helper cell; no GPU or network is required."""
import pytest
import pandas as pd
import numpy as np


@pytest.fixture
def helpers(nb, monkeypatch):
    monkeypatch.delenv("BOE_USE_ABSTRACTIVE_SUMMARIES", raising=False)
    cell = next(c for c in nb["cells"] if "4.1 Metric brief helpers" in "".join(c.get("source", [])))
    namespace = {"pd": pd, "section_header": lambda *a, **k: None, "insight": lambda *a, **k: None}
    exec("".join(cell["source"]), namespace)
    return namespace


def test_numeric_guidance_without_metric_is_not_evidence(helpers):
    text = "We expect 3% growth and 5% improvement next year. Operating costs remain stable this quarter."
    assert helpers["_best_evidence"](text, "operating_costs") == "Operating costs remain stable this quarter."


def test_absence_has_no_quality_score(helpers):
    brief = helpers["build_metric_brief"]({"question_text": "Hello", "answer_text": "Thank you"}, "cet1_ratio")
    assert brief["brief_status"] == "not_discussed"
    assert brief["faithfulness_support"] is None
    assert brief["numbers_preserved"] is None


@pytest.mark.parametrize("candidate", [
    "Operating costs rose this quarter overall.",
    "Operating costs rose 9% this quarter overall.",
])
def test_optional_polish_rejects_lost_or_invented_numbers(helpers, monkeypatch, candidate):
    monkeypatch.setenv("BOE_USE_ABSTRACTIVE_SUMMARIES", "1")
    helpers["_GENERATOR"] = lambda *a, **k: [{"summary_text": candidate}]
    original = "Operating costs rose 3% this quarter overall."
    result = helpers["_optional_abstractive"](original, original, "operating_costs")
    assert result[0] == original
    assert result[1] == "extractive_fallback"


def test_optional_polish_can_keep_supported_numbers(helpers, monkeypatch):
    monkeypatch.setenv("BOE_USE_ABSTRACTIVE_SUMMARIES", "1")
    original = "Operating costs rose 3% this quarter overall."
    helpers["_GENERATOR"] = lambda *a, **k: [{"summary_text": original}]
    assert helpers["_optional_abstractive"](original, original, "operating_costs")[1] == "extractive+distilbart_gated"


@pytest.mark.parametrize("missing", [None, float("nan"), pd.NA])
def test_missing_answer_is_unanswered(helpers, missing):
    row = {"question_text": "What is the CET1 ratio this quarter?", "answer_text": missing}
    brief = helpers["build_metric_brief"](row, "cet1_ratio")
    assert brief["brief_status"] == "unanswered"
    assert brief["needs_review"]


def test_polish_cannot_import_unselected_figures(helpers, monkeypatch):
    monkeypatch.setenv("BOE_USE_ABSTRACTIVE_SUMMARIES", "1")
    original = "Operating costs rose 3% this quarter overall."
    candidate = "Operating costs rose 3% this quarter overall, compared with 9%."
    helpers["_GENERATOR"] = lambda *a, **k: [{"summary_text": candidate}]
    source = original + " Income rose 9% compared with last year."
    assert helpers["_optional_abstractive"](original, source, "operating_costs")[1] == "extractive_fallback"


def test_stage4_tables_round_trip_and_review_keys(helpers, nb, tmp_path):
    import sqlite3
    rows = pd.DataFrame([
        {"pair_id": "a", "bank": "hsbc", "quarter": "2025-interim", "question_text": "What is the CET1 ratio this quarter?", "answer_text": "The CET1 ratio is 14% this quarter overall."},
        {"pair_id": "b", "bank": "barclays", "quarter": "2025-q2", "question_text": "What is the CET1 ratio this quarter?", "answer_text": None},
        {"pair_id": "c", "bank": "hsbc", "quarter": "2025-interim", "question_text": "Hello", "answer_text": "Thank you"},
    ])
    with sqlite3.connect(tmp_path / "summary.sqlite") as connection:
        helpers.update({"np": np, "_df": lambda name: rows.copy(),
                        "_save": lambda name, frame: frame.to_sql(name, connection, if_exists="replace", index=False),
                        "kpi_row": lambda *a, **k: None, "display_table": lambda *a, **k: None})
        for title in ["4.2 Build briefs", "4.3 Coverage, quality"]:
            cell = next(c for c in nb["cells"] if title in "".join(c.get("source", [])))
            exec("".join(cell["source"]), helpers)
        queue = pd.read_sql_query("SELECT * FROM summary_review_queue", connection)
        assert len(queue) == 2
        assert queue[["bank", "metric"]].notna().all().all()
        assert set(queue["pair_id"]) == {"a", "b"}
        assert queue["human_faithful"].isna().all()
        coverage = pd.read_sql_query("SELECT * FROM summary_coverage", connection)
        assert len(coverage) == 12
        absent = coverage[coverage["brief_status"] == "not_discussed"]
        assert absent[["faithfulness_support", "numbers_preserved"]].isna().all().all()
        quality = pd.read_sql_query("SELECT * FROM summary_quality", connection)
        assert quality.loc[quality["metric"] == "total_income", "mean_support"].isna().all()
