#!/usr/bin/env python3
"""Score Aidan's independent M2a labels against the machine dual-code.

Reads the 60-pair sample key + Aidan CSV. Does not relabel.
Writes docs/assignment2/human_labels/m2a_agreement.json
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "docs" / "assignment2" / "human_labels"
HUMAN = LAB / "m2a_aidan_labels.csv"
KEY = LAB / "sample_60_machine_key.csv"
OUT = LAB / "m2a_agreement.json"

EIGHT = {
    "capital_adequacy",
    "liquidity_funding",
    "asset_quality_credit",
    "profitability_earnings",
    "operational_efficiency",
    "market_traded_risk",
    "conduct_operational",
    "business_model_strategy",
    "untagged",
}


def _norm(s: pd.Series) -> pd.Series:
    return s.fillna("untagged").astype(str).str.strip().str.lower().replace({"": "untagged", "nan": "untagged"})


def agreement(a: pd.Series, b: pd.Series) -> dict:
    same = a == b
    n = int(len(a))
    n_agree = int(same.sum())
    return {
        "n": n,
        "n_agree": n_agree,
        "pct": round(n_agree / n, 4) if n else None,
    }


def main() -> None:
    human = pd.read_csv(HUMAN)
    key = pd.read_csv(KEY)
    df = key.merge(human, on="pair_id", how="inner", validate="one_to_one")
    if len(df) != 60:
        raise SystemExit(f"expected 60 merged rows, got {len(df)}")

    aidan = _norm(df["aidan_pair"])
    c1 = _norm(df["coder1_category"])
    c2 = _norm(df["coder2_category"])
    scored = df[aidan.isin(EIGHT) & c1.isin(EIGHT)].copy()
    aidan_s = _norm(scored["aidan_pair"])
    c1_s = _norm(scored["coder1_category"])

    conf = (
        pd.crosstab(c1_s, aidan_s, dropna=False)
        .reindex(index=sorted(EIGHT), columns=sorted(EIGHT), fill_value=0)
    )
    disagree_cols = [
        c
        for c in [
            "pair_id",
            "bank",
            "quarter",
            "coder1_category",
            "coder2_category",
            "aidan_pair",
            "aidan_q",
            "aidan_confidence",
        ]
        if c in scored.columns
    ]
    disagreements = scored.loc[c1_s != aidan_s, disagree_cols]

    low = int((df["aidan_confidence"].astype(str) == "low").sum())
    usable = df[df["aidan_confidence"].astype(str) != "low"]
    usable_block = agreement(_norm(usable["aidan_pair"]), _norm(usable["coder1_category"]))

    summary = {
        "n_sample": int(len(df)),
        "n_low_confidence": low,
        "n_usable_not_low": int(len(usable)),
        "machine_coder1_vs_aidan_pair": agreement(c1, aidan),
        "machine_coder1_vs_aidan_pair_excluding_low_confidence": usable_block,
        "machine_coder2_vs_aidan_pair": agreement(c2, aidan),
        "machine_coder1_vs_coder2": agreement(c1, c2),
        "aidan_q_vs_aidan_a": agreement(_norm(df["aidan_q"]), _norm(df["aidan_a"])),
        "m4_bar": "60-pair sample; 70% human agreement is the M4/M7 evaluation bar, not a method claim",
        "confusion_coder1_rows_aidan_cols": conf.to_dict(),
        "n_disagreements_coder1_vs_aidan": int(len(disagreements)),
        "disagreement_pair_ids": disagreements["pair_id"].tolist(),
        "pitch_line": None,
    }
    mm = summary["machine_coder1_vs_coder2"]["pct"]
    p = summary["machine_coder1_vs_aidan_pair"]["pct"]
    summary["pitch_line"] = (
        f"Machine coder1 vs coder2 on n={summary['n_sample']}: {mm:.0%}. "
        f"The 8-way does not stabilize even without a human. "
        f"Aidan vs coder1 is {p:.0%} (below 70%)."
    )
    OUT.write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: summary[k] for k in summary if k != "confusion_coder1_rows_aidan_cols"}, indent=2))
    print(f"wrote {OUT}")
    print("disagreements:")
    print(disagreements.to_string(index=False))


if __name__ == "__main__":
    main()
