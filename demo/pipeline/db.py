"""SQLite desk DB — Python's H2: one file, zero server.

Pipeline notebooks still *emit* CSVs (easy to debug in Jupyter). Sync folds the
product tables into ``data/desk.sqlite`` so the UI / cloud deploy reads one DB.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from .paths import DB_PATH, PIPELINE_PROCESSED, PIPELINE_ROOT, ensure_demo_dirs

# Tables the desk cares about (CSV name → table name)
CSV_TABLES = {
    "episode_metric_briefs.csv": "metric_briefs",
    "episode_quotes.csv": "quotes",
    "episode_topic_share.csv": "topic_share",
    "alert_null_protocol.csv": "protocol",
    "peer_gap_matched.csv": "peer_gap",
    "sentiment_by_topic.csv": "sentiment_by_topic",
    "structured_vs_unstructured.csv": "struct_vs_unstruct",
    "metric_briefs_faithful.csv": "metric_briefs_faithful",
    "all_qa_pairs.csv": "qa_pairs_full",
}

PRA_NOTE = PIPELINE_ROOT / "docs" / "assignment2" / "pra_notes" / "pra_notes.md"


def connect(db: Path | None = None) -> sqlite3.Connection:
    ensure_demo_dirs()
    path = Path(db or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def build_db(src: Path | None = None, db: Path | None = None) -> dict[str, Any]:
    """Ingest Pipeline processed artifacts into a fresh SQLite file."""
    src = Path(src or PIPELINE_PROCESSED)
    db_path = Path(db or DB_PATH)
    if not src.exists():
        raise FileNotFoundError(f"Pipeline processed dir missing: {src}")

    if db_path.exists():
        db_path.unlink()

    loaded, missing = [], []
    with connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE meta (
              key TEXT PRIMARY KEY,
              value TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE episodes (
              id TEXT PRIMARY KEY,
              label TEXT,
              bank TEXT,
              quarter TEXT,
              calendar_period TEXT,
              struct_quarter TEXT,
              n_turns INTEGER,
              finbert_net REAL,
              topic1_turns INTEGER,
              topic1_neg_share REAL,
              peer_gap_hsbc_minus_barclays REAL,
              peer_hsbc_net REAL,
              peer_barclays_net REAL,
              peer_hsbc_n INTEGER,
              peer_barclays_n INTEGER,
              peer_hsbc_non_neutral_share REAL,
              peer_barclays_non_neutral_share REAL,
              peer_usable_for_a2 INTEGER,
              peer_caveat TEXT,
              rules_fired TEXT,
              verdict TEXT,
              headline TEXT,
              pitch_angle TEXT,
              payload_json TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE documents (
              name TEXT PRIMARY KEY,
              mime TEXT,
              body TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE assets (
              name TEXT PRIMARY KEY,
              path TEXT,
              bytes BLOB
            )
            """
        )

        # Episodes
        multi = src / "supervisory_episodes.json"
        single = src / "supervisory_episode.json"
        episodes: list[dict] = []
        if multi.exists():
            episodes = json.loads(multi.read_text())
            loaded.append(multi.name)
        elif single.exists():
            episodes = [json.loads(single.read_text())]
            loaded.append(single.name)
        else:
            missing.append("supervisory_episodes.json")

        for ep in episodes:
            conn.execute(
                """
                INSERT INTO episodes VALUES (
                  ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                )
                """,
                (
                    ep.get("id"),
                    ep.get("label"),
                    ep.get("bank"),
                    ep.get("quarter"),
                    ep.get("calendar_period"),
                    ep.get("struct_quarter"),
                    ep.get("n_turns"),
                    ep.get("finbert_net"),
                    ep.get("topic1_turns"),
                    ep.get("topic1_neg_share"),
                    ep.get("peer_gap_hsbc_minus_barclays"),
                    ep.get("peer_hsbc_net"),
                    ep.get("peer_barclays_net"),
                    ep.get("peer_hsbc_n"),
                    ep.get("peer_barclays_n"),
                    ep.get("peer_hsbc_non_neutral_share"),
                    ep.get("peer_barclays_non_neutral_share"),
                    1 if ep.get("peer_usable_for_a2") else 0,
                    ep.get("peer_caveat"),
                    json.dumps(ep.get("rules_fired") or []),
                    ep.get("verdict"),
                    ep.get("headline"),
                    ep.get("pitch_angle"),
                    json.dumps(ep),
                ),
            )

        # CSV tables
        for fname, table in CSV_TABLES.items():
            path = src / fname
            if not path.exists():
                missing.append(fname)
                continue
            df = pd.read_csv(path)
            df.to_sql(table, conn, if_exists="replace", index=False)
            loaded.append(fname)

        # PRA note + finetune metrics as documents
        if PRA_NOTE.exists():
            conn.execute(
                "INSERT INTO documents VALUES (?,?,?)",
                ("pra_notes.md", "text/markdown", PRA_NOTE.read_text()),
            )
            loaded.append("pra_notes.md")
        else:
            missing.append("pra_notes.md")

        metrics = src / "finetune_metrics.json"
        if metrics.exists():
            conn.execute(
                "INSERT INTO documents VALUES (?,?,?)",
                ("finetune_metrics.json", "application/json", metrics.read_text()),
            )
            loaded.append(metrics.name)

        # Peer chart blob (so cloud only needs the .sqlite file)
        peer_png = src / "peer_gap_matched.png"
        if peer_png.exists():
            conn.execute(
                "INSERT INTO assets VALUES (?,?,?)",
                ("peer_gap_matched.png", str(peer_png), peer_png.read_bytes()),
            )
            loaded.append(peer_png.name)
        else:
            missing.append(peer_png.name)

        conn.execute(
            "INSERT INTO meta VALUES (?, ?)",
            ("source", str(src)),
        )
        conn.execute(
            "INSERT INTO meta VALUES (?, ?)",
            ("built_tables", json.dumps(sorted({*CSV_TABLES.values(), "episodes", "documents", "assets"}))),
        )
        conn.commit()

    return {
        "db": str(db_path),
        "loaded": loaded,
        "missing": missing,
        "n_episodes": len(episodes),
        "size_bytes": db_path.stat().st_size if db_path.exists() else 0,
    }


