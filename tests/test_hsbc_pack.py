"""HSBC data packs: all three layouts parse (2014 Q1 - 2026 Q2)."""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("openpyxl")

from hsbc_pack import parse_hsbc_datapack  # noqa: E402

PACKS = Path(__file__).resolve().parents[1] / "data" / "structured" / "hsbc"


def _pack(name: str) -> Path:
    path = PACKS / f"{name}-data-pack.xlsx"
    if not path.exists():
        pytest.skip(f"{path.name} not in this checkout")
    return path


def test_every_hsbc_pack_parses():
    paths = sorted(PACKS.glob("*.xlsx"))
    if not paths:
        pytest.skip("no HSBC packs in this checkout")
    failed = []
    for path in paths:
        try:
            out = parse_hsbc_datapack(path)
        except Exception as exc:  # noqa: BLE001
            failed.append(f"{path.name}: {exc}")
            continue
        if not {"total_income", "operating_costs"} <= set(out):
            failed.append(f"{path.name}: missing income/costs ({sorted(out)})")
    assert not failed, failed


def test_pre_2018_layout_hsbc_group_sheet():
    out = parse_hsbc_datapack(_pack("2014-1q"))
    assert out["total_income"] == (15884.0, 15195.0)
    assert out["credit_impairment"] == (-798.0, -1140.0)  # IAS 39 loan impairment charges
    assert out["operating_costs"] == (-8852.0, -10573.0)
    assert "cet1_ratio" not in out  # not in pre-2018 packs


def test_2018q4_layout_hyphenated_sheets_and_footnotes():
    out = parse_hsbc_datapack(_pack("2018-4q"))
    assert out["total_income"] == (12695.0, 13798.0)
    assert out["credit_impairment"] == (-853.0, -507.0)
    assert out["operating_costs"] == (-9144.0, -7966.0)  # label is "Total operating expenses1"
    assert out["cet1_ratio"] == (0.14, 0.143)


def test_current_layout_uses_reported_not_adjusted():
    out = parse_hsbc_datapack(_pack("2021-1q"))
    assert out["total_income"] == (12986.0, 11757.0)  # adjusted block would give 13273
    assert out["operating_costs"] == (-8527.0, -9864.0)


def test_cet1_found_below_constant_currency_block():
    assert "cet1_ratio" in parse_hsbc_datapack(_pack("2023-1q"))


def test_ifrs9_transition_quarter_has_no_impairment_direction():
    assert "credit_impairment" not in parse_hsbc_datapack(_pack("2018-1q"))


def test_packs_in_dollars_are_rescaled_to_millions():
    out = parse_hsbc_datapack(_pack("2016-4q"))
    assert out["total_income"] == (8984.0, 9512.0)

