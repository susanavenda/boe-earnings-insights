#!/usr/bin/env python3
"""Attempted press-coverage cross-check (Hunter's suggestion).

yfinance `.news` on a bank ticker is "news mentioning this name", not coverage
of that bank's own earnings. Recency is a second limit (no 2006–2026 archive).
Does not touch Stage 4 or the Q&A sentiment pipeline.

Rows are tagged to the Stage 8/9 worked examples only as a *scope* label.
Do not treat press_vs_qa as a real signal.
"""
from __future__ import annotations

import re
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
BANK_ALIASES = {"hsbc": ("hsbc",), "barclays": ("barclays",)}
# Hunter: earnings / results / profit / quarter; bank as subject, not merely mentioned.
EARNINGS_TOKENS = ("earnings", "results", "profit", "quarter", "interim")
ANALYST_ON_OTHER = (
    r"\b(downgrade|upgrade|upside|price target|initiates coverage)\b",
    r"\b(on|by|from)\s+(hsbc|barclays)\b",
)


def _bank_as_subject(title: str, aliases: tuple[str, ...]) -> bool:
    """Bank name opens the headline (or follows Can/Will/...), not a later mention."""
    t = title
    for a in aliases:
        if re.match(rf"^(the\s+)?{re.escape(a)}('s)?\b", t):
            return True
        if re.match(rf"^(can|will|does|did|has|have|why|how|what)\s+{re.escape(a)}('s)?\b", t):
            return True
    return False


def flag_earnings_coverage(title: str, bank: str) -> bool:
    """Bank is the subject of an earnings/results headline, not the analyst on another name."""
    t = " ".join(str(title).lower().split())
    aliases = BANK_ALIASES.get(str(bank).lower(), ())
    if not t or not aliases:
        return False
    if not _bank_as_subject(t, aliases):
        return False
    earnings = any(re.search(rf"\b{re.escape(tok)}\b", t) for tok in EARNINGS_TOKENS)
    if not earnings:
        return False
    if any(re.search(p, t) for p in ANALYST_ON_OTHER):
        return False
    return True


def filter_earnings_relevant(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only own-results headlines. Empty is a valid outcome — do not invent rows."""
    if df is None or df.empty or "earnings_relevant" not in df.columns:
        return pd.DataFrame()
    return df.loc[df["earnings_relevant"].eq(True)].reset_index(drop=True)


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


def fetch_press(bank: str, max_items: int | None = None) -> pd.DataFrame:
    """Raw ticker feed. Caller should `filter_earnings_relevant` before scoring."""
    import yfinance as yf

    bank = str(bank).lower()
    if bank not in TICKERS:
        raise KeyError(f"unknown bank {bank!r}; expected {list(TICKERS)}")
    t = yf.Ticker(TICKERS[bank])
    items = list(t.news or [])
    if max_items is not None:
        items = items[:max_items]
    rows = []
    for it in items:
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
                "earnings_relevant": flag_earnings_coverage(fields["title"], bank),
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
    """Gap on *filtered* rows only. treat_as_signal is False unless n_relevant >= 3.

    Missing side is never zero. Small n after the keyword filter is expected.
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
        rel = p[p["earnings_relevant"].eq(True)] if n_press and "earnings_relevant" in p.columns else pd.DataFrame()
        n_relevant = int(len(rel))
        press_net = (
            float(rel["press_net"].mean())
            if n_relevant and "press_net" in rel.columns
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
                "n_earnings_relevant": n_relevant,
                "press_net": press_net,
                "n_qa": n_qa,
                "qa_finbert_net": qa_net,
                "gap": gap,
                "treat_as_signal": bool(n_relevant >= 3 and gap is not None),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    frames = [fetch_press(b) for b in TICKERS]
    raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    kept = filter_earnings_relevant(raw)
    save_df("press_coverage_raw", raw)
    save_df("press_coverage", kept)
    print(
        f"Fetched {len(raw)} ticker mentions; kept {len(kept)} earnings-relevant "
        f"({list(TICKERS)}). Small n is expected."
    )


if __name__ == "__main__":
    main()
