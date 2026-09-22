"""Map bank-specific quarter labels onto a shared calendar period.

HSBC uses interim/annual; Barclays uses q2/fy. Any year (2024, 2025, …)
must land on the same H1/FY key so peer and pack joins work.
"""
from __future__ import annotations

import re

_TAG = {
    "q1": "H1q1",
    "1q": "H1q1",
    "q2": "H1",
    "2q": "H1",
    "interim": "H1",
    "h1": "H1",
    "q3": "Q3",
    "3q": "Q3",
    "q4": "FY",
    "4q": "FY",
    "annual": "FY",
    "fy": "FY",
}


def calendar_period(quarter) -> str:
    q = str(quarter).lower().strip()
    m = re.match(r"(20\d{2})[-_]?(.*)", q)
    if not m:
        return str(quarter)
    year, rest = m.group(1), m.group(2)
    tag = _TAG.get(rest)
    return f"{year}-{tag}" if tag else str(quarter)


_ORDER = {"H1q1": 1, "H1": 2, "Q3": 3, "FY": 4}
_SHORT = {"H1q1": "Q1", "H1": "H1", "Q3": "Q3", "FY": "FY"}


def period_sort_key(label) -> tuple:
    """Chronological key for 2014-H1 / 2025-interim / raw quarter strings."""
    p = calendar_period(label)
    m = re.match(r"(20\d{2})-(H1q1|H1|Q3|FY)$", p)
    if m:
        return (m.group(1), _ORDER[m.group(2)])
    return (str(label), 9)


def compact_period_label(label) -> str:
    """2014-H1 / 2014-interim → 14H1 so a long x-axis stays readable."""
    p = calendar_period(label)
    m = re.match(r"20(\d{2})-(H1q1|H1|Q3|FY)$", p)
    if not m:
        return str(label)
    return f"{m.group(1)}{_SHORT[m.group(2)]}"


def period_fig_width(n: int, *, min_w: float = 10.0, max_w: float = 16.0, per: float = 0.32) -> float:
    """Wide enough for compact period ticks; capped so the figure stays on one slide."""
    return float(max(min_w, min(max_w, per * max(n, 1) + 4.0)))


def readable_period_axis(ax, labels, *, max_ticks: int | None = None) -> None:
    """Integer-positioned date ticks: compact labels (14H1), vertical, thinned to fit."""
    labels = [str(x) for x in labels]
    n = len(labels)
    if n == 0:
        return
    compact = [compact_period_label(x) for x in labels]
    fig_w = float(ax.figure.get_size_inches()[0])
    if max_ticks is None:
        max_ticks = max(8, int(fig_w / 0.42))
    if n <= max_ticks:
        idx = list(range(n))
    else:
        idx = []
        prev_year = None
        for i, lab in enumerate(labels):
            year = period_sort_key(lab)[0]
            tag = calendar_period(lab)
            if year != prev_year or str(tag).endswith("-FY"):
                idx.append(i)
                prev_year = year
        if not idx:
            idx = [0]
        if idx[-1] != n - 1:
            idx.append(n - 1)
        if len(idx) > max_ticks:
            step = max(1, (len(idx) + max_ticks - 1) // max_ticks)
            kept = idx[::step]
            if kept[-1] != idx[-1]:
                kept.append(idx[-1])
            idx = kept
    ax.set_xticks(idx)
    ax.set_xticklabels(
        [compact[i] for i in idx],
        rotation=90,
        ha="center",
        va="top",
        fontsize=8,
    )
    ax.tick_params(axis="x", pad=4, length=3)
    ax.set_xlim(-0.6, n - 0.4)
