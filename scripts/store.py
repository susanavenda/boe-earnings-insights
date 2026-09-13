"""Pipeline SQLite store — system of record for analysis intermediates.

Notebook contract:
  - **Files = inputs only** (PDFs under data/raw/, Excel under data/structured/,
    hand labels CSV).
  - **Everything else** → this DB (in-memory working set and/or ``data/boe.sqlite``).

    from store import configure, save_df, load_df, flush, hydrate

Modes:
  - ``configure(memory=False)`` — scripts / Demo: read-write ``data/boe.sqlite``
  - ``configure(memory=True)``  — notebook: shared in-memory SQLite, hydrate from
    disk on start, flush to disk after each write (so scripts/Demo still see it)

Env:
  ``BOE_DB`` path to on-disk file (default ``data/boe.sqlite``)
  ``BOE_EXPORT_CSV=1`` also mirror tables as CSV under ``data/processed/``
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
DB_PATH = Path(os.environ.get("BOE_DB", ROOT / "data" / "boe.sqlite"))
EXPORT_CSV = os.environ.get("BOE_EXPORT_CSV", "").strip() in {"1", "true", "yes"}

# Shared in-memory URI (survives across connect() calls while keepalive is held)
_MEM_URI = "file:boe_pipeline?mode=memory&cache=shared"
_MEMORY = False
_AUTO_FLUSH = True
_KEEPALIVE: sqlite3.Connection | None = None

# Logical name → default SQL table (dots/slashes stripped)
_TABLE_ALIASES = {
    "corpus_analyst": "analyst_turns",
    "all_turns": "all_turns",
    "reported_metrics": "reported_metrics",
    "narrative_df": "narrative",
    "peer_matched_quarters": "peer_matched",
    "peer_gap_matched": "peer_gap",
    "structured_vs_unstructured": "struct_vs_unstruct",
    "sentiment_by_topic": "sentiment_by_topic",
    "sentiment_topic_quarter": "sentiment_topic_quarter",
    "sentiment_labels": "sentiment_labels",
    "sentiment_finetuned": "sentiment_finetuned",
    "topic_coherence": "topic_coherence",
    "known_events_crosscheck": "known_events",
    "bertopic_topic_info": "bertopic_topic_info",
    "refined_corpus": "refined_corpus",
    "refined_topic_info": "refined_topic_info",
    "summary_sample": "summary_sample",
    "episode_metric_briefs": "metric_briefs",
    "episode_quotes": "quotes",
    "episode_topic_share": "topic_share",
    "alert_null_protocol": "protocol",
    "event_timeline": "event_timeline",
    "metric_briefs_faithful": "metric_briefs_faithful",
    "supervisory_episodes": "episodes_json",
    "supervisory_episode": "episode_json",
    "finetune_metrics": "finetune_metrics",
    "corpus_manifest": "corpus_manifest",
    "qa_pairs": "qa_pairs",
    "numeric_claims": "numeric_claims",
    "behavioural_signals": "behavioural_signals",
    "prudential_map": "prudential_map",
    "state_summary": "state_summary",
    "numeric_claims_audit": "numeric_claims_audit",
}


def _slug(name: str) -> str:
    base = Path(str(name)).stem
    return _TABLE_ALIASES.get(base, re.sub(r"[^a-zA-Z0-9_]", "_", base))


def configure(
    *,
    memory: bool = False,
    path: Path | str | None = None,
    auto_flush: bool = True,
) -> dict[str, Any]:
    """Select file vs in-memory working DB (notebook should call memory=True)."""
    global DB_PATH, _MEMORY, _AUTO_FLUSH, _KEEPALIVE
    if path is not None:
        DB_PATH = Path(path)
    _MEMORY = bool(memory)
    _AUTO_FLUSH = bool(auto_flush)
    if _KEEPALIVE is not None:
        try:
            _KEEPALIVE.close()
        except Exception:
            pass
        _KEEPALIVE = None
    ensure()
    return info()


def info() -> dict[str, Any]:
    ensure()
    return {
        "mode": "memory" if _MEMORY else "file",
        "path": str(DB_PATH),
        "uri": _MEM_URI if _MEMORY else str(DB_PATH),
        "auto_flush": _AUTO_FLUSH and _MEMORY,
        "tables": list_tables(),
    }


def _open(target: str | Path, *, uri: bool = False) -> sqlite3.Connection:
    conn = sqlite3.connect(str(target), uri=uri, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meta (
          key TEXT PRIMARY KEY,
          value TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
          name TEXT PRIMARY KEY,
          mime TEXT,
          body TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS assets (
          name TEXT PRIMARY KEY,
          mime TEXT,
          bytes BLOB NOT NULL
        )
        """
    )
    conn.commit()