def list_episodes(db: Path | None = None) -> list[dict]:
    with connect(db) as conn:
        rows = conn.execute(
            "SELECT payload_json FROM episodes ORDER BY id"
        ).fetchall()
    episodes = [json.loads(r["payload_json"]) for r in rows]

    def sort_key(ep: dict) -> tuple:
        bank = str(ep.get("bank") or "").lower()
        period = str(ep.get("calendar_period") or ep.get("quarter") or "").lower()
        # Inbox: reviewed proof cases first, then unreviewed computed quarters
        reviewed = ep.get("reviewed")
        if reviewed is False:
            return (9, bank, period)
        if bank == "hsbc" and ("2025-h1" in period or "2025-interim" in period):
            return (0, period)
        if bank == "barclays" and ("2026" in period):
            return (1, period)
        if "credit" in bank and ("2022" in period):
            return (2, period)
        if reviewed is True or ep.get("id") in {
            "hsbc_2025_h1",
            "barclays_2026_h1",
            "cs_2022_q4",
        }:
            if bank == "hsbc":
                return (0, period)
            if bank == "barclays":
                return (1, period)
            if "credit" in bank:
                return (2, period)
        return (10, bank, period)

    return sorted(episodes, key=sort_key)


def read_table(
    table: str,
    *,
    episode_id: str | None = None,
    db: Path | None = None,
) -> pd.DataFrame:
    with connect(db) as conn:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if not exists:
            return pd.DataFrame()
        if episode_id:
            cols = {
                r[1]
                for r in conn.execute(f"PRAGMA table_info({table})").fetchall()
            }
            if "episode_id" in cols:
                return pd.read_sql_query(
                    f'SELECT * FROM "{table}" WHERE episode_id = ?',
                    conn,
                    params=(episode_id,),
                )
        return pd.read_sql_query(f'SELECT * FROM "{table}"', conn)


def read_document(name: str, db: Path | None = None) -> str | None:
    with connect(db) as conn:
        row = conn.execute(
            "SELECT body FROM documents WHERE name = ?", (name,)
        ).fetchone()
    return None if row is None else row["body"]


def read_asset(name: str, db: Path | None = None) -> bytes | None:
    with connect(db) as conn:
        row = conn.execute(
            "SELECT bytes FROM assets WHERE name = ?", (name,)
        ).fetchone()
    return None if row is None else row["bytes"]


if __name__ == "__main__":
    print(json.dumps(build_db(), indent=2))
