"""Read the four locked KPIs from an HSBC quarterly data pack.

HSBC changed the pack layout twice, so one sheet name is not enough:

  2014 Q1 - 2018 Q3   sheet "HSBC Group"                (no CET1 ratio in the pack)
  2018 Q4 - 2020 Q1   sheet "Group - Income Statement"  + "Group - Balance Sheet"
  2020 Q2 onwards     sheet "Group income statement"    + "Group balance sheet"

Labels change too: footnote digits ("Total operating expenses1"), and IAS 39
"loan impairment charges" before IFRS 9 "change in expected credit losses"
(2018). Each metric returns (current quarter, previous quarter): the first two
numbers on the row, because every layout lists quarters newest first.

Reported figures, not adjusted: the reported block is the first one in every
layout from 2014 to 2026, so the series is consistent. (The old notebook parser
kept the last row with a matching label, which was the adjusted block in the
2020 Q2 - 2022 packs only.) Two packs (2016 Q4, 2018 Q2) are in $ instead of
$m; values are rescaled to $m.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

INCOME_SHEETS = ("groupincomestatement", "hsbcgroup")
BALANCE_SHEETS = ("groupbalancesheet",)

# First matching row wins, so list the preferred label first.
PATTERNS: dict[str, list[str]] = {
    "total_income": [r"^net operating income.*\bbefore\b"],
    "credit_impairment": [
        r"^change in expected credit losses",
        r"^loan impairment.*credit risk provisions",
    ],
    "operating_costs": [r"^total operating expenses"],
    "cet1_ratio": [r"^common equity tier 1 ratio", r"^cet1 ratio"],
}


def _sheet_key(name: str) -> str:
    return re.sub(r"[^a-z]", "", str(name).lower())


def _find_sheet(sheet_names, wanted) -> str | None:
    keys = {_sheet_key(s): s for s in sheet_names}
    for w in wanted:
        if w in keys:
            return keys[w]
    return None


def _label(value) -> str:
    s = re.sub(r"\s+", " ", str(value).replace("\n", " ")).strip().lower()
    return re.sub(r"\d+$", "", s).strip()  # footnote markers: "expenses1"


def _numbers(row) -> list[float]:
    out = []
    for v in row:
        if isinstance(v, bool) or not isinstance(v, (int, float)) or pd.isna(v):
            continue
        out.append(float(v))
    return out


def _scan(df: pd.DataFrame, metrics, stop_at_constant_currency: bool = True) -> dict:
    found: dict[str, tuple[float, float]] = {}
    for _, row in df.iterrows():
        lab = row.iloc[0]
        if pd.isna(lab):
            continue
        s = _label(lab)
        if stop_at_constant_currency and s.startswith("constant currency"):
            break  # later income sections restate the same lines
        nums = _numbers(row.iloc[1:].tolist())
        if len(nums) < 2:
            continue
        for metric in metrics:
            if metric in found:
                continue
            if any(re.search(p, s) for p in PATTERNS[metric]):
                found[metric] = (nums[0], nums[1])
    return found


def parse_hsbc_datapack(path) -> dict:
    """{metric: (current, previous)} for the metrics this pack carries."""
    xl = pd.ExcelFile(path)
    income = _find_sheet(xl.sheet_names, INCOME_SHEETS)
    if income is None:
        raise ValueError(f"no group income sheet in {Path(path).name}: {xl.sheet_names}")
    out = _scan(pd.read_excel(xl, sheet_name=income, header=None),
                ("total_income", "credit_impairment", "operating_costs", "cet1_ratio"))
    balance = _find_sheet(xl.sheet_names, BALANCE_SHEETS)
    if balance is not None and "cet1_ratio" not in out:
        # CET1 sits below the constant-currency block in the 2023+ balance sheets.
        out.update(_scan(pd.read_excel(xl, sheet_name=balance, header=None), ("cet1_ratio",),
                         stop_at_constant_currency=False))
    for metric in ("total_income", "credit_impairment", "operating_costs"):
        vals = out.get(metric)
        if vals is not None and max(abs(vals[0]), abs(vals[1])) > 1e7:  # $ not $m
            out[metric] = (vals[0] / 1e6, vals[1] / 1e6)
    # IFRS 9 started in 2018 Q1: the prior quarter has no ECL figure (0), so
    # there is no like-for-like comparison. Drop it rather than call it "flat".
    imp = out.get("credit_impairment")
    if imp is not None and imp[1] == 0:
        del out["credit_impairment"]
    return out
