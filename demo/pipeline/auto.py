"""Auto-manage Demo desk data from the Pipeline DB.

On open the tool:
  1. If desk already has episodes and Pipeline is missing/older → use frozen pack
  2. If Pipeline ``boe.sqlite`` is newer → sync product tables
  3. If Pipeline exists but has no episodes → run product scripts, then sync

Never trains models. Recalibration stays gated/manual.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import DB_PATH, PIPELINE_ROOT, RUN_LOG, SNAPSHOT_DIR, ensure_demo_dirs
from .registry import record_run
from .run_product import run_product
from .sync import PIPELINE_DB, sync_snapshot

FROZEN_DB = SNAPSHOT_DIR / "desk.sqlite"


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _desk_has_episodes() -> bool:
    if not DB_PATH.exists():
        return False
    try:
        from .db import list_episodes

        return bool(list_episodes())
    except Exception:
        return False


def _pipeline_has_episodes() -> bool:
    if not PIPELINE_DB.exists():
        return False
    import sqlite3

    try:
        con = sqlite3.connect(str(PIPELINE_DB))
        row = con.execute(
            "SELECT 1 FROM documents WHERE name='supervisory_episodes' LIMIT 1"
        ).fetchone()
        con.close()
        return row is not None
    except Exception:
        return False


def freeze_pack() -> Path:
    """Copy current desk.sqlite into snapshots/latest for offline demos."""
    ensure_demo_dirs()
    if not DB_PATH.exists():
        raise FileNotFoundError(DB_PATH)
    shutil.copy2(DB_PATH, FROZEN_DB)
    (SNAPSHOT_DIR / "README.txt").write_text(
        "Frozen supervisory pack for offline demo.\n"
        "App reads ../../desk.sqlite; this copy is the shippable snapshot.\n"
        "Restore: copy desk.sqlite → ../../desk.sqlite\n"
    )
    return FROZEN_DB


def _restore_frozen() -> bool:
    if FROZEN_DB.exists() and FROZEN_DB.stat().st_size > 0:
        shutil.copy2(FROZEN_DB, DB_PATH)
        return True
    return False


def ensure_desk(*, force: bool = False, rebuild_episodes: bool = False) -> dict[str, Any]:
    """Make desk.sqlite current. Safe to call on every UI load."""
    ensure_demo_dirs()
    actions: list[str] = []
    errors: list[str] = []

    pipe_m = _mtime(PIPELINE_DB)
    desk_m = _mtime(DB_PATH)
    need_sync = force or (not DB_PATH.exists()) or (pipe_m > desk_m + 0.5)
    need_build = rebuild_episodes or (
        PIPELINE_ROOT.exists()
        and PIPELINE_DB.exists()
        and not _pipeline_has_episodes()
        and not _desk_has_episodes()
    )

    try:
        if need_build and PIPELINE_DB.exists():
            actions.append("product_scripts")
            run_product(skip_scripts=False)
            actions.append("sync")
            freeze_pack()
            actions.append("freeze")
        elif need_sync and PIPELINE_DB.exists():
            actions.append("sync")
            sync_snapshot()
            freeze_pack()
            actions.append("freeze")
        elif not DB_PATH.exists() or not _desk_has_episodes():
            if _restore_frozen():
                actions.append("restore_frozen")
            elif not PIPELINE_DB.exists():
                errors.append(
                    "No desk pack and no Pipeline DB. "
                    f"Expected frozen {FROZEN_DB} or {PIPELINE_DB}."
                )
            else:
                actions.append("noop")
        else:
            actions.append("noop")
            if not FROZEN_DB.exists() and DB_PATH.exists():
                freeze_pack()
                actions.append("freeze")
    except Exception as e:
        errors.append(str(e))
        if not _desk_has_episodes() and _restore_frozen():
            actions.append("restore_frozen_after_error")

    status = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "actions": actions,
        "errors": errors,
        "pipeline_db": str(PIPELINE_DB),
        "pipeline_mtime": pipe_m,
        "desk_db": str(DB_PATH),
        "desk_mtime": _mtime(DB_PATH),
        "desk_ready": _desk_has_episodes(),
        "frozen": FROZEN_DB.exists(),
        "synced": "sync" in actions or "product_scripts" in actions,
        "offline_ok": _desk_has_episodes(),
    }
    RUN_LOG.write_text(json.dumps({"last_auto": status}, indent=2))
    record_run(
        "auto_ensure",
        {
            "actions": actions,
            "desk_ready": status["desk_ready"],
            "errors": errors[:2],
        },
    )
    return status
