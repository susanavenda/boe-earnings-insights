#!/usr/bin/env python3
"""M4: FinBERT on question_text and answer_text separately (Neutral kept)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from store import configure, load_df, save_df  # noqa: E402

_SIGN = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}


def _score(pipeline, texts: list[str], batch_size: int = 8) -> tuple[list[str], list[float]]:
    labels, scores = [], []
    texts = [str(t) if pd.notna(t) else "" for t in texts]
    for i in range(0, len(texts), batch_size):
        chunk = texts[i : i + batch_size]
        # empty strings → skip the model
        nonempty_idx = [j for j, t in enumerate(chunk) if t.strip()]
        results = [None] * len(chunk)
        if nonempty_idx:
            batch = [chunk[j] for j in nonempty_idx]
            out = pipeline(batch)
            for j, r in zip(nonempty_idx, out):
                results[j] = r
        for r in results:
            if r is None:
                labels.append("")
                scores.append(0.0)
            else:
                labels.append(str(r["label"]).lower())
                scores.append(float(r["score"]))
    return labels, scores


def score_frame(qa: pd.DataFrame) -> pd.DataFrame:
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline

    tok = AutoTokenizer.from_pretrained("ProsusAI/finbert", local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert", local_files_only=True)
    pipe = pipeline("text-classification", model=model, tokenizer=tok, truncation=True, max_length=512)

    q_lab, q_sc = _score(pipe, qa["question_text"].tolist())
    a_lab, a_sc = _score(pipe, qa["answer_text"].tolist())
    out = qa.copy()
    out["question_sentiment"] = q_lab
    out["question_score"] = q_sc
    out["question_net"] = [_SIGN.get(l, 0.0) * s for l, s in zip(q_lab, q_sc)]
    out["answer_sentiment"] = a_lab
    out["answer_score"] = a_sc
    out["answer_net"] = [_SIGN.get(l, 0.0) * s for l, s in zip(a_lab, a_sc)]
    return out


def main(*, configure_store: bool = True) -> None:
    if configure_store:
        configure(memory=False)
    qa = load_df("qa_pairs")
    if qa is None or qa.empty:
        raise SystemExit("qa_pairs missing — run scripts/build_a1_evidence.py first")
    scored = score_frame(qa)
    save_df("qa_pairs", scored)
    save_df("behavioural_signals", scored)
    ss = load_df("state_summary")
    if ss is not None and not ss.empty:
        extra = scored.groupby(["bank", "quarter"], as_index=False).agg(
            mean_question_net=("question_net", "mean"),
            mean_answer_net=("answer_net", "mean"),
        )
        keep = [c for c in ss.columns if c not in extra.columns or c in ("bank", "quarter")]
        ss = ss[keep].merge(extra, on=["bank", "quarter"], how="left")
        save_df("state_summary", ss)
    qn = scored["question_sentiment"].replace("", pd.NA).value_counts(dropna=False)
    an = scored["answer_sentiment"].replace("", pd.NA).value_counts(dropna=False)
    print("question labels\n", qn.to_string())
    print("answer labels\n", an.to_string())
    print("scored pairs", len(scored))


if __name__ == "__main__":
    main()
