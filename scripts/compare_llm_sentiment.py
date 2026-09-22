#!/usr/bin/env python3
"""Optional Gemini/GPT vs FinBERT label comparison on a small Q&A sample.

Does not recode human gold. Does not write Stage 4 tables. Skips if no API key.
Set BOE_LLM_PROVIDER=openai|gemini and the matching API key, or pass --provider.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from store import load_df, save_df  # noqa: E402

LABELS = ("positive", "negative", "neutral")
PROMPT = (
    "You label bank earnings Q&A for supervisory screening. "
    "Reply with exactly one word: positive, negative, or neutral. "
    "Hedged or mixed answers are neutral. Do not invent a fourth class.\n\n"
    "TEXT:\n{text}\n"
)


def _provider() -> str | None:
    p = os.environ.get("BOE_LLM_PROVIDER", "").strip().lower()
    if p in {"openai", "gemini"}:
        return p
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return "gemini"
    return None


def _parse_label(raw: str) -> str:
    t = re.sub(r"[^a-z]", "", str(raw).lower())
    for lab in LABELS:
        if t.startswith(lab) or lab in t[:20]:
            return lab
    return "neutral"


def _call_openai(text: str, model: str) -> str:
    from openai import OpenAI

    client = OpenAI()
    r = client.chat.completions.create(
        model=model,
        temperature=0,
        max_tokens=8,
        messages=[{"role": "user", "content": PROMPT.format(text=text[:4000])}],
    )
    return _parse_label(r.choices[0].message.content or "")


def _call_gemini(text: str, model: str) -> str:
    import google.generativeai as genai

    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    genai.configure(api_key=key)
    m = genai.GenerativeModel(model)
    r = m.generate_content(PROMPT.format(text=text[:4000]))
    return _parse_label(getattr(r, "text", "") or "")


def _sample(pairs: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    df = pairs.copy()
    if "answer_text" in df.columns:
        df = df[df["answer_text"].fillna("").str.strip().ne("")]
    if df.empty:
        return df
    n = min(n, len(df))
    if "answer_sentiment" in df.columns:
        parts = []
        for _, g in df.groupby(df["answer_sentiment"].fillna("neutral")):
            k = max(1, n // max(df["answer_sentiment"].nunique(), 1))
            parts.append(g.sample(n=min(k, len(g)), random_state=seed))
        out = pd.concat(parts).drop_duplicates("pair_id")
        if len(out) < n:
            extra = df.drop(out.index, errors="ignore")
            need = min(n - len(out), len(extra))
            if need:
                out = pd.concat([out, extra.sample(n=need, random_state=seed)])
        return out.head(n)
    return df.sample(n=n, random_state=seed)


def compare(n: int = 20, seed: int = 42, provider: str | None = None) -> pd.DataFrame:
    provider = (provider or _provider() or "").lower() or None
    if provider is None:
        return pd.DataFrame()
    pairs = load_df("qa_pairs")
    sample = _sample(pairs, n=n, seed=seed)
    model = (
        os.environ.get("BOE_OPENAI_MODEL", "gpt-4o-mini")
        if provider == "openai"
        else os.environ.get("BOE_GEMINI_MODEL", "gemini-1.5-flash")
    )
    rows = []
    for rec in sample.to_dict("records"):
        text = f"Q: {rec.get('question_text') or ''}\nA: {rec.get('answer_text') or ''}"
        try:
            llm_lab = (
                _call_openai(text, model) if provider == "openai" else _call_gemini(text, model)
            )
            err = ""
        except Exception as exc:
            llm_lab, err = "", f"{type(exc).__name__}: {exc}"
        fin = str(rec.get("answer_sentiment") or "").lower()
        rows.append(
            {
                "pair_id": rec.get("pair_id"),
                "bank": rec.get("bank"),
                "quarter": rec.get("quarter"),
                "finbert_answer": fin,
                "llm_label": llm_lab,
                "llm_provider": provider,
                "llm_model": model,
                "agree_with_finbert": int(bool(llm_lab) and llm_lab == fin),
                "error": err,
                "text_clip": text[:400],
            }
        )
    out = pd.DataFrame(rows)
    save_df("llm_sentiment_compare", out)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--provider", choices=["openai", "gemini"], default=None)
    args = ap.parse_args()
    if not (args.provider or _provider()):
        print("No OPENAI_API_KEY / GEMINI_API_KEY — skip LLM comparison.")
        sys.exit(0)
    out = compare(n=args.n, provider=args.provider)
    if out.empty:
        print("empty")
        return
    print(json.dumps({
        "n": int(len(out)),
        "provider": out["llm_provider"].iloc[0],
        "agree": float(out["agree_with_finbert"].mean()) if len(out) else None,
    }, indent=2))


if __name__ == "__main__":
    main()
