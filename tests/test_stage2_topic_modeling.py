"""Tests for Stage 2 (topic modeling) issues found in PR #55.

Run: pytest tests/test_stage2_topic_modeling.py -v -m "not slow"
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import pytest

from topic_modeling import clean_timestamp as _clean_timestamp

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = ROOT / "notebooks" / "boe_earnings_insights.ipynb"

SYNTHETIC_DOCS = [
    "our net interest income grew this quarter on higher rates",
    "total income was up driven by strong net interest income",
    "credit impairment charges rose due to a weaker macro outlook",
    "we saw higher loan loss provisions this quarter",
    "operating costs increased due to inflation and investment spend",
    "cost to income ratio worsened slightly this period",
    "our CET1 capital ratio remains well above regulatory minimums",
    "capital ratios stayed strong with CET1 comfortably above target",
] * 4


class TestCleanTimestamp:
    """Numbered quarters stay ordered; interim/annual must not collapse onto Q1."""

    def test_numbered_quarters_parse_and_order_correctly(self):
        q1 = _clean_timestamp("2024-q1")
        q2 = _clean_timestamp("2024-q2")
        q3 = _clean_timestamp("2024-q3")
        q4 = _clean_timestamp("2024-q4")
        assert q1 < q2 < q3 < q4, "numbered quarters out of chronological order"

    def test_interim_does_not_collide_with_q1(self):
        q1 = _clean_timestamp("2024-q1")
        interim = _clean_timestamp("2024-interim")
        assert q1 != interim, (
            f"'interim' collapsed onto the same date as Q1: both = {q1}. "
            "HSBC's interim/annual labels need their own month mapping, "
            "not a fallback to Jan 1."
        )

    def test_no_two_distinct_quarters_collapse_onto_the_same_date(self):
        labels = [
            "2024-q1",
            "2024-q2",
            "2024-q3",
            "2024-q4",
            "2024-interim",
            "2024-annual",
        ]
        seen: dict[pd.Timestamp, str] = {}
        for label in labels:
            d = _clean_timestamp(label)
            assert not pd.isna(d), f"{label!r} parsed to NaT"
            assert d not in seen, (
                f"{label!r} collapsed onto the same date as {seen[d]!r}: {d}"
            )
            seen[d] = label

    def test_unparseable_date_does_not_default_to_fake_recency(self):
        result = _clean_timestamp("garbage-no-date-here")
        if result is None or pd.isna(result):
            return
        assert result.year != 2026, (
            "unparseable date silently defaulted to 2026 instead of being "
            "flagged or excluded"
        )

    @pytest.mark.parametrize("year", ["2006", "2015", "2026"])
    def test_annual_label_extracts_correct_year(self, year):
        result = _clean_timestamp(f"{year}-annual")
        assert result.year == int(year)


def _skip_unless_bertopic():
    try:
        import bertopic  # noqa: F401
    except Exception as exc:
        pytest.skip(f"bertopic unavailable: {type(exc).__name__}")


class TestBERTopicReproducibility:
    def test_topic_assignments_identical_across_two_runs(self):
        _skip_unless_bertopic()
        from topic_modeling import fit_bertopic

        _, topics_a = fit_bertopic(SYNTHETIC_DOCS, seed=42)
        _, topics_b = fit_bertopic(SYNTHETIC_DOCS, seed=42)
        assert topics_a == topics_b, (
            "same seed produced different topic assignments across two runs"
        )


class TestTopicModelInputConsistency:
    def test_lda_and_bertopic_use_the_same_input_column(self):
        from topic_modeling import (
            get_bertopic_input_column,
            get_lda_input_column,
        )

        df = pd.DataFrame(
            {
                "text": ["a"],
                "clean_text": ["a clean"],
                "llm_preprocessed_text": ["a preprocessed"],
            }
        )
        bertopic_col = get_bertopic_input_column(df)
        lda_col = get_lda_input_column(df)
        assert bertopic_col == lda_col, (
            f"BERTopic reads {bertopic_col!r} but LDA reads {lda_col!r} — "
            "they are no longer modeling the same text, so LDA is not "
            "actually a sanity check on BERTopic's input anymore"
        )


class TestMissingCleanTextFallback:
    def test_lda_does_not_raise_bare_keyerror_without_clean_text(self):
        pytest.importorskip("gensim")
        from topic_modeling import score_lda

        df = pd.DataFrame({"text": ["some analyst turn text here"]})
        try:
            score_lda(df)
        except KeyError:
            pytest.fail(
                "score_lda() raised a bare KeyError on missing 'clean_text' "
                "— should fall back to 'text' or raise a clear, named error, "
                "consistent with the existence-check pattern used elsewhere "
                "in this notebook (cell 20's target_col selection)"
            )


@pytest.mark.slow
class TestFullNotebookExecutes:
    def test_every_code_cell_has_run(self):
        import nbformat

        nb = nbformat.read(NOTEBOOK_PATH, as_version=4)
        unrun = [
            i
            for i, c in enumerate(nb.cells)
            if c.cell_type == "code" and c.get("execution_count") is None
        ]
        assert not unrun, (
            f"{len(unrun)} code cells never executed: {unrun}. "
            "A committed notebook with unrun cells can't be trusted — "
            "run top to bottom before committing."
        )

    def test_no_cell_raised_an_error(self):
        import nbformat

        nb = nbformat.read(NOTEBOOK_PATH, as_version=4)
        errors = [
            (i, o.get("ename"))
            for i, c in enumerate(nb.cells)
            if c.cell_type == "code"
            for o in c.get("outputs", [])
            if o.get("output_type") == "error"
        ]
        assert not errors, f"cells raised errors: {errors}"

    def test_notebook_executes_cleanly_from_scratch(self):
        import nbformat
        from nbclient import NotebookClient

        nb = nbformat.read(NOTEBOOK_PATH, as_version=4)
        client = NotebookClient(nb, timeout=7200, kernel_name="python3")
        client.execute()


class TestLLMPreprocessingIsExplicitOptIn:
    def test_llm_preprocessed_text_not_used_without_explicit_opt_in(self, monkeypatch):
        from topic_modeling import get_bertopic_input_column

        monkeypatch.delenv("BOE_USE_LLM_PREPROCESSING", raising=False)
        df = pd.DataFrame(
            {
                "text": ["original analyst text"],
                "clean_text": ["original cleaned text"],
                "llm_preprocessed_text": ["an LLM's paraphrase of it"],
            }
        )
        col = get_bertopic_input_column(df)
        assert col != "llm_preprocessed_text", (
            "BERTopic silently modeled LLM-paraphrased text instead of the "
            "analysts' actual words, with no explicit opt-in set. This "
            "should require BOE_USE_LLM_PREPROCESSING=1, not just the "
            "column happening to be present."
        )

    def test_llm_preprocessed_text_used_when_explicitly_enabled(self, monkeypatch):
        from topic_modeling import get_bertopic_input_column

        monkeypatch.setenv("BOE_USE_LLM_PREPROCESSING", "1")
        df = pd.DataFrame(
            {
                "text": ["original analyst text"],
                "llm_preprocessed_text": ["an LLM's paraphrase of it"],
            }
        )
        col = get_bertopic_input_column(df)
        assert col == "llm_preprocessed_text"


class TestSectionHeadersMatchTitles:
    def test_no_cell_displays_the_wrong_stage_number(self):
        nb = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
        mismatches = []
        for i, c in enumerate(nb["cells"]):
            if c["cell_type"] != "code":
                continue
            src = "".join(c["source"])
            title_match = re.search(r"@title\s+(.+)", src)
            header_match = re.search(r"section_header\(\s*'([^']+)'", src)
            if not (title_match and header_match):
                continue
            stage_num = re.search(r"(\d+\.\d+)", title_match.group(1))
            header_num = re.search(r"Stage\s+(\d+\.\d+)", header_match.group(1))
            if stage_num and header_num and stage_num.group(1) != header_num.group(1):
                mismatches.append(
                    f"cell {i}: @title says {stage_num.group(1)!r} but "
                    f"section_header displays {header_num.group(1)!r}"
                )
        assert not mismatches, "\n".join(mismatches)


class TestTopicModelReloadsInFreshKernel:
    def test_missing_topic_model_is_rebuilt_not_a_nameerror(self):
        _skip_unless_bertopic()
        from topic_modeling import get_or_rebuild_topic_model

        try:
            model, topics = get_or_rebuild_topic_model(SYNTHETIC_DOCS)
        except NameError:
            pytest.fail(
                "jumping straight to the temporal-drift stage in a fresh "
                "kernel raises NameError instead of rebuilding topic_model "
                "— inconsistent with lda_model's guard in cell 28"
            )
        assert model is not None
        assert len(topics) == len(SYNTHETIC_DOCS)


class TestMinTopicSizeScalesWithCorpus:
    @pytest.mark.parametrize(
        "n_docs,max_expected",
        [
            (200, 10),
            (1_000, 25),
            (4_000, 60),
        ],
    )
    def test_min_topic_size_grows_with_corpus_size(self, n_docs, max_expected):
        from topic_modeling import get_min_topic_size

        size = get_min_topic_size(n_docs)
        assert size <= max_expected, (
            f"min_topic_size={size} for n_docs={n_docs} looks unbounded, "
            f"expected something under {max_expected}"
        )

    def test_min_topic_size_is_not_constant_across_very_different_corpus_sizes(self):
        from topic_modeling import get_min_topic_size

        small = get_min_topic_size(200)
        large = get_min_topic_size(4_000)
        assert small != large, (
            f"min_topic_size is {small} for both a 200-row and a 4,000-row "
            "corpus — the cap is masking the size-based formula entirely"
        )


class TestTemporalBinningGranularity:
    def test_bin_width_is_no_coarser_than_one_quarter(self):
        from topic_modeling import get_nr_bins

        date_min = pd.Timestamp("2006-01-01")
        date_max = pd.Timestamp("2026-01-01")
        nr_bins = get_nr_bins(date_min, date_max, target_granularity="quarter")

        span_days = (date_max - date_min).days
        bin_width_days = span_days / nr_bins
        assert bin_width_days <= 95, (
            f"nr_bins={nr_bins} over a {span_days}-day range gives a bin "
            f"width of {bin_width_days:.0f} days — coarser than one quarter, "
            "so quarter-to-quarter topic disappearance won't be visible"
        )


class TestFiguresAreSavedNotJustShown:
    def test_every_show_call_is_routed_through_show_plt(self):
        nb = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
        unsaved = []
        for i, c in enumerate(nb["cells"]):
            if c["cell_type"] != "code":
                continue
            src = "".join(c["source"])
            show_calls = re.findall(r"(\w+)\.show\(\)", src)
            saved_vars = re.findall(r"_show_plt\(\s*(\w+)", src)
            for var in show_calls:
                if var not in saved_vars:
                    unsaved.append(f"cell {i}: '{var}.show()' bypasses _show_plt()")
        assert not unsaved, "\n".join(unsaved)
