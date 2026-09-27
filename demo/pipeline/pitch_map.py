"""A2 deck claims → factory code → what this desk must show.

Slides: https://docs.google.com/presentation/d/1p9LD9KQ2COHz-7NIoFRXdVXlPDQvf7AFsKIBYP0wMTk/edit
The desk is the live proof, not a second pitch.
"""
from __future__ import annotations

import re

import pandas as pd

SLIDES_URL = (
    "https://docs.google.com/presentation/d/"
    "1p9LD9KQ2COHz-7NIoFRXdVXlPDQvf7AFsKIBYP0wMTk/edit"
)

PROBLEM = (
    "Do quarterly earnings Q&A carry a leading signal about prudential condition "
    "that reported metrics alone don't capture?"
)

# Deck: seed category → PRA code (built independently of transcripts).
KPI_TO_PRA = {
    "total_income": {
        "label": "Total income",
        "seed": "Profitability",
        "pra": "P03",
        "pra_name": "Financial position and performance",
    },
    "operating_costs": {
        "label": "Operating costs",
        "seed": "Efficiency",
        "pra": "P03",
        "pra_name": "Administrative / operating expenses",
    },
    "credit_impairment": {
        "label": "Credit impairment / ECL",
        "seed": "Asset quality",
        "pra": "P04",
        "pra_name": "Credit risk and asset quality",
    },
    "cet1_ratio": {
        "label": "CET1",
        "seed": "Capital",
        "pra": "P01",
        "pra_name": "Own funds, capital, RWA",
    },
}

LIQUIDITY_NOTE = (
    "Liquidity (P10–P12) is first-order for the PRA. If earnings Q&A barely "
    "surfaces it, that is a finding — the taxonomy was not fitted to the transcripts."
)

# Order matches the v0.4 deck. Each row is a claim the case file must finish.
DECK_TRAIL = [
    {
        "after": "Problem: Q&A vs structured returns",
        "shows": "Four KPIs — pack vs Q&A",
        "factory": "scripts/build_metric_briefs.py",
        "table": "metric_briefs",
    },
    {
        "after": "Differentiator #1 — how they answered",
        "shows": "Directness · coverage · substitution",
        "factory": "scripts/build_a1_evidence.py → behavioural_signals()",
        "table": "state_summary",
    },
    {
        "after": "Differentiator #2 — supervisor language",
        "shows": "P01 / P03 / P04 on the four KPI tiles",
        "factory": "docs/assignment2/A2_prudential_taxonomies.md",
        "table": "prudential_map",
    },
    {
        "after": "Soft quarter + packs agree → WATCH",
        "shows": "This case verdict + protocol A3",
        "factory": "scripts/build_supervisory_episode.py",
        "table": "episodes / protocol",
    },
    {
        "after": "62 paired quarters; never fillna(0)",
        "shows": "Matched peer, 2012–2025",
        "factory": "scripts/periods.py → calendar_period() / in_peer_window()",
        "table": "peer_gap · corpus_coverage",
    },
    {
        "after": "Fine-tune not promoted (silver lift is the trap)",
        "shows": "Ops → Check FT gates — human gold only",
        "factory": "scripts/finetune_sentiment.py · score_sentiment_human.py",
        "table": "sentiment_agreement.json",
    },
]


REVIEWED_EPISODE_IDS = frozenset({"hsbc_2025_h1", "barclays_2026_h1", "cs_2022_q4"})


def is_reviewed_episode(ep: dict) -> bool:
    """Desk copy of factory EPISODES — keep in lockstep with scripts/build_supervisory_episode.py."""
    if ep.get("reviewed") is False:
        return False
    if ep.get("reviewed") is True:
        return True
    return ep.get("id") in REVIEWED_EPISODE_IDS


def period_key(label) -> str:
    s = str(label or "").lower().replace("_", "-")
    year_m = re.search(r"20\d{2}", s)
    year = year_m.group(0) if year_m else ""
    if any(tok in s for tok in ("interim", "-h1", "h1", "q2", "2q")):
        tag = "h1"
    elif any(tok in s for tok in ("annual", "-fy", "fy", "q4", "4q")):
        tag = "fy"
    elif "q1" in s or "1q" in s:
        tag = "q1"
    elif "q3" in s or "3q" in s:
        tag = "q3"
    else:
        tag = s
    return f"{year}-{tag}" if year else s


