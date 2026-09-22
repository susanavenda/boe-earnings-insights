#!/usr/bin/env python3
"""M4: FinBERT on question_text and answer_text separately (Neutral kept).

Thin wrapper over ``scripts/sentiment.py`` so the notebook (Stage 3.1b) and the CLI
score Q&A pairs identically: turn unit (legacy ``question_sentiment / _score / _net``
and ``answer_*``), sentence unit (``*_sent_*``) and Loughran–McDonald (``*_ldsa_*``,
``*_lm_hedge``).

Usage:  python scripts/score_qa_sentiment.py [--unit both|turn|sentence] [--device cpu]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from sentiment import FINBERT, FinBertScorer, LMScorer, score_qa  # noqa: E402
from store import configure, has_df, load_df, save_df  # noqa: E402


def score_frame(
    qa: pd.DataFrame,
    *,
    unit: str = "both",
    model: str = FINBERT,
    device: str | None = None,
    all_turns: pd.DataFrame | None = None,
    batch_size: int = 16,
) -> pd.DataFrame:
    """Return ``qa`` with question_* / answer_* sentiment columns (see sentiment.py)."""
    if all_turns is None and has_df("all_turns"):
        all_turns = load_df("all_turns")
    scorer = FinBertScorer(model, device=device, batch_size=batch_size)
    return score_qa(qa, all_turns=all_turns, scorer=scorer, lm=LMScorer("lm"), unit=unit)


def main(*, configure_store: bool = True, unit: str = "both", device: str | None = None) -> None:
    if configure_store:
        configure(memory=False)
    qa = load_df("qa_pairs")
    if qa is None or qa.empty:
        raise SystemExit("qa_pairs missing — run scripts/build_a1_evidence.py first")
    scored = score_frame(qa, unit=unit, device=device)
    save_df("qa_pairs", scored)
    save_df("behavioural_signals", scored)
    if has_df("state_summary"):
        ss = load_df("state_summary")
        agg = {"mean_question_net": ("question_net", "mean"), "mean_answer_net": ("answer_net", "mean")}
        if "answer_sent_net" in scored.columns:
            agg["mean_question_sent_net"] = ("question_sent_net", "mean")
            agg["mean_answer_sent_net"] = ("answer_sent_net", "mean")
        if "answer_lm_hedge" in scored.columns:
            agg["mean_answer_hedge"] = ("answer_lm_hedge", "mean")
        extra = scored.groupby(["bank", "quarter"], as_index=False).agg(**agg)
        keep = [c for c in ss.columns if c not in extra.columns or c in ("bank", "quarter")]
        save_df("state_summary", ss[keep].merge(extra, on=["bank", "quarter"], how="left"))
    for col in ("question_sentiment", "answer_sentiment", "question_sent_label", "answer_sent_label"):
        if col in scored.columns:
            print(col, scored[col].replace("", pd.NA).value_counts(dropna=False).to_dict())
    print("scored pairs", len(scored))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--unit", default="both", choices=["turn", "sentence", "both"])
    ap.add_argument("--device", default=None)
    a = ap.parse_args()
    main(unit=a.unit, device=a.device)
