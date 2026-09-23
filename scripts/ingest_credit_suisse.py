#!/usr/bin/env python3
"""Ingest Credit Suisse Q4 2022 into sqlite and rebuild supervisory episodes.

Does not re-run Stages 1–7 on HSBC/Barclays. Appends CS analyst turns + 4 KPI rows,
scores FinBERT, then calls build_supervisory_episode.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
os.environ.setdefault("TRANSFORMERS_NO_FLAX", "1")

import pandas as pd
import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_supervisory_episode import main as build_episodes  # noqa: E402
from segment_transcripts import infer_bank, infer_quarter, segment_transcript  # noqa: E402
from store import configure, load_df, save_df  # noqa: E402

PDF = ROOT / "data" / "raw" / "transcripts" / "credit_suisse" / "2022-q4-results-qa-transcript.pdf"
XLSX = ROOT / "data" / "structured" / "credit_suisse" / "2022-q4-financial-tables.xlsx"
BANK = "credit_suisse"


def extract_transcript_text(pdf_path: Path) -> str:
    text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text.append(page_text)
    return "\n".join(text)


def clean_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\d+", "", text)
    try:
        from nltk.corpus import stopwords
        from nltk.tokenize import word_tokenize

        tokens = word_tokenize(text)
        stop = set(stopwords.words("english"))
        tokens = [t for t in tokens if t.isalpha() and t not in stop]
        return " ".join(tokens)
    except Exception:
        tokens = re.findall(r"[a-z]+", text)
        return " ".join(t for t in tokens if len(t) > 2)


def score_finbert(texts: list[str]) -> tuple[list[str], list[float]]:
    # Manual forward pass — transformers.pipeline imports tensorflow via image ops (protobuf clash).
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tok = AutoTokenizer.from_pretrained("ProsusAI/finbert")
    model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
    model.eval()
    id2label = {int(k): str(v).lower() for k, v in model.config.id2label.items()}
    labels, scores = [], []
    with torch.no_grad():
        for t in texts:
            inputs = tok(t, return_tensors="pt", truncation=True, max_length=512)
            prob = torch.softmax(model(**inputs).logits[0], dim=0)
            idx = int(prob.argmax())
            labels.append(id2label[idx])
            scores.append(float(prob[idx]))
    return labels, scores


def _direction(curr, prev, flat_tol=0.01) -> str:
    if curr is None or prev is None or prev == 0:
        return "flat"
    chg = (curr - prev) / abs(prev)
    if abs(chg) <= flat_tol:
        return "flat"
    return "up" if chg > 0 else "down"


def reported_rows() -> pd.DataFrame:
    df = pd.read_excel(XLSX, sheet_name="Group key metrics")
    alias = {
        "net revenues": "total_income",
        "provision for credit losses": "credit_impairment",
        "total operating expenses": "operating_costs",
        "cet1 ratio": "cet1_ratio",
    }
    rows = []
    for _, row in df.iterrows():
        key = alias.get(str(row["metric"]).strip().lower())
        if not key:
            continue
        curr, prev = float(row["current"]), float(row["prior"])
        rows.append(
            {
                "bank": BANK,
                "quarter": "2022-q4",
                "metric": key,
                "value": curr,
                "prior": prev,
                "direction": _direction(curr, prev),
                "source": XLSX.name,
                "calendar_period": "2022-FY",
            }
        )
    return pd.DataFrame(rows)


def drop_bank(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or "bank" not in df.columns:
        return df
    return df[df["bank"] != BANK].copy()


def main() -> None:
    db = Path(os.environ.get("BOE_DB", ROOT / "data" / "boe.sqlite"))
    configure(memory=False, path=db, auto_flush=False)
    raw = extract_transcript_text(PDF)
    turns = segment_transcript(raw, BANK)
    if turns.empty:
        raise SystemExit("CS parse produced 0 turns — stop.")
    turns["bank"] = BANK
    turns["quarter"] = infer_quarter(PDF)
    turns["source"] = PDF.name

    all_turns = drop_bank(load_df("all_turns"))
    all_turns = pd.concat([all_turns, turns], ignore_index=True)
    save_df("all_turns", all_turns)

    qa = turns[turns["role"] == "analyst"].copy()
    qa["clean_text"] = qa["text"].apply(clean_text)
    qa = qa[qa["clean_text"].str.split().str.len() > 3].reset_index(drop=True)
    labels, scores = score_finbert(qa["text"].tolist())
    qa["seed_topic"] = None
    qa["topic"] = -1
    qa["finbert_sentiment"] = labels
    qa["finbert_score"] = scores
    qa["finbert_net"] = [
        s if lab == "positive" else -s if lab == "negative" else 0.0 for lab, s in zip(labels, scores)
    ]
    qa["ldsa_sentiment"] = None
    qa["ldsa_net"] = None
    qa["ft_sentiment"] = None
    qa["ft_score"] = None
    qa["gold_label"] = None

    corp = drop_bank(load_df("corpus_analyst"))
    # keep column order of existing table
    for col in corp.columns:
        if col not in qa.columns:
            qa[col] = None
    qa = qa[list(corp.columns)]
    corp = pd.concat([corp, qa], ignore_index=True)
    save_df("corpus_analyst", corp)

    reported = drop_bank(load_df("reported_metrics"))
    reported = pd.concat([reported, reported_rows()], ignore_index=True)
    save_df("reported_metrics", reported)

    n_a = int((turns["role"] == "analyst").sum())
    n_m = int((turns["role"] == "management").sum())
    print(f"CS turns={len(turns)} analyst={n_a} management={n_m} corpus_rows={len(qa)}")
    print(qa["finbert_sentiment"].value_counts().to_string())
    print(f"FinBERT net={qa['finbert_net'].mean():.3f}")
    build_episodes()


if __name__ == "__main__":
    main()
