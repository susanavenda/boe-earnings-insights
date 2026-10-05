"""#90 — Barclays packs whose layout or period the old fixed-layout parser got wrong."""
from __future__ import annotations

import pandas as pd
import pytest

import reported_metrics as rm

BARCLAYS = rm.STRUCTURED_ROOT / "barclays"

# Figures read off each workbook by hand: (current, prior) in £m.
EXPECTED = {
    # Values two columns right of the label (Notes / spacer columns in between).
    "2009-h1": {"total_income": (16253, 11843), "operating_costs": (-8747, -6753), "credit_impairment": (-4556, -2448)},
    "2011-q3": {"total_income": (25213, 22872), "operating_costs": (-14488, -14476), "credit_impairment": (-2851, -4298)},
    # Statutory sheets with a Notes column; net-of-insurance income, not gross or the note number.
    "2011-fy": {"total_income": (32292, 31440), "operating_costs": (-20777, -19971), "credit_impairment": (-3802, -5672)},
    "2012-fy": {"total_income": (24691, 32292), "operating_costs": (-20989, -20777), "credit_impairment": (-3596, -3802)},
    # Total income stored as text ("31,440 ").
    "2010-fy": {"total_income": (31440, 29123)},
}

# CET1 from the capital block on the summary sheet (2013-15 packs).
CET1 = {"2014-q1": (0.0962, 0.093), "2014-fy": (0.103, 0.0913), "2015-fy": (0.1135, 0.1031)}


def _parse(stem: str) -> dict:
    path = BARCLAYS / f"{stem}-financial-tables.xlsx"
    if not path.is_file():
        pytest.skip(f"{path} not present")
    return rm.parse_barclays_group_ph(path)


@pytest.mark.parametrize("stem", sorted(EXPECTED))
def test_older_layouts_parse(stem):
    got = _parse(stem)
    for metric, want in EXPECTED[stem].items():
        assert got[metric] == pytest.approx(want), metric


@pytest.mark.parametrize("stem", sorted(CET1))
def test_cet1_found_on_summary_sheet(stem):
    assert _parse(stem)["cet1_ratio"] == pytest.approx(CET1[stem], abs=1e-4)


def test_core_tier_1_is_not_read_as_cet1():
    # Pre-Basel III packs print Core Tier 1 only; that is a different measure.
    assert _parse("2011-q3")["cet1_ratio"] is None


# Both workbooks put the 2013 FY tables first and the H1 tables after them.
H1 = {
    "2014-h1": {"total_income": (13332.128, 15071), "credit_impairment": (-1086, -1631), "cet1_ratio": (0.099, 0.091)},
    "2015-h1": {"total_income": (12982, 13332), "credit_impairment": (-973, -1086), "cet1_ratio": (0.111, 0.103)},
}


@pytest.mark.parametrize("stem", sorted(H1))
def test_h1_read_from_the_h1_sheet_not_the_2013_tables(stem):
    got = _parse(stem)
    for metric, want in H1[stem].items():
        assert got[metric] == pytest.approx(want, abs=1e-3), metric


def test_pack_without_a_sheet_for_its_period_is_skipped(tmp_path, capsys):
    path = tmp_path / "2014-h1-financial-tables.xlsx"
    pd.DataFrame(
        [["Perf Highlights", "31.12.13", "31.12.12"], [None, "£m", "£m"], ["Total income", 28155, 29361]]
    ).to_excel(path, sheet_name="Perf Highlights", header=False, index=False)
    assert rm.parse_barclays_group_ph(path) == {}
    assert "header period ends 2013-12-31, filename says 2014-06-30" in capsys.readouterr().out


def test_excel_lock_files_are_ignored(tmp_path, capsys):
    (tmp_path / "barclays").mkdir()
    (tmp_path / "barclays" / "~$2014-h1-financial-tables.xlsx").write_bytes(b"lock")
    assert rm.build_reported_metrics(tmp_path).empty
    assert "WARN" not in capsys.readouterr().out


def test_to_float_reads_numbers_stored_as_text():
    assert rm._to_float("31,440 ") == 31440.0
    assert rm._to_float("-1,234.5") == -1234.5
    for not_a_number in ("nm", "-", "30.09.11", "£m", "Notes1"):
        assert rm._to_float(not_a_number) is None


@pytest.mark.parametrize(
    "rows, want",
    [
        # Label, Notes, current, prior (2011-12 statutory income statement).
        ([["Income statement", None, None, None], [None, "Notes", "£m", "£m"],
          ["Total income", 2, 32292, 31440]], (0, 2, 3)),
        # Label, spacer, current, spacer, prior (2011 Q3).
        ([["Results", None, None, None, None], [None, None, "£m", None, "£m"],
          ["Total income", None, 25213, None, 22872]], (0, 2, 4)),
        # Group PH: label in column 1 (2016 onwards).
        ([[None, "Group results", None, None], [None, None, "£m", "£m"],
          [None, "Total income", 21451, 22040]], (1, 2, 3)),
        # No £m heading: fall back to the fixed layouts.
        ([["Total income", 1, 2]], None),
    ],
)
def test_header_layout_finds_label_and_value_columns(rows, want):
    assert rm._header_layout(pd.DataFrame(rows)) == want


def test_first_header_date_reads_text_and_datetime_headers():
    assert rm._first_header_date(pd.DataFrame([["Group", "30.09.11", "30.09.10"]])) == "2011-09-30"
    assert rm._first_header_date(pd.DataFrame([[None, pd.Timestamp("2024-12-31")]])) == "2024-12-31"
    assert rm._first_header_date(pd.DataFrame([["no dates here"]])) is None
