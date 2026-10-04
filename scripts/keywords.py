"""Whole-word keyword matching and reported-metric direction.

Substring matching tagged "forward" as RWA and "decline" as ECL.
"cost of risk" is an impairment phrase, not operating costs.
"capital" on its own is not CET1 — "capital markets" is the usual miss.
"""
from __future__ import annotations

import re

import pandas as pd

# Bare tokens that collide with a longer phrase. The phrase stays a hit for
# whichever list names it explicitly ("cost of risk", "capital ratio").
_BARE_EXCLUSIONS = {
    "cost": re.compile(r"\bcosts?\b(?!\s+of\s+risk\b)", re.I),
    "costs": re.compile(r"\bcosts?\b(?!\s+of\s+risk\b)", re.I),
    "capital": re.compile(r"\bcapital\b(?!\s+markets?\b)", re.I),
}

ABS_DIRECTION_METRICS = frozenset({"operating_costs", "credit_impairment"})

STOP_WORDS = frozenset(
    """
    a an the and or but if in on of to for from with without as at by into over
    after before this that these those it its we our you your they their he she
    his her them is are was were be been being have has had do does did not no
    nor so than then too very can could should would will just about up down out
    off also please thank thanks
    """.split()
)


def _pattern(keyword: str) -> re.Pattern[str]:
    k = keyword.strip().lower()
    special = _BARE_EXCLUSIONS.get(k)
    if special is not None and " " not in k:
        return special
    parts = [re.escape(p) for p in k.split()]
    if len(parts) == 1:
        body = rf"{parts[0]}(?:s|es)?"
    else:
        body = r"\s+".join(parts[:-1] + [rf"{parts[-1]}(?:s|es)?"])
    return re.compile(rf"\b{body}\b", re.I)


def keyword_count(text: str, keyword: str) -> int:
    if not str(keyword).strip():
        return 0
    return len(_pattern(keyword).findall(str(text or "")))


def keyword_in_text(text: str, keyword: str) -> bool:
    return keyword_count(text, keyword) > 0


def any_keyword(text: str, keywords) -> bool:
    return any(keyword_in_text(text, k) for k in keywords)


def faith_label(faith) -> str | None:
    """yes/no when a flag was stored; None when the cell is empty.

    SQLite round-trips booleans as 0.0/1.0, and numpy bools fail `is True`.
    """
    try:
        missing = bool(pd.isna(faith))
    except (TypeError, ValueError):
        missing = faith is None
    if missing:
        return None
    return "yes" if bool(faith) else "no"


def reported_direction(curr, prev, metric: str | None = None, flat_tol: float = 0.01, rescale_pct: bool = False) -> str:
    """Up/down versus the prior print.

    Costs and impairment are compared on absolute value, so a larger charge is
    "up" whether the pack stores it as a positive expense or a negative credit.
    """
    if curr is None or prev is None or prev == 0:
        return "flat"
    curr, prev = float(curr), float(prev)
    if metric in ABS_DIRECTION_METRICS:
        curr, prev = abs(curr), abs(prev)
        if prev == 0:
            return "flat"
    if rescale_pct:
        if abs(curr) <= 1 and abs(prev) > 1:
            curr *= 100
        if abs(prev) <= 1 and abs(curr) > 1:
            prev *= 100
        if prev == 0:
            return "flat"
    chg = (curr - prev) / abs(prev)
    if abs(chg) <= flat_tol:
        return "flat"
    return "up" if chg > 0 else "down"


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(text).lower())


def content_tokens(text: str, word_cap: int | None = None) -> set[str]:
    toks = words(text)
    if word_cap is not None:
        toks = toks[:word_cap]
    return {w for w in toks if len(w) >= 3 and w not in STOP_WORDS}


def directness_v2(question: str, answer: str, answer_word_cap: int = 100) -> float | None:
    """Token overlap with stop words removed, scored on the first ~100 answer words."""
    tq = content_tokens(question)
    ta = content_tokens(answer, word_cap=answer_word_cap)
    if not tq:
        return None
    return round(len(tq & ta) / len(tq), 3)


def narrative_direction(qa_net: float, metric: str | None = None, flat_band: float = 0.05) -> str:
    """Q&A tone as a direction comparable with the reported one.

    Positive tone reads as "up". For costs and impairment a rising charge is bad
    news, so negative tone reads as "up" there.
    """
    narr = "up" if qa_net > flat_band else "down" if qa_net < -flat_band else "flat"
    if metric in ABS_DIRECTION_METRICS:
        narr = {"up": "down", "down": "up"}.get(narr, narr)
    return narr
