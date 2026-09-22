#!/usr/bin/env python3
"""Write a labelled-fake PRA desk activity log.

This is not IR, not a bank rating, and not used by Stages 1–9.
Rows are invented supervisor workflow around the existing episode ids.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from store import save_df  # noqa: E402

OUT_DIR = ROOT / "data" / "synthetic"
OUT_CSV = OUT_DIR / "pra_supervisor_log.csv"

ROWS = [
    {
        "log_id": "syn-001",
        "supervisor_id": "desk_A",
        "timestamp_utc": "2026-07-30T08:05:00Z",
        "episode_id": "hsbc_2025_h1",
        "bank": "hsbc",
        "calendar_period": "2025-H1",
        "action": "opened_pack",
        "protocol_output": "watch",
        "note": "Opened HSBC interim 2025 pack after earnings print.",
    },
    {
        "log_id": "syn-002",
        "supervisor_id": "desk_A",
        "timestamp_utc": "2026-07-30T08:12:00Z",
        "episode_id": "hsbc_2025_h1",
        "bank": "hsbc",
        "calendar_period": "2025-H1",
        "action": "requested_quote",
        "protocol_output": "watch",
        "note": "Asked for impairment / office CRE quote (pair_id on evidence tab).",
    },
    {
        "log_id": "syn-003",
        "supervisor_id": "desk_A",
        "timestamp_utc": "2026-07-30T08:18:00Z",
        "episode_id": "hsbc_2025_h1",
        "bank": "hsbc",
        "calendar_period": "2025-H1",
        "action": "accepted_watch",
        "protocol_output": "watch",
        "note": "Four pack lines agree; FinBERT net soft. Accept A3 WATCH. Not a firm rating.",
    },
    {
        "log_id": "syn-004",
        "supervisor_id": "desk_B",
        "timestamp_utc": "2026-07-30T09:02:00Z",
        "episode_id": "barclays_2026_h1",
        "bank": "barclays",
        "calendar_period": "2026-H1",
        "action": "opened_pack",
        "protocol_output": "null",
        "note": "Opened matched peer window.",
    },
    {
        "log_id": "syn-005",
        "supervisor_id": "desk_B",
        "timestamp_utc": "2026-07-30T09:10:00Z",
        "episode_id": "barclays_2026_h1",
        "bank": "barclays",
        "calendar_period": "2026-H1",
        "action": "rejected_alert",
        "protocol_output": "null",
        "note": "Peer all FinBERT-neutral — not A2-eligible. Do not invent ALERT from a flat print.",
    },
    {
        "log_id": "syn-006",
        "supervisor_id": "desk_B",
        "timestamp_utc": "2026-07-30T09:14:00Z",
        "episode_id": "barclays_2026_h1",
        "bank": "barclays",
        "calendar_period": "2026-H1",
        "action": "closed_null",
        "protocol_output": "null",
        "note": "Closed as null. Logged for audit trail only.",
    },
]


def build() -> pd.DataFrame:
    df = pd.DataFrame(ROWS)
    df["is_synthetic"] = 1
    df["source"] = "synthetic_pra_desk_log"
    df["disclaimer"] = "Invented workflow. Not a Bank of England record."
    return df


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = build()
    df.to_csv(OUT_CSV, index=False)
    save_df("pra_supervisor_log", df)
    print(json.dumps({"rows": int(len(df)), "path": str(OUT_CSV)}, indent=2))


if __name__ == "__main__":
    main()
