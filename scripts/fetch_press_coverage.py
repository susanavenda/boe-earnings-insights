#!/usr/bin/env python3
"""Post-earnings press coverage as a supplementary signal (Hunter's suggestion).

Scope: recent episode windows only (yfinance news is not a historical archive —
it cannot backfill coverage for 2010, 2015, etc.). Extra source, disclosed as such.
Does not touch Stage 4 or the Q&A sentiment pipeline.

Yahoo's feed is the *current* headlines for HSBA.L / BARC.L. Rows are tagged to
the Stage 8/9 worked examples (HSBC 2025-H1, Barclays 2026-H1) so press tone can
be compared with those episodes' FinBERT net — that tag is the comparison window,
not a claim the article ran in that H1.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from periods import calendar_period  # noqa: E402
from store import save_df  # noqa: E402

TICKERS = {"hsbc": "HSBA.L", "barclays": "BARC.L"}
# Stage 8/9 worked-example windows — not a historical news archive.
EPISODE_WINDOWS = {"hsbc": "2025-H1", "barclays": "2026-H1"}
_SIGN = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}


def _item_fields(it: dict) -> dict:
    """Flatten old (title/link) and current (content.title / canonicalUrl) yfinance news."""
    if not isinstance(it, dict):
        return {"title": "", "publisher": "", "link": "", "published": None}
    content = it.get("content") if isinstance(it.get("content"), dict) else {}
    provider = content.get("provider") if isinstance(content.get("provider"), dict) else {}
    canon = content.get("canonicalUrl") if isinstance(content.get("canonicalUrl"), dict) else {}
    click = content.get("clickThroughUrl") if isinstance(content.get("clickThroughUrl"), dict) else {}
    title = str(it.get("title") or content.get("title") or "").strip()
    publisher = str(it.get("publisher") or provider.get("displayName") or "").strip()
    link = str(it.get("link") or canon.get("url") or click.get("url") or "").strip()
    published = it.get("providerPublishTime") or content.get("pubDate")
    return {"title": title, "publisher": publisher, "link": link, "published": published}


def fetch_press(bank: str, max_items: int = 10) -> pd.DataFrame:
    import yfinance as yf

    bank = str(bank).lower()
    if bank not in TICKERS:
        raise KeyError(f"unknown bank {bank!r}; expected {list(TICKERS)}")
    t = yf.Ticker(TICKERS[bank])
    items = t.news or []
    rows = []
    for it in items[:max_items]:
        fields = _item_fields(it)
        if not fields["title"]:
            continue
        rows.append(
            {
                "bank": bank,
                "ticker": TICKERS[bank],
                "calendar_period": EPISODE_WINDOWS[bank],
                "title": fields["title"],
                "publisher": fields["publisher"],
                "link": fields["link"],
                "published": fields["published"],
                "source": "yfinance_news",
            }
        )
    return pd.DataFrame(rows)


def score_press(df: pd.DataFrame, finbert_pipeline) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        out["press_sentiment"] = pd.Series(dtype=str)
        out["press_score"] = pd.Series(dtype=float)
        out["press_net"] = pd.Series(dtype=float)
        return out
    titles = [str(t) if pd.notna(t) else "" for t in out["title"].tolist()]
    results = finbert_pipeline(titles, truncation=True, max_length=512)
    labels, scores = [], []
    for r in results:
        lab = str(r.get("label", "neutral")).lower()
        sc = float(r.get("score", 0.0))
        labels.append(lab)
        scores.append(sc)
    out["press_sentiment"] = labels
    out["press_score"] = scores
    out["press_net"] = [_SIGN.get(lab, 0.0) * sc for lab, sc in zip(labels, scores)]
    return out


def _with_period(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "calendar_period" not in out.columns:
        if "quarter" not in out.columns:
            out["calendar_period"] = None
        else:
            out["calendar_period"] = out["quarter"].map(calendar_period)
    return out


def compare_press_vs_qa(press_df: pd.DataFrame, corpus_df: pd.DataFrame) -> pd.DataFrame:
    """Press net vs Q&A FinBERT net for the Stage 8/9 windows.

    Same shape as Stage 6.2: one row per bank, gap is None if either side is
    missing — never treat a missing side as zero.
    """
    press = press_df.copy() if press_df is not None else pd.DataFrame()
    corpus = _with_period(corpus_df) if corpus_df is not None else pd.DataFrame()
    if not press.empty and "bank" in press.columns:
        press["bank"] = press["bank"].astype(str).str.lower()
    if not corpus.empty and "bank" in corpus.columns:
        corpus["bank"] = corpus["bank"].astype(str).str.lower()

    rows = []
    for bank, period in EPISODE_WINDOWS.items():
        p = press[press["bank"] == bank] if not press.empty and "bank" in press.columns else pd.DataFrame()
        n_press = int(len(p))
        press_net = (
            float(p["press_net"].mean())
            if n_press and "press_net" in p.columns
            else None
        )

        q = pd.DataFrame()
        if not corpus.empty and "bank" in corpus.columns and "calendar_period" in corpus.columns:
            q = corpus[(corpus["bank"] == bank) & (corpus["calendar_period"] == period)]
        if q.empty or "finbert_net" not in q.columns:
            qa_net, n_qa = None, 0
        else:
            n_qa = int(len(q))
            qa_net = float(q["finbert_net"].mean()) if n_qa else None

        gap = None
        if press_net is not None and qa_net is not None:
            gap = float(press_net - qa_net)
        rows.append(
            {
                "bank": bank,
                "calendar_period": period,
                "n_press": n_press,
                "press_net": press_net,
                "n_qa": n_qa,
                "qa_finbert_net": qa_net,
                "gap": gap,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    frames = [fetch_press(b) for b in TICKERS]
    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    save_df("press_coverage_raw", combined)
    print(f"Fetched {len(combined)} press items across {list(TICKERS)}")


if __name__ == "__main__":
    main()
