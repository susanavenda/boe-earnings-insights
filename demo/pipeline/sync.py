"""Build Demo desk.sqlite from Pipeline boe.sqlite (preferred) or legacy CSVs."""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from pathlib import Path

from .paths import (
    DB_PATH,
    DEMO_DATA,
    PIPELINE_PROCESSED,
    PIPELINE_ROOT,
    RUN_LOG,
    SNAPSHOT_DIR,
    ensure_demo_dirs,
)
from .registry import record_run

PIPELINE_DB = PIPELINE_ROOT / "data" / "boe.sqlite"


def _copy_pipeline_db() -> dict:
    """Ship a product subset from Pipeline boe.sqlite → Demo desk.sqlite."""
    if not PIPELINE_DB.exists():
        raise FileNotFoundError(PIPELINE_DB)

    if DB_PATH.exists():
        DB_PATH.unlink()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    src = sqlite3.connect(str(PIPELINE_DB))
    dst = sqlite3.connect(str(DB_PATH))
    src.row_factory = sqlite3.Row

    # Tables the desk reads (Pipeline store names → desk tables)
    table_map = {
        "metric_briefs": "metric_briefs",
        "quotes": "quotes",
        "topic_share": "topic_share",
        "protocol": "protocol",
        "peer_gap": "peer_gap",
        "sentiment_by_topic": "sentiment_by_topic",
        "struct_vs_unstruct": "struct_vs_unstruct",
        "metric_briefs_faithful": "metric_briefs_faithful",
        "state_summary": "state_summary",
        "qa_pairs": "qa_pairs",
        "qa_pairs_full": "qa_pairs_full",
        "behavioural_signals": "behavioural_signals",
        "prudential_map": "prudential_map",
        "corpus_manifest": "corpus_manifest",
        "numeric_claims": "numeric_claims",
        "cs_quarter_trend": "cs_quarter_trend",
        "event_timeline": "event_timeline",
        "pra_supervisor_log": "pra_supervisor_log",
        "corpus_coverage": "corpus_coverage",
    }

    dst.execute(
        "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)"
    )
    dst.execute(
        "CREATE TABLE documents (name TEXT PRIMARY KEY, mime TEXT, body TEXT)"
    )
    dst.execute(
        "CREATE TABLE assets (name TEXT PRIMARY KEY, path TEXT, bytes BLOB)"
    )
    dst.execute(
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

    loaded, missing = [], []

    # Episodes from documents JSON
    row = src.execute(
        "SELECT body FROM documents WHERE name='supervisory_episodes'"
    ).fetchone()
    if not row:
        row = src.execute(
            "SELECT body FROM documents WHERE name='supervisory_episode'"
        ).fetchone()
        episodes = [json.loads(row["body"])] if row else []
    else:
        episodes = json.loads(row["body"])
        if isinstance(episodes, dict):
            episodes = [episodes]

    for ep in episodes:
        dst.execute(
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
    loaded.append(f"episodes×{len(episodes)}")

    src_tables = {
        r[0]
        for r in src.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }

    for src_name, dst_name in table_map.items():
        if src_name not in src_tables:
            missing.append(src_name)
            continue
        cols = [r[1] for r in src.execute(f"PRAGMA table_info({src_name})").fetchall()]
        col_sql = ", ".join('"' + c + '"' for c in cols)
        create_cols = ", ".join('"' + c + '"' for c in cols)
        dst.execute(f'CREATE TABLE "{dst_name}" ({create_cols})')
        for r in src.execute(f'SELECT {col_sql} FROM "{src_name}"'):
            placeholders = ", ".join("?" * len(cols))
            dst.execute(
                f'INSERT INTO "{dst_name}" VALUES ({placeholders})',
                tuple(r),
            )
        loaded.append(dst_name)

    # documents of interest
    for name in ("pra_notes.md", "finetune_metrics"):
        r = src.execute(
            "SELECT name, mime, body FROM documents WHERE name=?", (name,)
        ).fetchone()
        if r:
            dst.execute(
                "INSERT INTO documents VALUES (?,?,?)",
                (r["name"] if name != "finetune_metrics" else "finetune_metrics.json",
                 r["mime"],
                 r["body"]),
            )
            loaded.append(name)
        else:
            missing.append(name)

    # peer chart
    asset = src.execute(
        "SELECT name, bytes FROM assets WHERE name='peer_gap_matched.png'"
    ).fetchone()
    if asset:
        dst.execute(
            "INSERT INTO assets VALUES (?,?,?)",
            (asset["name"], str(PIPELINE_PROCESSED / "peer_gap_matched.png"), asset["bytes"]),
        )
        (DEMO_DATA / "peer_gap_matched.png").write_bytes(asset["bytes"])
        loaded.append("peer_gap_matched.png")
    else:
        png = PIPELINE_PROCESSED / "peer_gap_matched.png"
        if png.exists():
            data = png.read_bytes()
            dst.execute(
                "INSERT INTO assets VALUES (?,?,?)",
                ("peer_gap_matched.png", str(png), data),
            )
            (DEMO_DATA / "peer_gap_matched.png").write_bytes(data)
            loaded.append("peer_gap_matched.png")
        else:
            missing.append("peer_gap_matched.png")

    dst.execute(
        "INSERT INTO meta VALUES (?, ?)",
        ("source", str(PIPELINE_DB)),
    )
    dst.commit()
    src.close()
    dst.close()

    return {
        "db": str(DB_PATH),
        "source": str(PIPELINE_DB),
        "loaded": loaded,
        "missing": missing,
        "n_episodes": len(episodes),
        "size_bytes": DB_PATH.stat().st_size,
    }


def sync_snapshot(src: Path | None = None, *, keep_csv: bool = False) -> dict:
    ensure_demo_dirs()
    if PIPELINE_DB.exists():
        db_info = _copy_pipeline_db()
    else:
        # Legacy fallback: fold CSVs
        from .db import build_db

        db_info = build_db(src=Path(src or PIPELINE_PROCESSED), db=DB_PATH)

    if SNAPSHOT_DIR.exists() and not keep_csv:
        for p in SNAPSHOT_DIR.iterdir():
            if p.is_file() and p.name not in {"manifest.json", "README.txt"}:
                p.unlink()

    (SNAPSHOT_DIR / "README.txt").write_text(
        "Product DB: ../../desk.sqlite\n"
        "Source of truth: Pipeline data/boe.sqlite\n"
    )
    manifest = {
        "db": db_info,
        "product": str(DB_PATH),
        "pipeline_db": str(PIPELINE_DB),
        "note": "Demo reads desk.sqlite; Pipeline owns boe.sqlite (not CSV).",
    }
    (SNAPSHOT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2))
    RUN_LOG.write_text(json.dumps({"last_sync": manifest}, indent=2))
    record_run("sync", {"db": str(DB_PATH), "n_episodes": db_info.get("n_episodes")})
    return manifest


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep-csv", action="store_true")
    args = ap.parse_args()
    print(json.dumps(sync_snapshot(keep_csv=args.keep_csv), indent=2))