def rows_for_episode(df: pd.DataFrame, ep: dict) -> pd.DataFrame:
    """Keep rows for this bank × calendar period. Empty if no match."""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    bank = str(ep.get("bank") or "").lower()
    if "bank" in out.columns:
        out = out[out["bank"].astype(str).str.lower() == bank]
    keys = {
        period_key(ep.get("calendar_period")),
        period_key(ep.get("quarter")),
        period_key(ep.get("struct_quarter")),
    }
    keys.discard("")
    keys.discard("-")
    for col in ("calendar_period", "quarter", "struct_quarter"):
        if col not in out.columns:
            continue
        hit = out[col].map(period_key).isin(keys)
        if bool(hit.any()):
            return out.loc[hit].copy()
    return out.iloc[0:0]


def coverage_line(cov: pd.DataFrame) -> str:
    """One line from corpus_coverage; fallback is the deck's published counts."""
    if cov is None or cov.empty or "year" not in cov.columns:
        return (
            "Deck: 136 results calls · 62 paired quarters (124 transcripts) · "
            "peer charts 2012–2025 · missing stays missing."
        )
    hs = cov["hsbc"] if "hsbc" in cov.columns else 0
    ba = cov["barclays"] if "barclays" in cov.columns else 0
    years = pd.to_numeric(cov["year"], errors="coerce")
    paired = int(((pd.to_numeric(hs, errors="coerce").fillna(0) > 0)
                  & (pd.to_numeric(ba, errors="coerce").fillna(0) > 0)).sum())
    n_hs = int(pd.to_numeric(hs, errors="coerce").fillna(0).sum())
    n_ba = int(pd.to_numeric(ba, errors="coerce").fillna(0).sum())
    both = cov[(years >= 2012) & (years <= 2025)] if years.notna().any() else cov
    return (
        f"Live: HSBC {n_hs} · Barclays {n_ba} results calls · "
        f"{paired} years with both banks on the year grid. "
        "Deck pairing is by quarter (62 paired quarters). "
        "Peer charts 2012–2025. Never fillna(0) on a gap."
    )


def trail_for(ep: dict) -> str:
    if ep.get("reviewed") is False:
        return (
            "Same A1–A3/N1 rules as the Case File. Unreviewed — not captioned."
        )
    bank = str(ep.get("bank") or "").lower()
    if bank == "hsbc":
        return (
            "Completes the episode slide: soft Q&A + packs agree → WATCH (A3), "
            "not a peer ALERT."
        )
    if bank == "barclays":
        return (
            "2026 is in progress (2 quarters to date on the deck). "
            "Peer charts stay 2012–2025. The pair for HSBC 2025-H1 is Barclays 2025-H1."
        )
    if "credit" in bank:
        return (
            "Credit Suisse is built and parses; the deck holds it for A3, "
            "not this submission's scope."
        )
    return "Protocol case from scripts/build_supervisory_episode.py."


def inbox_bucket(ep: dict) -> str:
    """Deck buckets: paired quarter · 2026 in progress · CS held for A3."""
    bank = str(ep.get("bank") or "").lower()
    blob = " ".join(
        str(ep.get(k) or "") for k in ("calendar_period", "quarter", "id")
    ).lower()
    if "credit" in bank:
        return "a3"
    if "2026" in blob:
        return "in_progress"
    return "paired"


def inbox_period_label(ep: dict) -> str:
    bank = str(ep.get("bank") or "").lower()
    if "credit" in bank:
        q = str(ep.get("quarter") or ep.get("calendar_period") or "")
        return q.replace("-q4", "-Q4").replace("-q2", "-Q2").replace("-q1", "-Q1").replace("-q3", "-Q3")
    return str(ep.get("calendar_period") or ep.get("quarter") or "")