def ensure() -> Path:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROC.mkdir(parents=True, exist_ok=True)
    global _KEEPALIVE
    if _MEMORY:
        if _KEEPALIVE is None:
            _KEEPALIVE = _open(_MEM_URI, uri=True)
            _init_schema(_KEEPALIVE)
        return DB_PATH
    conn = _open(DB_PATH)
    try:
        _init_schema(conn)
    finally:
        conn.close()
    return DB_PATH


def connect() -> sqlite3.Connection:
    """Return a connection to the active store (memory or file)."""
    ensure()
    if _MEMORY:
        # New connection to same shared in-memory DB (keepalive holds it alive)
        return _open(_MEM_URI, uri=True)
    return _open(DB_PATH)


def flush() -> Path:
    """Copy in-memory DB → on-disk ``DB_PATH`` (no-op in file mode)."""
    ensure()
    if not _MEMORY:
        return DB_PATH
    src = connect()
    try:
        dst = _open(DB_PATH)
        try:
            src.backup(dst)
            dst.commit()
        finally:
            dst.close()
    finally:
        src.close()
    return DB_PATH


def hydrate() -> Path:
    """Load on-disk ``DB_PATH`` → in-memory working set (no-op if no file)."""
    ensure()
    if not _MEMORY:
        return DB_PATH
    if not DB_PATH.exists() or DB_PATH.stat().st_size == 0:
        return DB_PATH
    src = _open(DB_PATH)
    try:
        dst = connect()
        try:
            src.backup(dst)
            dst.commit()
        finally:
            dst.close()
    finally:
        src.close()
    return DB_PATH


def _maybe_flush() -> None:
    if _MEMORY and _AUTO_FLUSH:
        flush()


def _json_default(obj: Any) -> Any:
    """Make numpy / set values JSON-serializable."""
    if hasattr(obj, "item"):
        try:
            return obj.item()
        except Exception:
            pass
    if isinstance(obj, (set, tuple)):
        return list(obj)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    return str(obj)


