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
