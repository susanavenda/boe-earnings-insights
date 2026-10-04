#!/usr/bin/env python3
"""Flatten scored Q&A pairs for the desk Browse tab.

Does not model. Selects columns already on ``qa_pairs`` (and, when present,
BERTopic ``topic`` on matching ``corpus_analyst`` turns). Pair-level FinBERT /
LDSA on this table are the *question* scores already written by Stage 3.

Writes ``data/processed/all_qa_pairs.csv`` and ``qa_pairs_full`` in sqlite.
Does not touch ``EPISODES`` or protocol verdicts.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from periods import calendar_period  # noqa: E402
from store import configure, has_df, load_df, save_df  # noqa: E402

PROC = ROOT / "data" / "processed"
OUT_CSV = PROC / "all_qa_pairs.csv"

COLUMNS = [
    "pair_id",
    "bank",
    "quarter",
    "calendar_period",
    "question_text",
    "answer_text",
    "finbert_sentiment",
    "ldsa_sentiment",
    "topic_id",
    "directness",
    "topic_substitution",
]


def _pick(df: pd.DataFrame, *names: str):
    for n in names:
        if n in df.columns:
            return df[n]
    return pd.Series([pd.NA] * len(df), index=df.index)


def flatten_qa_pairs(qa: pd.DataFrame, corpus: pd.DataFrame | None = None) -> pd.DataFrame:
    """Select and rename; never invent a score or a protocol verdict."""
    if qa is None or qa.empty:
        return pd.DataFrame(columns=COLUMNS)
    out = pd.DataFrame(index=qa.index)
    out["pair_id"] = _pick(qa, "pair_id")
    out["bank"] = _pick(qa, "bank")
    out["quarter"] = _pick(qa, "quarter")
    out["calendar_period"] = out["quarter"].map(calendar_period)
    out["question_text"] = _pick(qa, "question_text")
    out["answer_text"] = _pick(qa, "answer_text")
    out["finbert_sentiment"] = _pick(qa, "finbert_sentiment", "question_sentiment")
    out["ldsa_sentiment"] = _pick(qa, "ldsa_sentiment", "question_ldsa_sentiment")
    out["topic_id"] = _pick(qa, "topic_id", "topic")
    out["directness"] = _pick(qa, "directness")
    out["topic_substitution"] = _pick(qa, "topic_substitution")
    out = out[COLUMNS]
    out = out[out["pair_id"].notna() & (out["pair_id"].astype(str).str.strip() != "")]
    out["pair_id"] = out["pair_id"].astype(str)
    out = out.drop_duplicates("pair_id", keep="first").reset_index(drop=True)

    if (
        corpus is not None
        and not corpus.empty
        and {"bank", "quarter", "text", "topic"}.issubset(corpus.columns)
        and out["topic_id"].isna().all()
    ):
        keys = corpus[["bank", "quarter", "text", "topic"]].copy()
        keys["text"] = keys["text"].astype(str).str.strip()
        keys = keys.drop_duplicates(["bank", "quarter", "text"], keep="first")
        tmp = out.copy()
        tmp["_q"] = tmp["question_text"].astype(str).str.strip()
        merged = tmp.merge(
            keys,
            left_on=["bank", "quarter", "_q"],
            right_on=["bank", "quarter", "text"],
            how="left",
        )
        merged = merged.drop_duplicates("pair_id", keep="first")
        out["topic_id"] = merged["topic"].to_numpy()

    return out


def main() -> None:
    configure(memory=False)
    if not has_df("qa_pairs"):
        raise SystemExit("qa_pairs missing — run Stage 1.5 / Stage 3 first")
    qa = load_df("qa_pairs")
    corp = load_df("corpus_analyst") if has_df("corpus_analyst") else None
    out = flatten_qa_pairs(qa, corp)
    PROC.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False)
    save_df("qa_pairs_full", out)
    print(f"qa_pairs_full {len(out)} unique pair_id → {OUT_CSV}")


if __name__ == "__main__":
    main()