def _cell_to_sql(val: Any) -> Any:
    """SQLite cannot bind list/dict — store nested values as JSON text."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, (list, dict, tuple, set)):
        return json.dumps(val, default=_json_default)
    # numpy scalars → native Python
    if hasattr(val, "item") and not isinstance(val, (bytes, str)):
        try:
            return val.item()
        except Exception:
            pass
    return val


def _sqlize_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if out[col].dtype != object:
            continue
        sample = out[col].dropna().head(8)
        if sample.empty:
            continue
        if any(isinstance(v, (list, dict, tuple, set)) for v in sample):
            out[col] = out[col].map(_cell_to_sql)
    return out


def _cell_from_sql(val: Any) -> Any:
    if not isinstance(val, str):
        return val
    s = val.strip()
    if not s or s[0] not in "[{":
        return val
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return val


def _unsqlize_df(df: pd.DataFrame) -> pd.DataFrame:
    """Restore JSON-encoded list/dict columns written by ``_sqlize_df``."""
    out = df.copy()
    for col in out.columns:
        if out[col].dtype != object:
            continue
        sample = out[col].dropna().head(12)
        if sample.empty:
            continue
        if any(
            isinstance(v, str) and v.strip()[:1] in "[{" for v in sample
        ):
            out[col] = out[col].map(_cell_from_sql)
    return out


def save_df(name: str, df: pd.DataFrame, *, index: bool = False) -> str:
    """Replace table contents with DataFrame. Returns table name."""
    ensure()
    table = _slug(name)
    out = df.copy()
    if index:
        out = out.reset_index()
    out = _sqlize_df(out)
    with connect() as conn:
        out.to_sql(table, conn, if_exists="replace", index=False)
        conn.execute(
            "INSERT OR REPLACE INTO meta VALUES (?, ?)",
            (f"table:{table}", json.dumps({"rows": len(out), "cols": list(out.columns)})),
        )
        conn.commit()
    if EXPORT_CSV:
        path = PROC / f"{Path(str(name)).stem}.csv"
        df.to_csv(path, index=index)
    _maybe_flush()
    return table


def load_df(name: str) -> pd.DataFrame:
    ensure()
    table = _slug(name)
    with connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        if exists:
            return _unsqlize_df(pd.read_sql_query(f'SELECT * FROM "{table}"', conn))
    # Fallback: legacy CSV in processed/
    csv_path = PROC / f"{Path(str(name)).stem}.csv"
    if csv_path.exists():
        return pd.read_csv(csv_path)
    raise FileNotFoundError(
        f"Table '{table}' not in {DB_PATH} and no CSV at {csv_path}"
    )


def has_df(name: str) -> bool:
    table = _slug(name)
    with connect() as conn:
        if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone():
            return True
    return (PROC / f"{Path(str(name)).stem}.csv").exists()


def save_json(name: str, obj: Any) -> None:
    ensure()
    key = Path(str(name)).stem
    body = json.dumps(obj, indent=2)
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO documents VALUES (?,?,?)",
            (key, "application/json", body),
        )
        conn.commit()
    if EXPORT_CSV:
        (PROC / f"{key}.json").write_text(body)
    _maybe_flush()


def load_json(name: str) -> Any:
    ensure()
    key = Path(str(name)).stem
    with connect() as conn:
        row = conn.execute(
            "SELECT body FROM documents WHERE name=?", (key,)
        ).fetchone()
    if row:
        return json.loads(row["body"])
    path = PROC / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())
    raise FileNotFoundError(f"JSON '{key}' not in DB or {path}")


def has_json(name: str) -> bool:
    key = Path(str(name)).stem
    with connect() as conn:
        if conn.execute(
            "SELECT 1 FROM documents WHERE name=?", (key,)
        ).fetchone():
            return True
    return (PROC / f"{key}.json").exists()


def save_text(name: str, text: str, *, mime: str = "text/plain") -> None:
    ensure()
    key = Path(str(name)).name
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO documents VALUES (?,?,?)",
            (key, mime, text),
        )
        conn.commit()
    _maybe_flush()


def load_text(name: str) -> str:
    key = Path(str(name)).name
    with connect() as conn:
        row = conn.execute(
            "SELECT body FROM documents WHERE name=?", (key,)
        ).fetchone()
    if not row:
        raise FileNotFoundError(key)
    return row["body"]


def save_bytes(name: str, data: bytes, *, mime: str = "application/octet-stream") -> None:
    ensure()
    key = Path(str(name)).name
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO assets VALUES (?,?,?)",
            (key, mime, data),
        )
        conn.commit()
    if EXPORT_CSV:
        (PROC / key).write_bytes(data)
    _maybe_flush()


def load_bytes(name: str) -> bytes:
    key = Path(str(name)).name
    with connect() as conn:
        row = conn.execute(
            "SELECT bytes FROM assets WHERE name=?", (key,)
        ).fetchone()
    if row:
        return row["bytes"]
    path = PROC / key
    if path.exists():
        return path.read_bytes()
    raise FileNotFoundError(key)


def list_tables() -> list[str]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY 1"
        ).fetchall()
    return [r[0] for r in rows]


def migrate_processed(src: Path | None = None) -> dict[str, Any]:
    """One-shot: fold existing data/processed CSV+JSON(+PNG) into boe.sqlite."""
    src = Path(src or PROC)
    loaded, skipped = [], []
    if not src.exists():
        raise FileNotFoundError(src)

    for csv in sorted(src.glob("*.csv")):
        try:
            save_df(csv.stem, pd.read_csv(csv))
            loaded.append(csv.name)
        except Exception as e:
            skipped.append(f"{csv.name}: {e}")

    for js in sorted(src.glob("*.json")):
        try:
            save_json(js.stem, json.loads(js.read_text()))
            loaded.append(js.name)
        except Exception as e:
            skipped.append(f"{js.name}: {e}")

    for png in sorted(src.glob("*.png")):
        try:
            save_bytes(png.name, png.read_bytes(), mime="image/png")
            loaded.append(png.name)
        except Exception as e:
            skipped.append(f"{png.name}: {e}")

    # Derive peer_gap table if we have peer_matched
    if has_df("peer_matched_quarters"):
        peer = load_df("peer_matched_quarters")
        if {"calendar_period", "bank", "sentiment_net"}.issubset(peer.columns):
            pivot = peer.pivot_table(
                index="calendar_period",
                columns="bank",
                values="sentiment_net",
                aggfunc="mean",
            )
            if "hsbc" in pivot.columns and "barclays" in pivot.columns:
                gap = (pivot["hsbc"] - pivot["barclays"]).rename("gap").reset_index()
                gap["hsbc"] = pivot["hsbc"].values
                gap["barclays"] = pivot["barclays"].values
                save_df("peer_gap_matched", gap)
                loaded.append("peer_gap_matched (derived)")

    pra = ROOT / "docs" / "assignment2" / "pra_notes" / "pra_notes.md"
    if pra.exists():
        save_text("pra_notes.md", pra.read_text(), mime="text/markdown")
        loaded.append("pra_notes.md")

    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO meta VALUES (?, ?)",
            ("migrated_from", str(src)),
        )
        conn.commit()
    _maybe_flush()

    return {
        "db": str(DB_PATH),
        "mode": "memory" if _MEMORY else "file",
        "loaded": loaded,
        "skipped": skipped,
        "tables": list_tables(),
        "size_bytes": DB_PATH.stat().st_size if DB_PATH.exists() else 0,
    }


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Pipeline SQLite store")
    ap.add_argument("--migrate", action="store_true", help="Import data/processed → boe.sqlite")
    ap.add_argument("--list", action="store_true", help="List tables")
    args = ap.parse_args()
    if args.migrate:
        print(json.dumps(migrate_processed(), indent=2))
    elif args.list:
        ensure()
        print("\n".join(list_tables()))
        print("db:", DB_PATH)
    else:
        ensure()
        print(DB_PATH)
