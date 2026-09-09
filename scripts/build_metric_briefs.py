#!/usr/bin/env python3
"""Faithful metric briefs for episode windows (extractive + optional generative).

Default path is extractive (no GPU): pick source sentences mentioning the metric,
score overlap with the source, and attach FinBERT tone. Set USE_GEN=1 to try a
small seq2seq model (DistilBART); Phi-4 is optional and heavy.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"

METRIC_LABELS = {
    "total_income": "total income / NII / revenue",
    "operating_costs": "operating costs / efficiency",
    "credit_impairment": "credit impairment / ECL",
    "cet1_ratio": "CET1 / capital ratio",
}

METRIC_KW = {
    "credit_impairment": ["impairment", "ecl", "stage 2", "credit cost", "cost of risk", "viu"],
    "operating_costs": ["cost", "costs", "efficiency", "expense"],
    "cet1_ratio": ["cet1", "capital"],
    "total_income": ["nii", "income", "revenue", "hibor", "fee"],
}


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", str(text)).strip())
    return [p for p in parts if len(p) > 40]


def overlap(a: str, b: str) -> float:
    ta = set(re.findall(r"[a-z0-9]+", a.lower()))
    tb = set(re.findall(r"[a-z0-9]+", b.lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta)


def extractive_brief(text: str, metric: str, max_sents: int = 2) -> tuple[str, float]:
    kws = METRIC_KW[metric]
    sents = sentences(text)
    scored = []
    for s in sents:
        sl = s.lower()
        hit = sum(1 for k in kws if k in sl)
        if hit:
            scored.append((hit, len(s), s))
    if not scored:
        brief = f"Metric ({METRIC_LABELS[metric]}) not clearly discussed in this turn."
        return brief, 1.0
    scored.sort(key=lambda x: (-x[0], x[1]))
    chosen = [s for _, __, s in scored[:max_sents]]
    brief = " ".join(chosen)
    return brief, float(overlap(brief, text))


def main():
    PROC.mkdir(parents=True, exist_ok=True)
    corp = pd.read_csv(PROC / "corpus_analyst.csv")
    # Focus on the two episode windows + a few Topic 1 negatives
    windows = [
        ("hsbc", "2025-interim"),
        ("barclays", "2026-q2"),
    ]
    rows = []
    for bank, quarter in windows:
        sub = corp[(corp["bank"] == bank) & (corp["quarter"] == quarter)].copy()
        # Prefer Topic 1 / negative lean, else all
        prefer = sub[(sub["topic"] == 1) | (sub["finbert_sentiment"] == "negative")]
        sample = prefer if len(prefer) else sub
        sample = sample.head(6)
        for _, turn in sample.iterrows():
            for metric in METRIC_LABELS:
                brief, faith = extractive_brief(turn["text"], metric)
                rows.append(
                    {
                        "bank": bank,
                        "quarter": quarter,
                        "speaker": turn.get("speaker"),
                        "topic": turn.get("topic"),
                        "finbert_sentiment": turn.get("finbert_sentiment"),
                        "metric": metric,
                        "metric_label": METRIC_LABELS[metric],
                        "summary": brief,
                        "faithfulness_overlap": round(faith, 3),
                        "method": "extractive",
                    }
                )

    # Optional generative polish on a tiny subset
    if os.environ.get("USE_GEN", "0") == "1":
        try:
            from transformers import pipeline

            gen = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")
            for r in rows[:8]:
                if "not clearly discussed" in r["summary"]:
                    continue
                out = gen(r["summary"][:800], max_length=60, min_length=20, do_sample=False)
                gen_txt = out[0]["summary_text"]
                r["summary_gen"] = gen_txt
                r["faithfulness_overlap_gen"] = round(overlap(gen_txt, r["summary"]), 3)
                r["method"] = "extractive+distilbart"
        except Exception as e:
            print("USE_GEN failed:", e)

    df = pd.DataFrame(rows)
    df.to_csv(PROC / "metric_briefs_faithful.csv", index=False)
    print(df.groupby(["bank", "quarter", "method"]).size())
    print("mean faithfulness", df["faithfulness_overlap"].mean())
    print("wrote", PROC / "metric_briefs_faithful.csv")


if __name__ == "__main__":
    main()
