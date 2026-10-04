"""Per-bank earnings-call speaker segmentation (Stage 1.3).

HSBC: ``NAME, ROLE:``
Barclays: ``Name, Firm`` on its own line (no colon)
Credit Suisse (Motley Fool / Thomson archive): ``Name -- Role`` or ``Name -- Firm -- Analyst``
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

HSBC_SPEAKER = re.compile(
    r"^([A-Z][A-Z\.\-\' ]{1,40})(?:,\s*([A-Z][A-Z0-9 &\.\-\'/]{1,60}))?:\s*",
    re.MULTILINE,
)
BARCLAYS_SPEAKER = re.compile(
    r"^([A-Z][A-Za-z\.\-\' ]+?),\s+([A-Za-z0-9 &\.\-\'/]+)\s*$",
    re.MULTILINE,
)
# Tried before Barclays: Barclays regex false-positives on comma-split CS prose.
CS_SPEAKER = re.compile(
    r"^([A-Z][A-Za-z][A-Za-z\.\-\' ]{0,44}?)\s+--\s+(.{3,90}?)\s*$",
    re.MULTILINE,
)
CS_OPERATOR = re.compile(r"^(Operator)\s*$", re.MULTILINE)

SELL_SIDE_FIRMS = [
    "Goldman Sachs",
    "Morgan Stanley",
    "JPMorgan",
    "JP Morgan",
    "Citi",
    "Citigroup",
    "UBS",
    "Barclays",
    "HSBC",
    "Deutsche Bank",
    "Bank of America",
    "BofA",
    "RBC",
    "Jefferies",
    "Jeferies",
    "Autonomous",
    "KBW",
    "Berenberg",
    "Exane",
    "BNP Paribas",
    "Mediobanca",
    "CICC",
    "China Securities",
    "Deutsche Numis",
    "Numis",
    "Societe Generale",
    "Société Générale",
    "Keefe",
    "Bruyette",
]

MGMT_HINTS = [
    "group ceo",
    "group cfo",
    "group chief",
    "chief executive",
    "finance director",
    "investor relations",
    "group treasurer",
    "chief financial",
]


def infer_bank(path) -> str:
    s = str(path).lower()
    if "credit_suisse" in s or "credit-suisse" in s or "/cs/" in s:
        return "credit_suisse"
    if "hsbc" in s:
        return "hsbc"
    if "barclays" in s:
        return "barclays"
    return "unknown"


def infer_quarter(path) -> str:
    name = Path(path).stem.lower()
    m = re.search(r"(20\d{2}).*?(q[1-4]|[1-4]q|interim|annual|fy|h1)", name)
    if not m:
        return Path(path).stem
    y, p = m.group(1), m.group(2)
    mapping = {
        "1q": "q1",
        "2q": "q2",
        "3q": "q3",
        "4q": "q4",
        "fy": "annual",
        "h1": "interim",
    }
    return f"{y}-{mapping.get(p, p)}"


def classify_role(firm, bank, speaker="") -> str:
    fl = (firm or "").lower()
    sl = (speaker or "").lower()
    if sl == "operator" or fl == "operator":
        return "operator"
    if "analyst" in fl:
        return "analyst"
    if any(h in fl for h in MGMT_HINTS):
        return "management"
    bank_l = (bank or "").lower().replace("_", " ")
    for f in SELL_SIDE_FIRMS:
        if f.lower() == bank_l:
            continue
        if f.lower() in fl:
            return "analyst"
    return "management"


def _cs_matches(text: str) -> list[re.Match]:
    items = list(CS_SPEAKER.finditer(text)) + list(CS_OPERATOR.finditer(text))
    items.sort(key=lambda m: m.start())
    return items


def _layout_matches(text: str) -> list[re.Match]:
    hsbc = list(HSBC_SPEAKER.finditer(text))
    if len(hsbc) >= 5:
        return hsbc
    cs = _cs_matches(text)
    if len(cs) >= 5:
        return cs
    return list(BARCLAYS_SPEAKER.finditer(text))


def segment_transcript(text, bank_name) -> pd.DataFrame:
    """Split transcript into (speaker, firm, role, text) turns."""
    matches = _layout_matches(text)
    turns = []
    for i, m in enumerate(matches):
        speaker = m.group(1).strip()
        firm = (m.group(2) if m.lastindex and m.lastindex >= 2 else "") or ""
        firm = firm.strip()
        if len(speaker) > 45 or len(firm) > 90:
            continue
        if speaker.lower().startswith(("and ", "in ", "we ", "the ", "information ", "finally ")):
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        turn_text = text[start:end].strip()
        turn_text = re.sub(r"\n\d+\nInvestor Relations\n?", "\n", turn_text)
        if len(turn_text) < 20:
            continue
        role = classify_role(firm, bank_name, speaker=speaker)
        if role == "operator":
            continue
        turns.append(
            {
                "speaker": speaker,
                "firm": firm,
                "role": role,
                "text": turn_text,
            }
        )
    return pd.DataFrame(turns)
