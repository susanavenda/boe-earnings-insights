"""Stage 6 — temporal / peer / structured-vs-unstructured. Peer gap is HSBC−Barclays."""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pandas as pd
import pytest

from periods import matched_peer_gap

HSBC_PACKS = Path(__file__).resolve().parents[1] / "data" / "structured" / "hsbc"


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


def _hsbc_parser(nb):
    wanted = {"_norm", "_to_float", "_first_match", "_hsbc_sheet", "parse_hsbc_datapack"}
    for cell in nb["cells"]:
        src = "".join(cell.get("source") or [])
        if cell.get("cell_type") == "code" and "def parse_hsbc_datapack" in src:
            tree = ast.parse(src)
            defs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
            ns = {"re": re, "pd": pd}
            exec(compile(ast.Module(body=defs, type_ignores=[]), "stage6.3", "exec"), ns)
            return ns["parse_hsbc_datapack"]
    raise AssertionError("parse_hsbc_datapack not found in the notebook")


@pytest.mark.skipif(not HSBC_PACKS.exists(), reason="HSBC data packs not present")
def test_hsbc_parser_reads_2018q4_layout_and_the_reported_block(nb):
    parse = _hsbc_parser(nb)

    old_layout = parse(HSBC_PACKS / "2018-4q-data-pack.xlsx")
    assert old_layout["total_income"] == (12695.0, 13798.0)
    assert old_layout["credit_impairment"] == (-853.0, -507.0)
    assert old_layout["operating_costs"] == (-9144.0, -7966.0)
    assert old_layout["cet1_ratio"] == (0.14, 0.143)

    # 2020 Q2 also prints an 'Adjusted ($m)' block (13,150); the reported figure is 13,059.
    assert parse(HSBC_PACKS / "2020-2q-data-pack.xlsx")["total_income"] == (13059.0, 13686.0)

    with pytest.raises(ValueError):
        parse(HSBC_PACKS / "2017-4q-data-pack.xlsx")
